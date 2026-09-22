import hashlib
import json
from pathlib import Path
import tempfile

import numpy as np
import torch

from comfy_api.latest import io
import comfy.model_management
import folder_paths

from .geometry import coverage
from .paint import paint_region, library_path
from .noisemaker import worker
from .observe import observe


def fingerprint(*paths):
    digest = hashlib.sha256()
    for path in paths:
        digest.update(Path(path).read_bytes())
    return digest.hexdigest()


class Vector(io.ComfyNode):
    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return fingerprint(Path(__file__).with_name("geometry.py"))

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AgentArtVector", category="Agent Art/Creative", inputs=[
            io.String.Input("path", multiline=True), io.Int.Input("width", default=640, min=1),
            io.Int.Input("height", default=480, min=1), io.String.Input("color", default="[0.2,0.5,0.5]")],
            outputs=[io.Image.Output("image"), io.Mask.Output("coverage")])

    @classmethod
    def execute(cls, path, width, height, color):
        mask = coverage(path, width, height)
        image = np.zeros((height, width, 4), np.float32)
        image[..., :3] = json.loads(color)
        image[..., 3] = mask
        return io.NodeOutput(torch.from_numpy(image[None]), torch.from_numpy(mask[None]))


class Paint(io.ComfyNode):
    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return fingerprint(Path(__file__).with_name("paint.py"), Path(__file__).with_name("geometry.py"), library_path())

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AgentArtPaint", category="Agent Art/Creative", inputs=[
            io.String.Input("path", multiline=True), io.Int.Input("width", default=640, min=1),
            io.Int.Input("height", default=480, min=1), io.String.Input("style", multiline=True, default="{}"),
            io.String.Input("preset", multiline=True, default="")],
            outputs=[io.Image.Output("image"), io.Mask.Output("coverage"), io.String.Output("generated_strokes")])

    @classmethod
    def execute(cls, path, width, height, style, preset):
        image, mask, strokes = paint_region(path, width, height, json.loads(style), preset,
                                           comfy.model_management.throw_exception_if_processing_interrupted)
        return io.NodeOutput(torch.from_numpy(image.copy()[None]), torch.from_numpy(mask[None]), json.dumps(strokes))


class Composite(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AgentArtComposite", category="Agent Art/Creative",
            inputs=[io.Image.Input("back"), io.Image.Input("front")], outputs=[io.Image.Output("image")])

    @classmethod
    def execute(cls, back, front):
        if back.shape != front.shape or back.shape[-1] != 4:
            raise ValueError("Composite requires matching straight RGBA frames; resize/convert explicitly")
        alpha = front[..., 3:] + back[..., 3:]*(1-front[..., 3:])
        rgb = front[..., :3]*front[..., 3:] + back[..., :3]*back[..., 3:]*(1-front[..., 3:])
        rgb = torch.where(alpha > 0, rgb / alpha.clamp_min(1e-12), 0)
        return io.NodeOutput(torch.cat((rgb, alpha), dim=-1))


class NoisemakerNode(io.ComfyNode):
    @classmethod
    def fingerprint_inputs(cls, **kwargs):
        return fingerprint(*(Path(__file__).with_name(name) for name in ("noisemaker.js", "worker.py", "noisemaker.py")))

    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AgentArtNoisemaker", category="Agent Art/Creative", inputs=[
            io.Image.Input("image", optional=True), io.String.Input("program", multiline=True),
            io.Int.Input("width", default=640, min=1), io.Int.Input("height", default=480, min=1),
            io.String.Input("engine_revision")],
            outputs=[io.Image.Output("image"), io.String.Output("receipt")])

    @classmethod
    def execute(cls, program, width, height, engine_revision, image=None):
        spec = json.loads(program)
        with tempfile.TemporaryDirectory(prefix="agent-art-noise-") as temp:
            inputs = {}
            if image is not None:
                if tuple(image.shape) != (1, height, width, 4):
                    raise ValueError("Noisemaker input must be one straight RGBA image at the requested resolution")
                path = Path(temp) / "input.npy"
                np.save(path, image.detach().cpu().numpy()[0], allow_pickle=False)
                inputs[spec.get("input", "o0")] = str(path)
            result = worker.run({**spec, "width": width, "height": height, "inputs": inputs,
                                 "directory": temp, "backend": spec.get("backend", "webgpu")},
                                comfy.model_management.throw_exception_if_processing_interrupted)
            frames = np.stack([np.load(Path(temp)/f"frame-{i:04}.npy", allow_pickle=False)
                               for i in range(len(result["frames"]))])
        return io.NodeOutput(torch.from_numpy(frames), json.dumps({**result, "engine_revision": engine_revision}))


class Observe(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(node_id="AgentArtObserve", category="Agent Art/Creative", inputs=[
            io.Image.Input("image"), io.String.Input("source", multiline=True),
            io.String.Input("metadata", multiline=True, default="{}"),
            io.String.Input("previous", default=""), io.String.Input("strokes", default="", optional=True),
            io.Mask.Input("coverage", optional=True)],
            outputs=[], is_output_node=True)

    @classmethod
    def execute(cls, image, source, metadata, previous, strokes="", coverage=None):
        root = Path(folder_paths.get_output_directory()).resolve()
        root.mkdir(exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix="art-", dir=root))
        prior = None
        if previous:
            path = (root / previous / "master.npy").resolve()
            if not path.is_relative_to(root):
                raise ValueError("Previous revision must be inside Comfy output")
            prior = np.load(path, allow_pickle=False)
        frames = image.detach().cpu().numpy()
        info = json.loads(metadata)
        visible = observe(frames, directory, source, info, prior, json.loads(strokes) if strokes else None)
        if strokes:
            (directory / "strokes.json").write_text(strokes, encoding="utf-8")
        if coverage is not None:
            np.save(directory / "coverage.npy", coverage.detach().cpu().numpy(), allow_pickle=False)
            (directory / "coverage.json").write_text(json.dumps({"semantic": "region coverage", "range": [0, 1],
                "color_space": "data", "origin": "top-left", "dtype": "float32", "alpha": "none"}), encoding="utf-8")
        receipt = {"directory": directory.name, "images": visible,
                   "frames": frames.shape[0], "min": float(frames.min()), "max": float(frames.max())}
        return io.NodeOutput(ui={"images": [{"filename": name, "subfolder": directory.name, "type": "output"} for name in visible],
                                 "text": [json.dumps(receipt)]})


NODES = [Vector, Paint, Composite, NoisemakerNode, Observe]
