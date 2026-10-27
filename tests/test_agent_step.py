"""CPU contract regressions, including production stationary verifier; not physical proof."""
import io

import pytest
from test_agent_domain import FixtureGateway, make_domain
from microduck_workshop.agent.runner import build_agent
from microduck_workshop.sim.evaluate import MotionVerifier
from microduck_workshop.sim.intent import IntentOwner
from cascade.agent.llm import LLMClient, LLMResponse, ToolCall


class StationaryGateway(FixtureGateway):
    # Exercise live receipt branching, explicitly NOT a real ROS/physics adapter.
    synthetic = False

    def __init__(self):
        super().__init__()
        self.now = 0.
        self.owner = IntentOwner('episode-1', clock=lambda: self.now)
        self.token = self.owner.claim('fixture')['lease_token']
        self.obs['generation'] = 0
        self.verifier = MotionVerifier(self.owner, io.StringIO())

    def bounded_motion(self, command, **kwargs):
        self.sent.append(command)
        ack = self.owner.submit(command, self.token)
        truth = dict(root_pose=[0, 0, .12, 0, 0, 0, 1], root_velocity=[0] * 6)
        for tick in range(151):
            self.now = tick * .02
            self.owner.renew('episode-1', self.token)
            self.verifier.begin_tick(self.now, truth)
            self.owner.consume(sim_time=self.now)
            self.verifier.end_tick(self.now, truth)
        return ack

    def motion_status(self, episode_id, request_id):
        return self.owner.status(request_id)


def test_verified_stationary_legacy_command_cannot_complete_forward_objective(tmp_path):
    gateway = StationaryGateway()
    agent, runtime = build_agent(None, gateway, tmp_path, episode_id='episode-1',
                                 frame_id='microduck_camera_optical')
    domain = runtime.domains['microduck']
    try:
        domain.execute('observe', {})
        receipt = domain.walk_bounded(dict(vx=0., vy=0., wz=0., duration_s=.5))
        assert receipt['verified'] is True  # production zero/rest evaluator is legitimate
        assert runtime.execute('task_done', dict(success=True, summary='walked'))['success'] is False
    finally:
        runtime.close()


def test_orchestrator_cannot_dispatch_unadvertised_zero_walk(tmp_path):
    class ZeroWalkModel(LLMClient):
        """Deterministic model fixture, NOT real model evidence."""
        def __init__(self):
            self.index = 0

        def chat(self, system, messages, tools=None, max_tokens=1024):
            calls = [
                ToolCall('microduck.observe', {}, 'observe'),
                ToolCall('microduck.walk_bounded',
                         dict(vx=0., vy=0., wz=0., duration_s=.5), 'zero'),
                ToolCall('microduck.verify', {}, 'verify'),
                ToolCall('task_done', dict(success=True, summary='false walk claim'), 'done'),
            ]
            response = LLMResponse(tool_calls=[calls[self.index]])
            self.index += 1
            return response

    gateway = StationaryGateway()
    agent, runtime = build_agent(ZeroWalkModel(), gateway, tmp_path,
                                 episode_id='episode-1', frame_id='microduck_camera_optical',
                                 max_steps=4)
    try:
        assert agent.run_task('Observe GO, step forward, verify.').success is False
        assert not gateway.sent
        assert not runtime.domains['microduck'].forward_step_confirmed
    finally:
        runtime.close()


def test_catalog_only_exposes_fixed_step():
    domain = make_domain()
    specs = {s['name']: s for s in domain.tool_specs}
    assert 'microduck.walk_bounded' not in specs
    schema = specs['microduck.step_forward']['parameters']
    assert schema['properties'] == {'action': {'type': 'string', 'enum': ['step_forward']}}
    assert schema['required'] == [] and schema['additionalProperties'] is False


@pytest.mark.parametrize('args', [{}, {'action': 'step_forward'}])
def test_fixed_step_constructs_independent_objective(args):
    gateway = FixtureGateway()
    gateway.synthetic = False  # CPU receipt contract only
    gateway.step_forward = gateway.bounded_motion
    original = gateway.motion_status
    gateway.motion_status = lambda *a: dict(original(*a), verified=True)
    domain = make_domain(gateway)
    domain.execute('observe', {})
    assert domain.execute('step_forward', args)['verified'] is True
    cmd = gateway.sent[0]
    assert (cmd.vx, cmd.vy, cmd.wz, cmd.duration_s) == (.1, 0., 0., 2.)
    assert domain.forward_step_confirmed is True
    domain.begin_task()
    assert domain.forward_step_confirmed is False


@pytest.mark.parametrize('args', [{'vx': 0}, {'action': 'walk_bounded'}, {'duration_s': .5}])
def test_step_rejects_numeric_choices(args):
    gateway = FixtureGateway()
    domain = make_domain(gateway)
    domain.execute('observe', {})
    assert domain.execute('step_forward', args)['ok'] is False
    assert not gateway.sent


def test_rejected_step_cannot_be_promoted_by_a_stray_verified_status():
    gateway = FixtureGateway()
    gateway.synthetic = False  # CPU receipt contract only
    original = gateway.bounded_motion
    gateway.bounded_motion = lambda *a, **kw: dict(original(*a, **kw), accepted=False)
    original_status = gateway.motion_status
    gateway.motion_status = lambda *a: dict(original_status(*a), verified=True)
    domain = make_domain(gateway)
    domain.execute('observe', {})
    assert domain.execute('step_forward', {})['accepted'] is False
    domain.verify()
    assert not domain.forward_step_confirmed


@pytest.mark.parametrize('vx,wz', [(0., 0.), (1e-12, 0.), (0., .1), (.1, 0.)])
def test_legacy_receipt_never_proves_named_step(vx, wz):
    gateway = FixtureGateway()
    gateway.synthetic = False
    original = gateway.motion_status
    gateway.motion_status = lambda *a: dict(original(*a), verified=True)
    domain = make_domain(gateway)
    domain.execute('observe', {})
    assert domain.walk_bounded(dict(vx=vx, vy=0., wz=wz, duration_s=2.))['verified']
    assert not domain.forward_step_confirmed
