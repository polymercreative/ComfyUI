"""Local source files and inspection endpoints inside the existing Comfy host."""
import asyncio
import json
from pathlib import Path
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from aiohttp import web
import folder_paths
from server import PromptServer

from .project import graph, revise, ROOT


_lock = asyncio.Lock()


def project_file(name):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", name):
        raise ValueError("Project name must use letters, numbers, hyphens or underscores")
    root = Path(folder_paths.get_user_directory()) / "agent-art"
    root.mkdir(parents=True, exist_ok=True)
    return root / (name+".json")


def execute(base, nodes):
    request = Request(base+"/prompt", data=json.dumps({"prompt": nodes}).encode(), headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=15) as response:
        queued = json.load(response)
    identity = queued["prompt_id"]
    deadline = time.monotonic()+150
    while time.monotonic() < deadline:
        with urlopen(base+"/history/"+identity, timeout=15) as response:
            history = json.load(response)
        if identity in history:
            result = history[identity]
            if result["status"]["status_str"] != "success":
                failures = [data.get("exception_message", event) for event, data in result["status"]["messages"]
                            if event in ("execution_error", "execution_interrupted")]
                raise RuntimeError("\n".join(failures) or str(result["status"]))
            return identity, result
        time.sleep(0.08)
    raise TimeoutError(f"Render {identity} still queued/running; inspect Comfy history")


def install():
    routes = PromptServer.instance.routes

    @routes.get("/agent-art")
    async def index(request):
        return web.FileResponse(ROOT/"creative/studio.html")

    @routes.get("/agent-art/document/{name}")
    async def read(request):
        try:
            return web.json_response(json.loads(project_file(request.match_info["name"]).read_text(encoding="utf-8")))
        except FileNotFoundError:
            raise web.HTTPNotFound()

    @routes.get("/agent-art/example")
    async def example(request):
        choices = {p.stem: p for p in (ROOT/"examples").glob("*.json")}
        name = request.query.get("name", "painted-bookmark")
        if name not in choices:
            raise web.HTTPNotFound(text="Unknown example")
        return web.json_response(json.loads(choices[name].read_text(encoding="utf-8")))

    @routes.get("/agent-art/examples")
    async def examples(request):
        result = []
        for path in sorted((ROOT/"examples").glob("*.json")):
            source = json.loads(path.read_text(encoding="utf-8"))
            result.append({"name": path.stem, "title": source.get("title", path.stem),
                           "description": source.get("description", "")})
        return web.json_response(result)

    @routes.get("/agent-art/capabilities")
    async def capabilities(request):
        return web.json_response({"version": 1, "source": "named SVG regions with even-odd fill",
            "painting": {"engine": "libmypaint", "interpolation": ["linear", "quadratic", "cubic", "auto"],
                         "controls": ["size", "pressure", "flow", "opacity", "rotation", "speed"],
                         "brushes": ["pencil", "wet-paint", "default"], "native_presets": "preset_json"},
            "processing": {"engine": "Noisemaker", "program": "native DSL", "backends": ["webgpu", "webgl2"],
                           "input": "o0", "output": "o1", "precision": "native float targets; float32 readback"},
            "observations": ["preview", "per-part proofs", "revision comparison", "contact sheet", "onion skin", "motion differences", "atlas", "raw float master"]})

    @routes.get("/agent-art/effects")
    async def effects(request):
        base = ROOT/"vendor/noisemaker/shaders/effects"
        manifest = json.loads((base/"manifest.json").read_text(encoding="utf-8"))
        effect = request.query.get("effect")
        if effect:
            if effect not in manifest:
                raise web.HTTPNotFound(text="Unknown Noisemaker effect")
            help_file = base/effect/"help.md"
            return web.json_response({"id": effect, **manifest[effect],
                "help": help_file.read_text(encoding="utf-8") if help_file.exists() else "",
                "definition": (base/effect/"definition.js").read_text(encoding="utf-8")})
        query = request.query.get("query", "").lower()
        return web.json_response([{ "id": key, "description": value.get("description"),
            "generator": value.get("starter", False), "tags": value.get("tags", [])}
            for key, value in manifest.items() if query in (key+" "+json.dumps(value)).lower()])

    @routes.post("/agent-art/edit")
    async def edit(request):
        body = await request.json()
        try:
            async with _lock:
                path = project_file(body["name"])
                current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
                if body.get("revision") is not None and (not current or body["revision"] != current["revision"]):
                    raise web.HTTPConflict(text="Source changed; reopen before editing")
                if "document" in body:
                    source = body["document"]
                elif current:
                    source = revise(current["document"], body["changes"])
                else:
                    raise ValueError("Create the document before editing")
                prior = current["observation"]["directory"] if current else ""
                nodes = graph(source, prior)
                # Derive the loopback destination from our bound server, never caller Host.
                base = f"http://127.0.0.1:{PromptServer.instance.port}"
                prompt, result = await asyncio.to_thread(execute, base, nodes)
                observation = json.loads(result["outputs"]["observe"]["text"][0])
                images = []
                for output_name, output in result["outputs"].items():
                    for image in output.get("images", []):
                        images.append({**image, "node": output_name, "url": "/view?"+urlencode(image)})
                cached = [name for event, data in result["status"]["messages"] if event == "execution_cached" for name in data["nodes"]]
                record = {"name": body["name"], "revision": current["revision"]+1 if current else 1,
                          "document": source, "observation": observation, "images": images, "prompt_id": prompt,
                          "cached": cached}
                history = path.parent / body["name"]
                history.mkdir(exist_ok=True)
                (history/f'{record["revision"]:06}.json').write_text(json.dumps(record, indent=2), encoding="utf-8")
                temporary = path.with_suffix(".tmp")
                temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
                temporary.replace(path)
                return web.json_response(record)
        except web.HTTPException:
            raise
        except Exception as error:
            return web.json_response({"error": str(error)}, status=400)
