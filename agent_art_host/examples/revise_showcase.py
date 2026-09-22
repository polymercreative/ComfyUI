"""A small named-part edit, measured through the actual MCP transport."""
import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image
from agent_art_host.creative.client import Art
from .make_showcase import rgb, lantern

ROOT=Path(__file__).resolve().parents[2]


async def main():
    changes={'parts':{'cap':{'color':rgb('947048')},'foot':{'color':rgb('886746')}}}
    params=StdioServerParameters(command=sys.executable,args=['-m','agent_art_host.creative.mcp_server'],cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            # Warm this document after switching from other examples.
            await session.call_tool('create_art',{'name':'harbor-lantern','document':lantern()})
            current=Art().open('harbor-lantern')
            start=time.perf_counter()
            result=await session.call_tool('edit_art',{'name':'harbor-lantern','changes':changes,'revision':current['revision']})
            elapsed=time.perf_counter()-start
            assert not result.isError,result.content
            after=Art().open('harbor-lantern')
            cached=[n for n in after['cached'] if n.startswith('part_')]
            assert 'part_glass' in cached and 'part_cap' not in cached
            images=[c for c in result.content if c.type=='image']
            assert len(images)>=3
            for i,image in enumerate(images):
                data=base64.b64decode(image.data)
                Image.open(BytesIO(data)).verify()
                (ROOT/f'output/showcase/lantern-edit-{i}.png').write_bytes(data)
            preview=next(p for p in after['images'] if p['node']=='observe' and p['filename']=='preview.png')
            assert base64.b64decode(images[0].data)==Art().image_bytes(preview)
            report={'seconds':round(elapsed,3),'cached_parts':len(cached),'changed_parts':2,
                    'inline_images':len(images),'main_image_first':True,'changes':changes}
            (ROOT/'output/showcase/edit.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
            (ROOT/'agent_art_host/examples/harbor-lantern.json').write_text(json.dumps(after['document'],indent=2))


if __name__=='__main__':
    asyncio.run(main())
