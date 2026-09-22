# Agent Art host

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
./agent_art_host/start.ps1
```

Agent Art is currently a local development dependency, not a published package.
The remote fork alone therefore does not contain everything needed for this extension.
This proof uses CPU PyTorch and requires no model files. Noisemaker/native GPU
backends are separate future integrations. The launcher binds localhost:8794,
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

This establishes the host boundary only. It does not yet provide art documents,
spline painting, SDF tooling, shader integrations or production growth quality.
The 4-neighbor solver remains Manhattan-biased. Next integration: a named editable
path driving native brushes, with explicit revisions and inspectable results.

See [Execution and intermediate-state map](EXECUTION.md) for inspected source
owners, integration boundaries and measured evidence. `requirements-tested.txt`
records the resolved Windows CPU environment, excluding the editable Agent Art
dependency; use the CPU wheel index when restoring its Torch packages.
