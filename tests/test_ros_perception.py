"""CPU capture provenance fixtures; no synthetic detector acceptance."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'ros_ws/src/microduck_gateway'))
from microduck_gateway.perception import CaptureCache


def test_original_capture_age_not_arrival_time():
    cache = CaptureCache(clock=lambda: 10.)
    cache.record('ep', 2, 1.25, 9.4, 'camera')
    assert not cache.detect(1.25, 'camera', [0])
    assert not cache.observe('ep', 7)['fresh']
    cache.record('ep', 3, 1.5, 9.9, 'camera')
    assert cache.detect(1.5, 'camera', [0])
    result = cache.observe('ep', 7)
    assert result['fresh'] and result['tag_ids'] == [0]
    assert result['frame_sequence'] == 3
    assert abs(result['age_s'] - .1) < 1e-6
    assert not cache.detect(1.5, 'wrong', [0])
    assert not cache.detect(99., 'camera', [0])
    assert not cache.observe('old', 7)['fresh']


def test_rewind_epoch_and_stopped_camera_clear_freshness():
    now = [10.]
    cache = CaptureCache(clock=lambda: now[0])
    cache.record('a', 1, 5., 10., 'camera')
    assert cache.detect(5., 'camera', [0])
    now[0] = 10.6
    assert not cache.observe('a', 0)['fresh']
    cache.record('b', 1, 0., 10.6, 'camera')
    assert not cache.detect(5., 'camera', [0])
    assert not cache.observe('b', 0)['fresh']


def test_out_of_order_detection_cannot_restore_an_old_go_signal():
    cache = CaptureCache(clock=lambda: 10.)
    cache.record('ep', 1, 1., 9.8, 'camera')
    cache.record('ep', 2, 2., 9.9, 'camera')
    assert cache.detect(2., 'camera', [1])
    assert not cache.detect(1., 'camera', [0])
    assert cache.observe('ep', 0)['tag_ids'] == [1]
