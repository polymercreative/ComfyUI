# Agent Art host

Start with the [design](DESIGN.md): product goals, shared art surface, module
boundaries, integration rules and production acceptance criteria.

Working branch: `agent-art`. Upstream baseline: `b0f4b7b294ce482a2e071d9d762c133d38c7aa07`.
Keep `upstream` pointing to Comfy-Org/ComfyUI and merge upstream changes here.
The existing Agent Art package remains independently callable; this extension
calls its operations directly, without nesting its recipe executor inside Comfy.

## Local setup

From this repository, with the Agent Art repository alongside it:

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
uv pip install --python .venv/Scripts/python.exe -r requirements.txt -e ../AgentArt
git submodule update --init agent_art_host/vendor/noisemaker
uv pip install --python .venv/Scripts/python.exe -r agent_art_host/requirements-creative.txt
./agent_art_host/start.ps1
```

Agent Art is currently a local development dependency, not a published package.
The remote fork alone therefore does not contain everything needed for this extension.
This uses CPU PyTorch and requires no model files. Noisemaker runs its own native
GPU backend in an installed Chrome browser. Painting requires libmypaint; on Windows
the adapter can use Krita's installed DLL, or set `AGENT_ART_MYPAINT` to the shared
library path. The launcher binds localhost:8794,
disables cloud API nodes and loads only this custom-node package.

## API proof

In another terminal:

```powershell
./.venv/Scripts/python.exe agent_art_host/prove.py
```

The saved API-format workflow can be submitted directly to `/prompt`. It passes
a mask into an immutable Agent Art field, runs the existing CPU growth reference,
and exports an unnormalized float NPY plus semantic metadata and a separate PNG
preview. The proof changes speed, verifies cache reuse/invalidation and checks
every pixel against an independent analytic result. It also checks invalid seeds
produce an execution error. Reports and generated assets live in ignored `output/`.

The 4-neighbor growth solver remains Manhattan-biased. SDF authoring is not yet
integrated. The new creative path is described below.

## Creative iteration

See the [working examples and ergonomics](examples/README.md), or use the browser's
Examples picker for painted foliage, a layered lantern, spline strokes and GPU motion.

### Official Comfy CLI

The official `comfy-cli` can validate and execute these same nodes. Install it in
its own environment; interactive browser/MCP edits use the local Comfy server API
directly to avoid an extra process per edit. Both paths use Comfy's scheduler and cache.

```powershell
uv tool install --python 3.12 comfy-cli
$env:COMFY_NO_TELEMETRY='1'
$env:DO_NOT_TRACK='1'
$env:COMFY_LOCAL_URL='http://127.0.0.1:8794'
./.venv/Scripts/python.exe -m agent_art_host.creative.project agent_art_host/examples/painted-bookmark.json output/creative-api.json
comfy --json workflow validate --workflow output/creative-api.json --where local
comfy --json run --workflow output/creative-api.json --where local --wait --no-notify
```

Verified with official CLI 1.20.0: no validation errors or warnings, successful
execution of the native paint/vector/Noisemaker graph, and local image artifacts.
Use `comfy --json discover` for its workflow, job and artifact-management commands.

### Edit and inspect

Open `http://127.0.0.1:8794/agent-art`. The example is authored geometry, native
libmypaint fills and a Noisemaker watercolor program; no generated bitmap is used.
The editor saves source revisions, per-part output, SVG geometry, native float
masters, coverage maps and paint trajectories. Change a named part without
invalidating other part renders. The browser supports source editing, paint controls,
revision comparisons and motion proofing; it is an inspection surface, not a layout engine.

The Python client uses the same endpoint:

```python
from agent_art_host.creative.client import Art
art = Art()
current = art.open('painted-bookmark')
result = art.edit('painted-bookmark', {
    'parts': {'fish': {'paint': {'angle': 25, 'variation': 0.12}}}
}, revision=current['revision'])
```

For agents, use the MCP entrypoint: its create/edit/open tools return **inline images**,
not just filenames. Animated results automatically include a contact sheet, onion
skin and frame-difference image. No separate observation tool call is needed.

```powershell
./.venv/Scripts/python.exe -m agent_art_host.creative.mcp_server
```

Run from the repository, or put this repository on `PYTHONPATH` in the MCP server
configuration. The local `agent-art` Codex plugin points to this entrypoint.
`capabilities`, `example_art` and `noisemaker_effects` provide discovery and native
effect parameter documentation. [Creative contracts](CREATIVE.md) describe sources,
backend boundaries, practical limitations and exports.

```powershell
./.venv/Scripts/python.exe -m pytest agent_art_host/tests/test_creative.py -q
./.venv/Scripts/python.exe -m agent_art_host.tests.prove_edit_loop
./.venv/Scripts/python.exe -m agent_art_host.tests.prove_browser
```

The latter two require the running host. They exercise real Comfy jobs, targeted
cache reuse, technical exports, actual MCP image content and browser editing.

See [Execution and intermediate-state map](EXECUTION.md) for inspected source
owners, integration boundaries and measured evidence. `requirements-tested.txt`
records the resolved Windows CPU environment, excluding the editable Agent Art
dependency; use the CPU wheel index when restoring its Torch packages.
