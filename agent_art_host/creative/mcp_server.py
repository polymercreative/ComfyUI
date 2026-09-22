"""MCP mutations return inline images automatically, including motion proofs."""
import argparse
import json
from urllib.parse import urlencode

from mcp.server.fastmcp import FastMCP, Image
from .client import Art


server = FastMCP("Agent Art")
art = Art()


def eyes(result):
    content = [json.dumps({key: result[key] for key in ("name", "revision", "observation", "cached")})]
    # Main proofs first; avoid flooding model context with every unchanged layer.
    for proof in result["images"]:
        changed_part = proof["node"].startswith("inspect_") and proof["node"].replace("inspect_", "part_", 1) not in result["cached"]
        if proof["node"] == "observe" or (changed_part and proof["filename"] == "trajectories.png"):
            content.extend([proof["filename"], Image(data=art.image_bytes(proof), format="png")])
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
def example_art() -> dict:
    """Get a working editable vector/paint/Noisemaker source document to adapt."""
    return art.request("example")


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
