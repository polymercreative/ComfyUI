from copy import deepcopy
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image
import pytest

from agent_art_host.creative.geometry import coverage, fill_strokes, sample_stroke
from agent_art_host.creative.paint import paint_region
from agent_art_host.creative.noisemaker import Noisemaker
from agent_art_host.creative.observe import observe
from agent_art_host.creative.project import graph, revise


SHAPE = 'M10 10H115V95H10Z M35 30H75V65H35Z M135 15H155V85H135Z'


def test_native_fill_holes_islands_and_replay():
    style = {"color": [0.2, 0.5, 0.6], "size": 12, "spacing": 6, "seed": 8, "base": 0.6}
    preset = (Path(__file__).parents[1]/'creative/brushes/pencil.myb').read_text(encoding='utf-8')
    first, mask, strokes = paint_region(SHAPE, 173, 107, style, preset)
    second, _, again = paint_region(SHAPE, 173, 107, style, preset)
    np.testing.assert_array_equal(first, second)
    assert strokes == again
    assert first[40:60, 40:70, 3].max() == 0
    assert first[:, 125:130, 3].max() == 0
    assert first[25:75, 140:150, 3].min() >= 0.6
    # Baking generated fill trajectories explicitly gives the same native render.
    baked, _, _ = paint_region(SHAPE, 173, 107, {**style, "fill": False, "strokes": strokes}, preset)
    np.testing.assert_array_equal(first, baked)
    changed, _, _ = paint_region(SHAPE, 173, 107, {**style, "angle": 45}, preset)
    assert np.max(abs(changed-first)) > 0.02


@pytest.mark.parametrize('mode', ['linear', 'auto', 'quadratic', 'cubic'])
def test_sparse_control_points(mode):
    samples = list(sample_stroke({'mode': mode, 'points': [
        {'x': 10, 'y': 20, 'out': [20, 0], 'size': 4, 'rotation': 170},
        {'x': 80, 'y': 50, 'in': [60, 10], 'size': 20, 'rotation': -170}]}))
    assert samples[0][:2] == (10, 20)
    assert samples[-1][:2] == (80, 50)
    assert samples[-1][2]['size'] == 20
    assert samples[-1][2]['rotation'] == 190


def test_named_revision_preserves_other_nodes():
    source = json.loads((Path(__file__).parents[1]/'examples/painted-bookmark.json').read_text())
    before = deepcopy(source)
    changed = revise(source, {'parts': {'fish': {'paint': {'angle': 45}}}})
    old, new = graph(source), graph(changed)
    assert source == before
    assert old['part_ring'] == new['part_ring']
    assert old['part_fish'] != new['part_fish']
    assert old['part_glint'] == new['part_glint']


def test_motion_proofs_and_atlas_roundtrip(tmp_path):
    frames = np.zeros((5, 39, 61, 4), np.float32)
    for i in range(5):
        frames[i, 5:20, 4+i*5:15+i*5] = [0.2, 0.5, 0.8, 1]
    visible = observe(frames, tmp_path, '{}', {'times': [0, .2, .4, .6, .8]}, frames*.8)
    assert {'revision.png', 'contact-sheet.png', 'onion.png', 'motion.png'} <= set(visible)
    np.testing.assert_array_equal(np.load(tmp_path/'master.npy'), frames)
    atlas = np.asarray(Image.open(tmp_path/'atlas.png'))
    for i, frame in enumerate(frames):
        x, y = (i%4)*61, (i//4)*39
        np.testing.assert_array_equal(atlas[y:y+39, x:x+61], np.round(frame*255).astype(np.uint8))
    assert np.asarray(Image.open(tmp_path/'motion.png'))[..., 0].max() > 0


@pytest.fixture
def renderer():
    instance = Noisemaker()
    yield instance
    instance.close()


def job(tmp_path, backend='webgpu'):
    values = np.zeros((61, 97, 4), np.float32)
    values[..., 0] = np.linspace(-0.5, 2, 97)
    values[..., 1] = np.linspace(0, 1, 61)[:, None]
    values[..., 2] = 0.314159
    values[..., 3] = np.linspace(0.1, 0.9, 97)
    path = tmp_path/'input.npy'
    np.save(path, values)
    return values, {'width': 97, 'height': 61, 'inputs': {'o0': str(path)}, 'directory': str(tmp_path),
        'effects': [], 'dsl': 'search synth\nread(o0).write(o1)\nrender(o1)', 'output': 'o1', 'times': [0], 'backend': backend}


@pytest.mark.parametrize('backend', ['webgpu', 'webgl2'])
def test_float_native_boundary(renderer, tmp_path, backend):
    values, request = job(tmp_path, backend)
    receipt = renderer.run(request)
    assert receipt['backend'] == backend
    result = np.load(tmp_path/'frame-0000.npy')
    np.testing.assert_allclose(result, values, atol=.001)
    pid = renderer.process.pid
    renderer.run(request)
    assert renderer.process.pid == pid


def test_failure_cancel_and_restart(renderer, tmp_path):
    values, request = job(tmp_path)
    renderer.run(request)
    with pytest.raises(RuntimeError, match='Unknown effect'):
        renderer.run({**request, 'dsl': 'search filter\nread(o0).missingArtEffect().write(o1)\nrender(o1)'})
    assert renderer.process is None
    renderer.run(request)
    class Cancelled(Exception):
        pass
    start = time.monotonic()
    def cancel():
        if time.monotonic()-start > .25:
            raise Cancelled()
    with pytest.raises(Cancelled):
        renderer.run({**request, 'times': [0]*10000}, check=cancel)
    assert renderer.process is None
    renderer.run(request)
    np.testing.assert_allclose(np.load(tmp_path/'frame-0000.npy'), values, atol=.001)
def test_curved_region_shared_endpoints():
    from agent_art_host.creative.geometry import region
    from agent_art_host.examples.make_showcase import herb
    for part in herb()['parts']:
        if 'paint' in part:
            assert region(part['path']).is_valid
