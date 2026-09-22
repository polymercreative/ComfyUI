"""Run the examples through the real agent-facing MCP interface."""
import asyncio
import base64
import json
from pathlib import Path
import sys
import time

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent_art_host.creative.client import Art

ROOT = Path(__file__).resolve().parents[2]
NAMES = ['kitchen-sage', 'harbor-lantern', 'tide-ornament', 'lagoon-light']


async def main():
    destination = ROOT/'output/showcase'
    destination.mkdir(exist_ok=True)
    results=[]
    params=StdioServerParameters(command=sys.executable,
        args=['-m','agent_art_host.creative.mcp_server'],cwd=str(ROOT))
    async with stdio_client(params) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            for name in NAMES:
                source=json.loads((ROOT/'agent_art_host/examples'/f'{name}.json').read_text())
                start=time.perf_counter()
                result=await session.call_tool('create_art',dict(name=name,document=source))
                if result.isError:
                    raise RuntimeError(result.content)
                seconds=time.perf_counter()-start
                images=[item for item in result.content if item.type=='image']
                for i,image in enumerate(images):
                    (destination/f'{name}-{i}.png').write_bytes(base64.b64decode(image.data))
                record=Art().open(name)
                results.append(dict(name=name,seconds=round(seconds,3),inline_images=len(images),
                    directory=record['observation']['directory'],revision=record['revision']))
                print(results[-1],flush=True)
    (destination/'results.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':
    asyncio.run(main())
