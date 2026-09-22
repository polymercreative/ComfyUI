"""Exercise actual Comfy edits and actual MCP inline-image responses."""
import asyncio
import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import numpy as np
from PIL import Image

from agent_art_host.creative.client import Art


ROOT = Path(__file__).resolve().parents[2]


async def main():
    art = Art()
    source = json.loads((ROOT/'agent_art_host/examples/painted-bookmark.json').read_text())
    first = art.create('edit-loop-proof', source)
    before = deepcopy(first['document'])
    start = time.monotonic()
    after = art.edit('edit-loop-proof', {'parts': {'fish': {'paint': {'angle': 45}}}}, first['revision'])
    seconds = time.monotonic()-start
    assert 'part_ring' in after['cached'] and 'part_fish' not in after['cached']
    assert 'part_eye' in after['cached']
    assert after['document']['parts'][0] == before['parts'][0]
    assert 'revision.png' in after['observation']['images']
    # Check region technical export roundtrip and hole independently of the painted image.
    ring = next(i for i in after['images'] if i['node'] == 'inspect_ring')
    region = np.load(ROOT/'output'/ring['subfolder']/'coverage.npy')
    assert region.shape == (1, 480, 640) and region.dtype == np.float32
    assert region[0, 240, 320] == 0 and region[0, 240, 100] == 1
    motion_source = deepcopy(source)
    motion_source['processing']['effects'].append('filter/warp')
    motion_source['processing']['dsl'] = motion_source['processing']['dsl'].replace(
        '.write(o1)', '.warp(strength: 7, scale: 2, seed: 3, speed: 1, wrap: clamp).write(o1)')
    motion_source['processing']['times'] = [i/12 for i in range(12)]
    art.create('motion-bookmark', motion_source)
    process = StdioServerParameters(command=sys.executable,
        args=['-m', 'agent_art_host.creative.mcp_server'], cwd=str(ROOT))
    async with stdio_client(process) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool('edit_art', {'name': 'edit-loop-proof',
                'changes': {'parts': {'fish': {'paint': {'angle': 15}}}}, 'revision': after['revision']})
            assert not result.isError, result
            images = [item for item in result.content if item.type == 'image']
            assert len(images) >= 2, [item.type for item in result.content]
            for image in images:
                Image.open(BytesIO(base64.b64decode(image.data))).verify()
            motion = await session.call_tool('open_art', {'name': 'motion-bookmark'})
            motion_images = [item for item in motion.content if item.type == 'image']
            assert len(motion_images) >= 4
    proof = {'named_revision_seconds': seconds, 'unchanged_parts_cached': True,
             'coverage_roundtrip': True, 'mcp_inline_images': len(images), 'mcp_motion_images': len(motion_images)}
    (ROOT/'output/creative-edit-proof.json').write_text(json.dumps(proof, indent=2))
    print(json.dumps(proof, indent=2))


asyncio.run(main())
