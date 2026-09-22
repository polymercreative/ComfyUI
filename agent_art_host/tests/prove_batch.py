"""Real MCP batch: one revision, inline eyes, cache reuse and failure isolation."""
import asyncio
import base64
from io import BytesIO
import json
from pathlib import Path
import sys
import time
from urllib.request import urlopen

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from PIL import Image

from agent_art_host.creative.client import Art
from agent_art_host.examples.make_showcase import waves

ROOT=Path(__file__).resolve().parents[2]


async def main():
    art=Art()
    first=art.create('tide-batch-proof',waves())
    edits=[
        {'part':'tidal-ink','stroke':'crest','point':'start','values':{'x':82,'y':235}},
        {'part':'tidal-ink','stroke':'crest','point':'swell','values':{'y':168,'size':56}},
        {'part':'tidal-ink','stroke':'crest','point':'bend','values':{'size':52}},
        {'part':'tidal-ink','stroke':'middle','point':'bend','values':{'y':264,'size':32}},
    ]
    process=StdioServerParameters(command=sys.executable,args=['-m','agent_art_host.creative.mcp_server'],cwd=str(ROOT))
    async with stdio_client(process) as (read,write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            start=time.perf_counter()
            response=await session.call_tool('batch_edit_art',{'name':'tide-batch-proof','edits':edits,'revision':first['revision']})
            seconds=time.perf_counter()-start
            assert not response.isError,response.content
            images=[c for c in response.content if c.type=='image']
            current=art.open('tide-batch-proof')
            assert current['revision']==first['revision']+1
            assert 'part_gold-thread' in current['cached'] and 'part_tidal-ink' not in current['cached']
            assert {'preview.png','revision.png','changed-area.png'}<=set(current['observation']['images'])
            assert len(images)==4
            destination=ROOT/'output/batch-proof'
            destination.mkdir(exist_ok=True)
            for i,item in enumerate(images):
                data=base64.b64decode(item.data)
                Image.open(BytesIO(data)).verify()
                (destination/f'inline-{i}.png').write_bytes(data)
            with urlopen('http://127.0.0.1:8794/history?max_items=1') as request:
                latest_before=json.load(request)
            invalid=await session.call_tool('batch_edit_art',{'name':'tide-batch-proof',
                'edits':[edits[0],{'part':'missing','values':{'color':[1,0,0]}}],'revision':current['revision']})
            assert invalid.isError
            assert art.open('tide-batch-proof')==current
            with urlopen('http://127.0.0.1:8794/history?max_items=1') as request:
                assert json.load(request)==latest_before
            stale=await session.call_tool('batch_edit_art',{'name':'tide-batch-proof','edits':edits,'revision':first['revision']})
            assert stale.isError and art.open('tide-batch-proof')==current
            failed=await session.call_tool('batch_edit_art',{'name':'tide-batch-proof','revision':current['revision'],
                'edits':[{'part':'tidal-ink','stroke':'crest','point':'swell','values':{'size':0}}]})
            assert failed.isError and art.open('tide-batch-proof')==current
    report={'seconds':round(seconds,3),'edits':len(edits),'saved_revisions':1,'inline_images':len(images),
            'untouched_part_cached':True,'invalid_batch_not_queued':True,'stale_rejected':True,
            'render_failure_preserves_source':True,'directory':current['observation']['directory']}
    (destination/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    asyncio.run(main())
