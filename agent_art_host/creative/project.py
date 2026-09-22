"""Small source-to-Comfy compiler. Parts remain independent cache dependencies."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def engine_revision():
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT / "vendor/noisemaker", text=True).strip()


def merge(target, patch):
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def revise(source, changes):
    result = deepcopy(source)
    by_id = {part["id"]: part for part in result["parts"]}
    for key, patch in changes.items():
        if key == "parts":
            for name, update in patch.items():
                if name not in by_id:
                    raise ValueError(f"Unknown part {name}; replace document to add/reorder parts")
                merge(by_id[name], update)
        else:
            result[key] = deepcopy(patch)
    return result


def batch_revise(source, edits):
    """Apply ordered edits to a private copy; callers render and publish once."""
    if not isinstance(edits, list) or not edits:
        raise ValueError("Provide a nonempty edits list")
    result = deepcopy(source)

    def select(items, selector, kind):
        if type(selector) is int and 0 <= selector < len(items):
            return items[selector]
        matches = [item for item in items if item.get("id") == selector] if isinstance(selector, str) else []
        if len(matches) != 1:
            raise ValueError(f"Expected one {kind} matching {selector!r}; found {len(matches)}")
        return matches[0]

    for index, edit in enumerate(edits):
        try:
            if not isinstance(edit, dict) or set(edit)-{"part", "stroke", "point", "values"}:
                raise ValueError("An edit accepts part, stroke, point and values")
            if not isinstance(edit.get("values"), dict) or not edit["values"]:
                raise ValueError("values must be a nonempty object")
            if "point" in edit and "stroke" not in edit:
                raise ValueError("A point target needs a stroke")
            target = select(result["parts"], edit["part"], "part")
            if "stroke" in edit:
                target = select(target.get("paint", {}).get("strokes", []), edit["stroke"], "authored stroke")
            if "point" in edit:
                target = select(target.get("points", []), edit["point"], "point")
            merge(target, edit["values"])
        except (ValueError, KeyError, TypeError) as error:
            raise ValueError(f"Edit {index+1}: {error}") from error
    return result


def graph(source, previous=""):
    if source.get("version") != 1:
        raise ValueError("Expected source version 1")
    width, height = source["width"], source["height"]
    nodes, output, names = {}, None, set()
    packed = json.dumps(source, sort_keys=True)
    for part in source["parts"]:
        name = part["id"]
        if not name or name in names:
            raise ValueError("Part ids must be nonempty and unique")
        names.add(name)
        node = "part_" + name
        inputs = {"path": part["path"], "width": width, "height": height}
        if "paint" in part:
            brush = part.get("brush", "pencil")
            if brush not in ("pencil", "wet-paint", "default"):
                raise ValueError("Unknown bundled brush; use preset_json for native .myb settings")
            preset = part.get("preset_json", "" if brush == "default" else (ROOT/"creative/brushes"/(brush+".myb")).read_text(encoding="utf-8"))
            inputs.update(style=json.dumps({"color": part["color"], **part["paint"]}, sort_keys=True), preset=preset)
            nodes[node] = {"class_type": "AgentArtPaint", "inputs": inputs}
        else:
            inputs["color"] = json.dumps(part["color"])
            nodes[node] = {"class_type": "AgentArtVector", "inputs": inputs}
        nodes["inspect_"+name] = {"class_type": "AgentArtObserve", "inputs": {
            "image": [node, 0], "source": json.dumps(part), "metadata": json.dumps({"part": name, "color_space": "srgb", "alpha": "straight"}),
            "previous": "", "coverage": [node, 1], **({"strokes": [node, 2]} if "paint" in part else {})}}
        if output is not None:
            mix = "composite_" + name
            nodes[mix] = {"class_type": "AgentArtComposite", "inputs": {"back": output, "front": [node, 0]}}
            output = [mix, 0]
        else:
            output = [node, 0]
    metadata = {"color_space": "srgb", "alpha": "straight", "origin": "top-left"}
    if source.get("processing"):
        program = {"output": "o1", "times": [0], "backend": "webgpu", **source["processing"]}
        nodes["process"] = {"class_type": "AgentArtNoisemaker", "inputs": {
            "program": json.dumps(program, sort_keys=True), "width": width, "height": height,
            "engine_revision": engine_revision(), **({"image": output} if output else {})}}
        output = ["process", 0]
        metadata.update(times=program["times"], engine="Noisemaker", revision=engine_revision())
    if output is None:
        raise ValueError("An art document needs parts or a Noisemaker generator")
    nodes["observe"] = {"class_type": "AgentArtObserve", "inputs": {
        "image": output, "source": packed, "metadata": json.dumps(metadata), "previous": previous}}
    return nodes


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Export an art document as a standard ComfyUI API workflow")
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    workflow = graph(json.loads(args.source.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(workflow, indent=2), encoding="utf-8")
