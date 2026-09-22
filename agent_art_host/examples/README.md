# Working examples

Use the **Examples** picker at http://127.0.0.1:8794/agent-art or MCP
`list_examples` → `example_art(name)` → `create_art(name, document)`.
The motion example has a **Play motion** button. Exported PNG frames retain alpha.

| Example | What it exercises |
| --- | --- |
| Kitchen sage | Shared stem/leaf attachment geometry; seeded paint fills; spline veins; Noisemaker watercolor |
| Harbor lantern | Named vector parts, selected painted materials and local color revisions |
| Tide ornament | Four sparse splines with varying width/pressure and native wet-paint strokes |
| Lagoon marbling | Native Noisemaker noise → warp → palette; 24 frames, atlas and motion proofs |

These are authored examples, not image-generated assets. The sage was corrected
after reviewing its disconnected leaves. Attachment structure was informed by
[this sage photograph](https://www.gastronomiavasca.net/es/gastro/glossary/salvia);
the photo is not included in the artwork or repository. Leaves, petioles and stem
now share attachment coordinates. Proofing includes the 128-pixel icon and a
connected silhouette, in addition to visual inspection.

## Reproduce

With the host running, from the repository:

```powershell
./.venv/Scripts/python.exe -m agent_art_host.examples.make_showcase
./.venv/Scripts/python.exe -m agent_art_host.examples.render_showcase
./.venv/Scripts/python.exe -m agent_art_host.examples.revise_showcase
./.venv/Scripts/python.exe -m agent_art_host.examples.proof_showcase
```

These commands replace the four named example documents. `make_showcase` retains
the compact drawing construction; generated JSON is the editable native source.
`revise_showcase` changes the lantern's cap/base and saves the revised fixture.
Proofs and measured timings are under ignored `output/showcase/`.

## Ergonomics observed

- Named edits are compact. Changing two lantern colors took **0.57 seconds** here,
  reused 17 part renders, and returned the composite, comparison and one labeled
  trajectory overview in the same MCP call.
- First authoring remains coordinate-heavy. The example construction helpers
  remove repetition, but transforms, reusable groups and named stroke-point edits
  are not yet first-class features. Stroke arrays currently need replacement.
- Paint needs deliberate brush selection: the pencil preset looked weak and
  blurred at broad sizes; wet paint gave coherent tapered ribbons.
- Solid geometry, painted coverage and shader output can be combined without
  raster export/import commands between them. All results retain source and float
  masters, with separate display proofs.
- Pictures arrive after a completed render, not continuously during a stroke.
  They enable inspection; they do not guarantee that the agent actually catches
  structural/artistic mistakes. Reference and silhouette checks still matter.
- Whole example renders measured roughly 0.4–3 seconds for stills and 6.4 seconds
  for the 24-frame shader sequence on this workstation. Cache reuse is measured
  within consecutive edits, not promised across unrelated workflow switches.
- Changed paint trajectories are combined into one labeled overview (up to 12
  parts), after the composed result. Full per-part proofs remain available on disk.

The current tools work for stylized icons, ornaments and shader recipes. These
examples do not establish painterly illustration quality or a production-complete
brush authoring system.
