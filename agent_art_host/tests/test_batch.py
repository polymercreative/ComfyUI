from copy import deepcopy
import json

import numpy as np
from PIL import Image
import pytest

from agent_art_host.creative.project import batch_revise
from agent_art_host.creative.observe import observe
from agent_art_host.examples.make_showcase import waves


def test_ordered_named_batch_preserves_source_and_other_strokes():
    source=waves()
    before=deepcopy(source)
    edited=batch_revise(source,[
        {'part':'tidal-ink','stroke':'crest','point':'swell','values':{'y':140}},
        {'part':'tidal-ink','stroke':'crest','point':'swell','values':{'size':60}},
        {'part':'tidal-ink','stroke':'crest','point':'swell','values':{'y':155}},
    ])
    assert source==before
    stroke=edited['parts'][0]['paint']['strokes'][0]
    assert stroke['points'][1]['y']==155 and stroke['points'][1]['size']==60
    assert stroke['points'][0]==before['parts'][0]['paint']['strokes'][0]['points'][0]
    assert edited['parts'][0]['paint']['strokes'][1:]==before['parts'][0]['paint']['strokes'][1:]
    assert edited['parts'][1]==before['parts'][1]


def test_late_bad_target_does_not_partially_mutate():
    source=waves()
    before=deepcopy(source)
    with pytest.raises(ValueError,match='Edit 2:'):
        batch_revise(source,[{'part':'tidal-ink','values':{'color':[1,0,0]}},
                            {'part':'tidal-ink','stroke':'missing','values':{'mode':'linear'}}])
    assert source==before
    with pytest.raises(ValueError,match='point target needs a stroke'):
        batch_revise(source,[{'part':'tidal-ink','point':0,'values':{'x':1}}])


def test_unnamed_points_support_explicit_index():
    result=batch_revise(waves(),[{'part':'tidal-ink','stroke':0,'point':1,'values':{'pressure':.6}}])
    assert result['parts'][0]['paint']['strokes'][0]['points'][1]['pressure']==.6


def test_closeup_detects_later_frame_change_and_skips_identical(tmp_path):
    before=np.zeros((3,100,150,4),np.float32)
    after=before.copy()
    after[2,40:50,65:75]=[.2,.5,.6,1]
    visible=observe(after,tmp_path/'changed','{}',{'times':[0,.3,.6]},before)
    assert 'changed-area.png' in visible
    proof=Image.open(tmp_path/'changed/changed-area.png')
    assert proof.width>=360 and proof.height<200
    # The changed-frame crop, rather than the unchanged first frame, is shown.
    pixels=np.asarray(proof)
    assert not np.array_equal(pixels[48:,:proof.width//2],pixels[48:,proof.width//2:])
    visible=observe(after,tmp_path/'same','{}',{'times':[0,.3,.6]},after)
    assert 'changed-area.png' not in visible
