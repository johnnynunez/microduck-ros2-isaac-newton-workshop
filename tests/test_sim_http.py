"""Real loopback HTTP protocol tests with labeled CPU-only source snapshots."""

import json
import urllib.error
import urllib.request


def test_http_priority_stop_and_not_ready_camera():
    from microduck_workshop.sim.http import SnapshotStore, serve
    from microduck_workshop.sim.intent import IntentOwner

    owner = IntentOwner("ep1")
    store = SnapshotStore(owner, runtime={"evidence_kind": "CPU_UNIT_TEST"})
    with serve(store, port=0) as server:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        health = json.load(urllib.request.urlopen(url + "/v1/health"))
        assert health["ready"] is False
        try:
            urllib.request.urlopen(url + "/v1/camera")
        except urllib.error.HTTPError as err:
            assert err.code == 503
        else:
            raise AssertionError("no camera frame exists")
        req = urllib.request.Request(
            url + "/v1/stop",
            method="POST",
            data=b'{"episode_id":"ep1","latch":true}',
            headers={"Content-Type": "application/json"},
        )
        assert json.load(urllib.request.urlopen(req))["stop_latched"]
        assert owner.consume(sim_time=0) == (0, 0, 0)
