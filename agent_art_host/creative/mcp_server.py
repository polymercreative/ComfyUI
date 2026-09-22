"""MCP mutations return inline images automatically, including motion proofs."""
import argparse
from io import BytesIO
import json
import math
from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP, Image
from PIL import Image as PILImage, ImageDraw
from .client import Art


server = FastMCP("Agent Art")
art = Art()


def eyes(result):
    content = [json.dumps({key: result[key] for key in ("name", "revision", "observation", "cached")})]
    # The composed result comes first, regardless of Comfy's node execution order.
    for proof in (p for p in result["images"] if p["node"] == "observe"):
        content.extend([proof["filename"], Image(data=art.image_bytes(proof), format="png")])
    changed = [p for p in result["images"] if p["filename"] == "trajectories.png"
               and p["node"].replace("inspect_", "part_", 1) not in result["cached"]]
    if changed:
        columns = min(4, len(changed))
        selected = changed[:12]
        sheet = PILImage.new("RGB", (columns*240, math.ceil(len(selected)/columns)*204), "#17232b")
        draw = ImageDraw.Draw(sheet)
        for i, proof in enumerate(selected):
            picture = PILImage.open(BytesIO(art.image_bytes(proof))).convert("RGB")
            picture.thumbnail((240, 180))
            x, y = (i%columns)*240, (i//columns)*204
            sheet.paste(picture, (x+(240-picture.width)//2, y+(180-picture.height)//2))
            draw.text((x+8, y+184), proof["node"].removeprefix("inspect_"), fill="white")
        buffer = BytesIO()
        sheet.save(buffer, format="PNG")
        content.extend([f"Changed paint trajectories: {len(selected)} of {len(changed)} parts; full proofs remain in output.",
                        Image(data=buffer.getvalue(), format="png")])
    return content


@server.tool()
def capabilities() -> dict:
    """Discover supported native art operations and source controls."""
    return art.request("capabilities")


@server.tool()
def noisemaker_effects(query: str = "", effect: str = "") -> dict | list:
    """Search installed effects, or get one effect's native parameters, help and definition.

    Use the returned id in processing.effects and native syntax in processing.dsl.
    """
    return art.request("effects?"+urlencode({"query": query, "effect": effect}))


@server.tool()
def list_examples() -> list:
    """Discover editable examples of vector construction, spline painting and GPU processing."""
    return art.request("examples")


@server.tool()
def example_art(name: str = "painted-bookmark") -> dict:
    """Get a named example's editable source document to adapt with create_art."""
    return art.request("example?"+urlencode({"name": name}))


@server.tool()
def create_art(name: str, document: dict) -> list:
    """Create/render editable art. Returns inline visual proofs in this same call."""
    return eyes(art.create(name, document))


@server.tool()
def edit_art(name: str, changes: dict, revision: int) -> list:
    """Merge changes into named parts; rerender affected work and SEE the revision automatically.

    Example changes: {"parts":{"body":{"paint":{"angle":25}}}}.
    Motion programs return contact sheet, onion skin and motion differences.
    """
    return eyes(art.edit(name, changes, revision))


@server.tool()
def batch_edit_art(name: str, edits: list[dict], revision: int) -> list:
    """Apply a batch, render ONCE, and return images immediately. One saved revision.

    Each edit is {part: id, values: {...}}, optionally targeting stroke and point
    by id (preferred) or zero-based index. Values merge; unspecified fields remain.
    Example: [{"part":"tidal-ink","stroke":"crest","point":"swell",
               "values":{"y":150,"size":60}},
              {"part":"gold-thread","stroke":"accent","values":{"color":[.7,.4,.2]}}].
    Edits apply in order to a copy. Invalid targets, stale revisions or failed
    rendering leave the saved document unchanged. Generated fill trajectories
    must be baked into paint.strokes before individual point editing.
    """
    return eyes(art.batch(name, edits, revision))


@server.tool()
def open_art(name: str) -> list:
    """Read editable source and see current artwork without a separate eyes command."""
    result = art.open(name)
    return [json.dumps(result["document"]), *eyes(result)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8794")
    options = parser.parse_args()
    art = Art(options.url)
    server.run()
