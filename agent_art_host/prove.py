"""Exercise the real Comfy API, typed fields, parameter revisions and cached reuse."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import time
from urllib.request import Request, urlopen

import numpy as np


def api(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as response:
        return json.load(response)


def run(base, graph):
    queued = api(base, "/prompt", {"prompt": graph})
    prompt_id = queued["prompt_id"]
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        history = api(base, "/history/" + prompt_id)
        if prompt_id in history:
            return prompt_id, history[prompt_id]
        time.sleep(0.1)
    raise TimeoutError(f"Execution {prompt_id} did not finish in 60 seconds")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8794")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    graph = json.loads((Path(__file__).parent / "workflows/growth.json").read_text())
    for node in ("AgentArtMaskField", "AgentArtGrowthCPU", "AgentArtInspectField"):
        assert node in api(args.url, "/object_info/" + node), node
    evidence = []
    y, x = np.mgrid[:61, :97]
    for speed in (1.0, 1.0, 2.0):
        revision = deepcopy(graph)
        revision["growth"]["inputs"]["speed"] = speed
        prompt_id, result = run(args.url, revision)
        assert result["status"]["status_str"] == "success", result["status"]
        metadata = json.loads(result["outputs"]["inspect"]["text"][0])
        (root / "output" / metadata["subfolder"] / "workflow.json").write_text(
            json.dumps(revision, indent=2), encoding="utf-8")
        raw = np.load(root / "output" / metadata["subfolder"] / "field.npy", allow_pickle=False)
        np.testing.assert_array_equal(raw[:, :, 0], (abs(x - 48) + abs(y - 30)) / speed)
        assert raw.dtype == np.float32 and raw.shape == (61, 97, 1)
        assert metadata["color_space"] == "data" and metadata["alpha"] == "none"
        assert metadata["max"] == 78 / speed
        cached = [node for event, data in result["status"]["messages"]
                  if event == "execution_cached" for node in data["nodes"]]
        evidence.append({"prompt_id": prompt_id, "speed": speed, "cached": cached,
                         "output": metadata["subfolder"]})
    assert "growth" in evidence[1]["cached"], evidence
    assert "field" in evidence[2]["cached"] and "growth" not in evidence[2]["cached"], evidence
    invalid = deepcopy(graph)
    invalid["growth"]["inputs"]["seeds"] = "[[999,30]]"
    _, failure = run(args.url, invalid)
    assert failure["status"]["status_str"] == "error", failure
    _, recovered = run(args.url, graph)
    assert recovered["status"]["status_str"] == "success", recovered
    report = {"runs": evidence, "invalid_seed_rejected": True,
              "recovered_after_failure": True,
              "checks": "API discovery, typed fields, raw float preservation, numerical oracle, cached replay, targeted invalidation"}
    path = root / "output" / "agent-art-proof.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
