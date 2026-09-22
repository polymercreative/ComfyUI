# Agent Art — design

## Goal

Build an agent-first creative toolkit with ComfyUI-style composability, capable of
producing editable, production-useful art and technical data. Agents must be free
to create from scratch, reconstruct a reference, paint over an image, process it
algorithmically, or combine those approaches in any order.

New technical-art ideas should become reusable operations or recipes here within
minutes when a working library, shader or CLI already exists. Avoid bespoke Blender
or Unity scaffolding for each experiment. Integration speed, iteration quality and
usable exports are product requirements. A successful command or attractive demo
alone does not establish a useful tool.

This is the governing design. Detailed research and execution notes support it;
they do not restrict the product to the current prototype.

## How it fits together

**Agent commands -> editable sources and recipes -> ComfyUI execution -> native
art engines -> inspectable results -> revisions or exports.**

- **Agent interface:** discover capabilities and examples; create, connect and
  revise operations; inspect results; compare alternatives; save reusable recipes.
  Python/CLI and eventual MCP share the same operations. GUI manipulation is optional.
- **Shared art surface:** named parts, layers, paths, regions, references and fields
  agree on coordinates, transforms and meaning. Each retains its native representation
  and resolution. The surface is not one flattened bitmap or one universal data type.
- **ComfyUI:** owns workflow scheduling, dependencies, intermediate caching, job
  reporting and existing execution infrastructure. Extend it before duplicating it.
- **Backends:** existing libraries, executables, shader engines and simulations own
  their algorithms and native resources. Keep native multipass work together where
  useful. No universal shader translation or mandatory GPU API.
- **Browser:** visual inspection, comparisons, overlays and progress. Agents must
  see the actual marks and intermediate results they are creating.

Editable persistence is required; a separate document service is not prescribed.
Choose storage through real editing tasks. Shared meaning is mandatory; shared
implementation is not. Each new abstraction must make the next integration easier.

## Cooperating, optional modules

| Module | Responsibility |
|---|---|
| Vector drawing | Direct agent-authored geometry, curves, fills, strokes and Boolean operations; editable named shapes. |
| Painting | Native brushes driven by simple spline points with interpolated size, flow, opacity, rotation and timing. Algorithmic region fills mix clean coverage with irregular brush passes; agents specify style and area rather than manually placing every fill stroke. |
| SDF tools | Shape generation, composition, rasterization, raster/vector conversion, smoothing and distance exports. SDFs can be intermediate material or the final product; they are never mandatory. |
| Image processing | Filters, stylization, algorithmic painting, quantization, Kuwahara/MLV variants, bevels and surface treatments. Reuse research and established implementations. |
| Technical-art recipes | Reusable compositions for maps, growth, flow, UVs, simulation, PBR/NPR textures, sequences, packing/unpacking, atlases and decoder metadata. Growth/reveal is one recipe among many. |

Modules share geometry, regions, masks, fields and inspection. A region can guide
a fill, clip a filter or become an SDF. A direction field can guide paint, distortion
or animation. Conversions are explicit operations, not a prescribed pipeline.
Raster-to-SDF may be direct or pass through traced/smoothed vectors. Preserve sources
and disclose approximation; not every conversion is reversible.

Recipes are shared infrastructure, not a second executor. They may branch, compose
subrecipes and produce multiple artifacts. The MOV-to-PNG workflow should be expressible
through reusable decoding, extraction, conversion and packaging steps. Rive and game
engines consume exports; UI layout and gameplay systems remain outside this toolkit.

## Integration and editing rules

1. Research existing solutions first. Keep backend-specific capabilities accessible;
   avoid reducing powerful tools to a lowest-common-denominator interface.
2. A normal integration supplies an operation schema, native invocation, declared
   inputs/outputs, dependency/version information and an executable example. It should
   not require changing the document model, scheduler or unrelated modules.
3. Separate editable intent from derived results. Preserve curves, brush presets,
   dynamics, recipes and seeds. Generated fill strokes remain inspectable; explicitly
   bake them into editable strokes when needed. Revisions preserve unrelated work.
4. Use ComfyUI's state infrastructure deliberately. Fingerprint relevant parts and
   external resources, rather than invalidating everything on a whole-document revision.
   Treat cached outputs as read-only. Painting/simulation checkpoints are derived
   state, not substitutes for saved sources. Replay only affected dependencies.
5. Adapters own native cleanup, cancellation cooperation and process failure handling.
   GPU residency, memory accounting and cross-engine transfers require explicit proofs.
6. Preserve technical meaning: units, precision, channels, color space, alpha and
   transforms. Never silently normalize, resize, gamma-correct or premultiply data.
   Packing/atlas recipes include registration and decode contracts.
7. Visual evidence is part of completing a useful edit, not an optional debugging
   step. Return full results, intended-size crops and relevant diagnostics. Save
   variants and support returning to prior revisions.

## What earns production readiness

- Create a useful asset from scratch, revise a named part and export it successfully.
- Paint expressive spline strokes and varied region fills, including holes, narrow
  areas and disconnected regions; retain predictable controls and editability.
- Combine different engines in a saved recipe, rerun it, and recompute only affected work.
- Produce technical maps and an atlas whose decoded values and placement match the sources.
- Integrate an unfamiliar working tool without core changes; measure time to first
  useful result. Investigate recurring friction that prevents minutes-scale integration.
- Exercise failure, cancellation, replay and realistic asset sizes. Numerical checks
  establish correctness; visual review establishes artistic usefulness.

## Current evidence and open decisions

Next milestone: one useful asset with a named region containing a hole, an algorithmic
painted fill and a native processing stage. Revise the region and a style parameter,
preserve unrelated work, inspect the regenerated marks, and export artwork plus a
technical channel with checked decoding. Exercise cancellation and restart on that
same workflow. This tests missing capabilities rather than re-proving the executor;
it does not mandate this sequence for other projects.

Verified: the fork runs API-driven custom fields, CPU growth and float exports;
cache reuse, targeted invalidation and failure recovery pass. There are 68 passing
focused upstream tests. See [execution evidence](EXECUTION.md) and [setup](README.md).

The first connected creative path now runs named SVG regions through native libmypaint
and Noisemaker, with cached edits, inline MCP observations and motion proof exports.
See [creative contracts and evidence](CREATIVE.md) for verified scope and limitations.
Still to prove: richer fill strategies, large streaming sequences, SDF conversions,
broader native-resource support and production packaging. Resolve remaining storage
and resource policies through real cross-module tasks.
