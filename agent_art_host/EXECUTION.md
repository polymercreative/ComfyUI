# Execution and intermediate-state map

Inspected baseline: b0f4b7b294ce482a2e071d9d762c133d38c7aa07 (ComfyUI 0.37.0).
This separates source findings from locally exercised behavior. Do not infer
backend compatibility from the existence of a custom-node API.

## Existing owners to reuse

| Concern | Source owner | Consequence for Agent Art |
|---|---|---|
| Discovery and validation | `server.py`, `validate_prompt` / `validate_inputs` in `execution.py` | Reuse object schemas and submission validation. Do not build a second node registry. |
| Jobs, queue, history, targeted cancellation | `PromptQueue`, `comfy_execution/jobs.py`, server job routes | Submit existing jobs; map authored revision IDs at our client boundary. |
| Dependencies, lazy inputs, ephemeral subgraphs | `comfy_execution/graph.py`, `graph_utils.py`, executor pending subgraphs | Use native links/expansion and selected output targets; don't embed our old executor. |
| Async node execution | `_async_map_node_over_list`, pending async nodes and external blocks | Native async operations are supported. A blocking subprocess call still blocks its execution context. |
| Intermediate values | `CacheEntry`, `CacheSet`, `comfy_execution/caching.py` | Native outputs can carry our typed fields. Treat cached values as read-only. |
| Invalidation | `CacheKeySetInputSignature`, `IsChangedCache` | Keys incorporate inputs/ancestry and node fingerprints. External file/preset/shader changes need explicit identity or fingerprinting. |
| External cache | `comfy_api/latest/_caching.py`, `comfy_execution/cache_provider.py` | Existing async lookup/store and prompt lifecycle hooks; no new disk-cache service yet. |
| Resource pressure | `RAMPressureCache`, `comfy.memory_management`, model management | Reuse where the resource representation is recognized. Foreign GPU contexts are not automatically managed. |
| Inspection | output UI payloads, progress, history, `app/assets` registration | Return previews and artifact metadata through existing execution results. |

## Important semantics observed in source

- Input signatures follow graph ancestry. A mutable canvas, changed file or
  different brush binary hidden behind unchanged inputs is not automatically a
  new revision. Source revisions and resource content identities must be explicit.
- Output values are cached as objects, not automatically copied snapshots.
  Mutating a shared field could change another branch's input. A stateful operation
  should produce a new state/artifact; persistent native workers may accelerate
  evaluation but must not become the only record of the document.
- Local caching, external persistence, output artifacts and job history are
  different lifetimes. A cached file reference does not guarantee the file still
  exists. Artifact retention and export side effects need explicit policies.
- External cache lookup occurs on local miss. Stores use asynchronous tasks;
  provider failures are logged rather than made execution failures. Treat these
  providers as optional acceleration, not the authoritative document save path.
- RAM-pressure sizing recognizes CPU Torch tensors, nested containers and a
  `_comfy_cache_tensors` hook. A custom Field wrapping NumPy or a foreign GPU handle
  does not automatically receive accurate accounting. Our small CPU proof does
  not establish large-art memory behavior. Avoid permanent global native handles.
- An interrupt check occurs before node calls. That does not preempt an arbitrary
  running Python loop, child process or GPU dispatch. Long operations must cooperate;
  process termination and native-job cleanup belong in their adapters.
- The executor handles node errors and reports them; prompt cleanup has a finally
  path. Its model unloading cannot reclaim unrelated browser/GPU resources.
  Adapter-owned resources need explicit cleanup on success, error and cancellation.
- Partial output targets and generated subgraphs already exist. Their validity,
  stable node identities and cache behavior should be retained rather than replaced
  with a generic orchestration abstraction.

## Integration shapes to prove next

| Backend | Smallest useful boundary | Specific proof needed |
|---|---|---|
| Pillow / NumPy library | In-process operation returning declared artwork/fields | Color/alpha preservation, immutable inputs, changed-region inspection |
| ImageMagick / other CLI | Node launching an explicit executable with argument arrays and owned temporary artifacts | Exit handling, stderr diagnostics, cancellation, cleanup and precision round-trip |
| Noisemaker | Native graph operation executed by its headless worker | Float readback, feedback reset/reuse, graph/resource fingerprints, cancellation and context cleanup |
| Custom compute engine | Native dispatch operation with declared fields or owned resource references | Synchronization, readback, numerical oracle, memory accounting and release |
| libmypaint | Authored spline/brush instructions plus explicit prior paint state | Replay, edits before dependent smudge strokes, preset identity, native surface lifetime |

Keep a whole native multi-pass chain inside its engine when it avoids readbacks.
Expose useful boundaries for branching/inspection. Passing one native texture handle
between engines is not a promise of interoperable or zero-copy GPU memory.

## Local evidence

- Real API workflow: 97x61 mask -> custom Field -> existing CPU growth -> float
  master + metadata + PNG inspection. No model checkpoint or SDF dependency.
- Per-pixel analytic oracle, raw float32/range/shape/semantics preservation.
- Identical workflow reused growth; changing speed retained the source mask/field
  and invalidated growth and inspection. Expected invalid seeds failed clearly.
- Upstream focused tests: **68 passed** across external cache-provider behavior,
  execution-list behavior and job-cancellation classification/dispatch.
- Tests require `comfy.cli_args.args.cpu = True` before graph imports with this
  CPU Torch environment. The first ordinary pytest attempt failed during collection
  because it attempted CUDA initialization; the CPU-configured run passed.

Run the focused tests from the repository root:

```powershell
./.venv/Scripts/python.exe -c "from comfy.cli_args import args; args.cpu = True; import pytest; raise SystemExit(pytest.main(['tests-unit/execution_test/test_cache_provider.py', 'tests-unit/execution_test/test_execution_list.py', 'tests-unit/jobs_cancel_test/jobs_cancel_test.py', '-q']))"
```

Still unverified: native process cancellation, GPU cleanup, persistent worker
recovery, cross-session custom-field caching, brush-state replay, large allocations
and Noisemaker execution. These require actual backend fixtures, not more wrappers.
