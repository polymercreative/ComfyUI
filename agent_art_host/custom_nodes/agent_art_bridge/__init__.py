import json
from pathlib import Path
import tempfile

import numpy as np
from PIL import Image

from agent_art.fields import Field, plane
from agent_art.operations import constant_speed, growth_cpu
from comfy_api.latest import ComfyExtension, io
import folder_paths


ArtField = io.Custom("AGENT_ART_FIELD")


class MaskField(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AgentArtMaskField", category="Agent Art/Fields",
            description="Preserve one Comfy coverage mask as a typed float field. No alpha inversion.",
            inputs=[io.Mask.Input("mask")], outputs=[ArtField.Output("field")],
        )

    @classmethod
    def execute(cls, mask):
        pixels = mask.detach().cpu().numpy()
        if pixels.ndim == 3 and pixels.shape[0] == 1:
            pixels = pixels[0]
        if pixels.ndim != 2:
            raise ValueError("MaskField accepts one HW or 1HW mask; process batches individually")
        return io.NodeOutput(Field(pixels, "mask", ("coverage",)))


class GrowthCPU(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AgentArtGrowthCPU", category="Agent Art/Technical Maps",
            description="Existing Agent Art 4-neighbor CPU reference. Manhattan-biased; no model or SDF required.",
            inputs=[ArtField.Input("mask"), io.Float.Input("speed", default=1.0, min=0.000001, max=1000000),
                    io.String.Input("seeds", default="[[48,30]]", multiline=True)],
            outputs=[ArtField.Output("arrival"), ArtField.Output("reachable")],
        )

    @classmethod
    def execute(cls, mask, speed, seeds):
        speed_field = constant_speed(None, mask, speed)["speed"]
        result = growth_cpu(None, speed_field, json.loads(seeds))
        return io.NodeOutput(result["arrival"], result["reachable"])


class InspectField(io.ComfyNode):
    @classmethod
    def define_schema(cls):
        return io.Schema(
            node_id="AgentArtInspectField", category="Agent Art/Inspection",
            description="Export a scalar float master, metadata and a separately normalized preview.",
            inputs=[ArtField.Input("field")], outputs=[], is_output_node=True,
        )

    @classmethod
    def execute(cls, field):
        values = plane(field, field.kind)
        output = Path(folder_paths.get_output_directory())
        output.mkdir(parents=True, exist_ok=True)
        run = Path(tempfile.mkdtemp(prefix="agent-art-", dir=output))
        np.save(run / "field.npy", field.pixels, allow_pickle=False)
        lo, hi = float(values.min()), float(values.max())
        preview = (values - lo) / (hi - lo) if hi > lo else np.zeros_like(values)
        Image.fromarray(np.round(preview * 255).astype(np.uint8)).save(run / "preview.png")
        metadata = {**field.metadata(), "min": lo, "max": hi,
                    "master": "field.npy", "preview": "preview.png",
                    "preview_encoding": {"offset": lo, "scale": hi - lo, "display_only": True}}
        (run / "field.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return io.NodeOutput(ui={
            "images": [{"filename": "preview.png", "subfolder": run.name, "type": "output"}],
            "text": [json.dumps({**metadata, "subfolder": run.name})],
        })


class AgentArtExtension(ComfyExtension):
    async def get_node_list(self):
        return [MaskField, GrowthCPU, InspectField]


async def comfy_entrypoint():
    return AgentArtExtension()
