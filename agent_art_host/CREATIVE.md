# Creative operations

## Ownership and architecture

- **Outcome:** create and revise useful art and see the effect in the same operation.
- **Authority chain:** named source parts and native programs → Comfy dependencies →
  native renders → saved artifacts and visual receipts. Sources survive cache eviction.
- **Responsibilities:** Skia rasterizes vector coverage; libmypaint paints; Shapely clips
  generated trajectories; Noisemaker runs native programs; Comfy queues/caches; the
  existing host stores source revisions and serves inspection results.
- **Invariant:** parts share pixel coordinates with top-left origin; conversions and
  color/alpha meanings are explicit. Editing one part leaves other source parts intact.
- **Existing model:** Comfy IMAGE tensors provide cache accounting and dependency
  identity. The earlier scalar-field/growth proof remains a separate optional module.
- **Simplest model:** JSON source files compile to ordinary Comfy nodes. No separate
  document server, scheduler, universal geometry type or shader translation layer.
- **Deletion/avoidance:** no second graph executor, homegrown dab rasterizer, custom
  Boolean engine, external studio dependency, or repeated browser launch per edit.
- **Plain-English design:** save intent; let the proper native engine derive each
  result; return evidence to the agent immediately. Browser and MCP use the same edits.

## Editable sources

`examples/painted-bookmark.json` is the executable example. A source has `version: 1`,
pixel `width`/`height`, ordered `parts` with stable ids, and an optional Noisemaker
`processing` program. Part paths are SVG path data with even-odd fill; multiple closed
contours can express holes and disconnected islands. Part color is display-sRGB RGB.
The raster composition currently uses source-over in display-sRGB, with straight RGBA
at operation boundaries. It does not silently apply linear-light compositing.

Parts without `paint` use Skia. Painted parts choose a bundled brush or provide the
full native `preset_json` string. Sparse strokes accept `linear`, `quadratic` (out
handle), `cubic` (out/in handles), or interpolating `auto` splines. Points specify x/y,
diameter `size`, `pressure`, `flow`, `opacity`, `rotation` in degrees and `speed` in
pixels/second. Flow and opacity multiply native dab opacity; native pressure mappings
are retained. Opacity is not a separately isolated post-stroke compositing layer.

### Batch iteration

MCP `batch_edit_art(name, edits, revision)` and Python `Art.batch` target named
parts, authored strokes and control points without replacing their surrounding
arrays. Stroke and point `id` fields are optional; zero-based selectors also work
for existing unnamed sources. `values` merges into the selected object.

```python
art.batch("tide-ornament", [
    {"part": "tidal-ink", "stroke": "crest", "point": "swell",
     "values": {"y": 168, "size": 56}},
    {"part": "tidal-ink", "stroke": "middle", "point": "bend",
     "values": {"y": 264, "size": 32}},
], revision=current["revision"])
```

All edits apply in order to a private document copy before one Comfy submission.
A later invalid target prevents the whole batch from being submitted. A stale
revision or failed render leaves the saved source unchanged. Source publication
remains in the existing edit endpoint; there is no additional transaction manager.
Successful batches return the composed image, comparison, changed-area close-up,
and a compact paint-trajectory overview through MCP. For motion, the close-up
uses the most changed frame. No visible change means no close-up. These are
completed-render receipts, not per-dab streaming previews.

Generated fill trajectories must be baked into `paint.strokes` before individual
editing. Batch editing currently merges existing targets; reusable components,
attachments, transforms, point insertion and removal are separate future work.

Fills generate seeded directional lanes intersected with the region. Size, spacing,
angle, jitter, color variation and clean base coverage are independent controls.
Final coverage clips paint, including overshooting spline/dab edges, to holes and
boundaries. `strokes.json` and `trajectories.png` expose generated marks. To bake them,
set `fill: false` and copy the generated strokes into `paint.strokes`; subsequent
geometry changes then clip those fixed marks rather than regenerating lanes.

Current region filling is a directional hatch strategy, not a claim of contour-aware,
flow-field-guided or physically simulated watercolor filling. Those can be additional
trajectory generators using the same native brush adapter. Paths for fill regions must
not self-intersect. Shapely handles intersections; sampled curves use a 0.5-pixel step.
Raster geometry itself is native Skia. libmypaint currently uses its fixed tiled
surface and 1.x stroke interface: native smudge and presets work, but the newer spectral
paint surface and tilt/barrel controls are not yet exposed.

## Noisemaker boundary

Pinned as a git submodule; source imports run locally with no CDN dependency. Programs
declare native `effects`, `dsl`, `output`, normalized `times`, and `backend`. The
document compiler binds its composed image to `o0`; generator-only documents can
have no parts. The worker transport supports named input surfaces; the current Comfy
node exposes one external RGBA input. Native internal branching and multipass/feedback
remain inside Noisemaker. No effect-by-effect intermediate CPU copies are introduced.

The process keeps Chrome warm, serializes requests, and disposes each renderer after
its program. Cancellation/error kills that owned process tree; the next operation
restarts it. Compilation and browser errors propagate as failed jobs. GPU textures
stay native within the program. Cross-engine exchange is explicit CPU float data,
not zero-copy. Native rgba16float output is expanded to float32 without claiming
float32 arithmetic occurred upstream. Negative/HDR values and alpha are retained;
only display previews are clipped to RGBA8. No silent backend fallback.

Browser automation is infrastructure for the shader engine, not GUI-driven authoring.
Native effects and help are discoverable with `noisemaker_effects`. New shader behavior
should use Noisemaker's native effect workflow; don't duplicate shader operations in
this adapter. Test an effect before claiming support for its particular resources.

## Eyes and exports

Every create/edit renders and returns an observation. MCP embeds the actual images:
main preview, revision comparison, changed paint trajectories, and motion views.
Python/HTTP receive the same receipt and image URLs. Browser previews are supplementary.
Revision preconditions reject stale edits. Failed renders do not replace the saved
current source. Previous sources/results are retained under Comfy `user/agent-art` and
`output/art-*`; source JSON accompanies every result. Revisions can be reopened or
submitted as the next source, without relying on cache contents.

Artifacts: unmodified float `master.npy`, transparent PNG frames, source JSON,
unpainted named `geometry.svg`, coverage NPY/metadata, generated stroke JSON/overlay,
and display-only proof images. Motion emits atlas + row-major decoding JSON and a
lossless animated WebP. Contact sheets select up to twelve labeled frames; originals
remain full-size. Decoding atlas frames is tested against the original exported pixels.

The current Comfy IMAGE path batches a sequence in host memory and the atlas is one
image. This is suitable for sprite-scale sequences, not long/high-resolution video.
A disk-backed sequence artifact node is the next scaling boundary; do not enlarge
this batch path into a video renderer. History retention is explicit and currently
manual; no background deletion of user art. Worker startup requires installed Chrome
and libmypaint; the local plugin does not launch Comfy automatically.

## Evidence

Ten focused tests exercise native repeatability, holes/islands, baking/replay,
interpolation, named edit isolation, atlas decoding, WebGPU/WebGL2 HDR/alpha/orientation,
warm worker reuse, failure, cancellation and recovery. The live API/MCP proof verifies
unchanged-part cache reuse and inline image content. Browser proof changes a paint
control and opens a motion document without page errors.

Measured here at 640×480: approximately 1.2 seconds for a changed paint part plus
Noisemaker and visual proofs; approximately 0.4 seconds for a cached replay with a
new comparison receipt. These are local measurements, not general performance promises.
