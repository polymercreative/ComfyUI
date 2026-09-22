"""Inspect the examples together, at icon size, and through the browser picker."""
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright
from scipy.ndimage import label

from agent_art_host.creative.client import Art
from .render_showcase import NAMES

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'output/showcase'


def main():
    records=[Art().open(name) for name in NAMES]
    board=Image.new('RGB',(1280,1040),'#e8e4da')
    draw=ImageDraw.Draw(board)
    title=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',23)
    caption=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',17)
    descriptions=['Named leaf shapes / generated paint / spline veins',
                  'Layered vectors / selective paint / local color edits',
                  'Four pressure-sensitive splines / native wet paint',
                  'Noise > warp > palette / 24-frame GPU sequence']
    for i,(record,description) in enumerate(zip(records,descriptions)):
        directory=ROOT/'output'/record['observation']['directory']
        image=Image.open(directory/'frame-0000.png').convert('RGBA')
        image=image.crop(image.getbbox())
        image.thumbnail((530,390),Image.Resampling.LANCZOS)
        x,y=(i%2)*640,(i//2)*510
        board.paste(image,(x+(640-image.width)//2,y+26+(390-image.height)//2),image)
        draw.text((x+38,y+434),record['document']['title'],font=title,fill='#183c43')
        draw.text((x+38,y+470),description,font=caption,fill='#455d61')
    board.save(DEST/'examples.png')
    sage=ROOT/'output'/records[0]['observation']['directory']
    alpha=np.load(sage/'master.npy')[0,...,3]
    _,components=label(alpha>.5)
    assert components==1, f'Sage has {components} disconnected components'
    small=Image.open(sage/'frame-0000.png').convert('RGBA')
    small.thumbnail((128,128),Image.Resampling.LANCZOS)
    proof=Image.new('RGB',(300,160),'#e8e4da')
    proof.paste(small,(10,15),small)
    solid=Image.new('RGBA',alpha.shape[::-1],'#183c43')
    solid.putalpha(Image.fromarray((alpha>.5).astype('uint8')*255))
    solid.thumbnail((128,128),Image.Resampling.LANCZOS)
    proof.paste(solid,(160,15),solid)
    proof.save(DEST/'sage-small-and-silhouette.png')
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1000})
        errors=[]
        page.on('pageerror',lambda error: errors.append(str(error)))
        page.goto('http://127.0.0.1:8794/agent-art?name=kitchen-sage')
        page.wait_for_function('document.querySelector("#hero").naturalWidth>0')
        for name in NAMES:
            page.locator('#examples').select_option(name)
            page.wait_for_function('(name)=>document.querySelector("#name").value===name && new URLSearchParams(location.search).get("name")===name',arg=name)
            page.wait_for_function('document.querySelector("#hero").complete && document.querySelector("#hero").naturalWidth>0')
        assert page.locator('#apply').is_disabled()
        page.get_by_role('button',name='Play motion',exact=True).click()
        page.wait_for_function('document.querySelector("#hero").src.includes("animation.webp") && document.querySelector("#hero").naturalWidth>0')
        assert not errors, errors
        page.screenshot(path=str(DEST/'motion-browser.png'),full_page=True)
        page.locator('#examples').select_option('kitchen-sage')
        page.wait_for_function('new URLSearchParams(location.search).get("name")==="kitchen-sage"')
        page.screenshot(path=str(DEST/'sage-browser.png'),full_page=True)
        browser.close()
    print(json.dumps({'sage_connected_components':components,'browser_errors':errors,
                      'examples_opened':4,'motion_playback':True}))


if __name__=='__main__':
    main()
