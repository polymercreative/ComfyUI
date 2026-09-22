"""Every completed edit has eyes: display proofs alongside unmodified masters."""
import json
import math
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
from PIL import Image, ImageDraw
from .geometry import sample_stroke


def display(rgba):
    return Image.fromarray(np.round(np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA")


def backing(image):
    background = Image.new("RGBA", image.size, "#e8e4da")
    background.alpha_composite(image)
    return background.convert("RGB")


def observe(frames, directory, source, metadata, previous=None, strokes=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / "master.npy", frames, allow_pickle=False)
    (directory / "source.json").write_text(source, encoding="utf-8")
    document = json.loads(source)
    parts = document.get("parts", [document] if "path" in document else [])
    if parts:
        paths = []
        for part in parts:
            color = '#'+''.join(f'{round(c*255):02x}' for c in part.get("color", [0, 0, 0]))
            paths.append(f'<path id={quoteattr(part.get("id", "region"))} d={quoteattr(part["path"])} fill="{color}" fill-rule="evenodd"/>')
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{frames.shape[2]}" height="{frames.shape[1]}" viewBox="0 0 {frames.shape[2]} {frames.shape[1]}"><desc>Editable vector geometry and base colors; native paint is retained separately in source.json.</desc>{"".join(paths)}</svg>'
        (directory / "geometry.svg").write_text(svg, encoding="utf-8")
    (directory / "metadata.json").write_text(json.dumps({**metadata, "shape": list(frames.shape),
        "dtype": str(frames.dtype), "master": "master.npy", "preview_encoding": "clipped RGBA8 display proof only"}, indent=2), encoding="utf-8")
    images = [display(frame) for frame in frames]
    for i, picture in enumerate(images):
        picture.save(directory / f"frame-{i:04}.png")
    proof = backing(images[0])
    proof.thumbnail((960, 720))
    proof.save(directory / "preview.png")
    visible = ["preview.png"]
    if strokes:
        overlay = Image.new("RGBA", images[0].size)
        draw = ImageDraw.Draw(overlay)
        for stroke in strokes:
            points = [(x, y) for x, y, _ in sample_stroke(stroke, step=4)]
            draw.line(points, fill=(13, 64, 84, 130), width=1)
            for point in stroke["points"]:
                x, y = point["x"], point["y"]
                draw.ellipse((x-2, y-2, x+2, y+2), fill=(255, 248, 222, 210))
        trajectories = backing(Image.alpha_composite(images[0], overlay))
        trajectories.thumbnail((960, 720))
        trajectories.save(directory / "trajectories.png")
        visible.append("trajectories.png")
    if previous is not None and previous.shape == frames.shape:
        delta = np.abs(frames-previous)
        change = np.max(delta, axis=(0, 3))
        heat = np.zeros((*change.shape, 4), np.float32)
        heat[..., 0] = np.clip(change*4, 0, 1)
        heat[..., 1] = heat[..., 0]*0.3
        heat[..., 3] = 1
        before = backing(display(previous[0]))
        after = backing(images[0])
        compare = Image.new("RGB", (before.width*3, before.height+28), "#17232b")
        for x, (label, img) in enumerate(zip(("Previous", "Current", "Difference x4"), (before, after, display(heat)))):
            compare.paste(img, (x*before.width, 28))
            ImageDraw.Draw(compare).text((x*before.width+12, 7), label, fill="white")
        compare.thumbnail((1536, 720))
        compare.save(directory / "revision.png")
        visible.append("revision.png")
    if len(images) > 1:
        columns = min(4, len(images))
        atlas = Image.new("RGBA", (images[0].width*columns, images[0].height*math.ceil(len(images)/columns)))
        for i, image in enumerate(images):
            atlas.paste(image, ((i%columns)*image.width, (i//columns)*image.height))
        atlas.save(directory / "atlas.png")
        atlas_info = {"frame_size": list(images[0].size), "columns": columns, "count": len(images),
                      "origin": "top-left", "order": "row-major", "times": metadata.get("times")}
        (directory / "atlas.json").write_text(json.dumps(atlas_info, indent=2), encoding="utf-8")
        indices = np.unique(np.linspace(0, len(images)-1, min(12, len(images)), dtype=int))
        thumb = images[0].copy()
        thumb.thumbnail((320, 220))
        tw, th = thumb.size
        sheet = Image.new("RGB", (tw*columns, (th+24)*math.ceil(len(indices)/columns)), '#17232b')
        for j, i in enumerate(indices):
            frame = backing(images[i])
            frame.thumbnail((tw, th))
            x, y = (j%columns)*tw, (j//columns)*(th+24)
            sheet.paste(frame, (x, y))
            times = metadata.get("times")
            label = f'Frame {i+1}' + (f' · t={times[i]:.3f}' if times else '')
            ImageDraw.Draw(sheet).text((x+8, y+th+5), label, fill='white')
        sheet.save(directory / "contact-sheet.png")
        onion = np.mean(frames, axis=0)
        display(onion).save(directory / "onion.png")
        motion = np.zeros(frames.shape[1:3], np.float32)
        for i in range(1, len(frames)):
            np.maximum(motion, np.max(np.abs(frames[i]-frames[i-1]), axis=2), out=motion)
        display(np.stack((np.clip(motion*4, 0, 1), np.clip(motion*1.3, 0, 1), motion*0, np.ones_like(motion)), axis=2)).save(directory / "motion.png")
        images[0].save(directory / "animation.webp", save_all=True, append_images=images[1:],
                       duration=metadata.get("frame_ms", 100), loop=0, lossless=True)
        visible.extend(["contact-sheet.png", "onion.png", "motion.png"])
    return visible
