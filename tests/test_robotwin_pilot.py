import copy
import json
import unittest
from unittest.mock import patch

from agent_vla.evaluation.pilot import PilotSettings, make_plan, summarize, validate_plan
from agent_vla.robotwin.contracts import CAMERAS, Observation, interpolate, validate_decision
from agent_vla.robotwin.supervisor import Supervisor, request_payload, ProviderError
from agent_vla.robotwin.episode import run_trial
from agent_vla.robotwin.skills import compile_skill


def observation(sequence=120, missing=None):
    return Observation(sequence, {c: None if c == missing else b'\x89PNG\r\n\x1a\nimage'
                                  for c in CAMERAS}, (0.,)*14, (0.,)*12,
                       {s: (0., 0., 0., 1., 0., 0., 0.) for s in ('left', 'right')},
                       'evaluator-only-reset-fingerprint')


def decision(kind='pass', **extra):
    return dict(sequence=120, kind=kind, reason='Visible evidence',
                evidence=[{'camera': 'head_camera', 'detail': 'Mug visible'}], **extra)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.settings = PilotSettings()
        self.plan = make_plan(self.settings, {'revision': 'frozen'}, {'model': 'frozen'})

    def test_allocation_and_roundtrip(self):
        self.assertEqual(len(self.plan['trials']), 40)
        self.assertEqual(validate_plan(json.loads(json.dumps(self.plan))), self.settings)
        for seed in self.settings.seeds:
            self.assertEqual(len([t for t in self.plan['trials'] if t['seed'] == seed]), 4)

    def test_changed_plan_rejected(self):
        self.plan['settings']['action_horizon'] += 1
        with self.assertRaises(ValueError): validate_plan(self.plan)

    def test_infrastructure_not_robot_failure(self):
        trial = self.plan['trials'][0]
        row = dict(trial, plan_sha256=self.plan['plan_sha256'], status='invalid', actions=2)
        report = summarize(self.plan, [row])
        group = report['conditions']['baseline']
        self.assertEqual((group['invalid'], group['missing'], group['completed']), (1, 9, 0))
        self.assertIsNone(group['observed_success_rate'])
        self.assertFalse(report['complete_matched_pilot'])

    def test_matching_requires_observed_resets(self):
        rows = [dict(t, plan_sha256=self.plan['plan_sha256'], status='completed',
                     success=False, initial_fingerprint=str(t['seed']), actions=1200)
                for t in self.plan['trials']]
        self.assertTrue(summarize(self.plan, rows)['complete_matched_pilot'])
        rows[0]['initial_fingerprint'] = 'different'
        self.assertFalse(summarize(self.plan, rows)['complete_matched_pilot'])
        with self.assertRaises(ValueError): summarize(self.plan, rows + [rows[0]])

    def test_interpolation_preserves_other_arm_and_grippers(self):
        proposal = [0.1]*14
        command = decision('interpolate', arm='right', joint_delta=[0.1]*6)
        actual = interpolate(proposal, command, self.settings, ([-1]*14, [1]*14))
        self.assertEqual(actual[:7], proposal[:7])
        self.assertEqual(actual[13], proposal[13])
        self.assertTrue(all(abs(x-.125) < 1e-9 for x in actual[7:13]))
        command['joint_delta'][0] = float('nan')
        with self.assertRaises(ValueError): interpolate(proposal, command, self.settings, ([-1]*14, [1]*14))

    def test_decision_modes_identity_and_shape(self):
        command = decision('skill', arm='left', skill='open_gripper')
        self.assertEqual(validate_decision(command, 'skills', 120, self.settings), command)
        for condition in ('baseline', 'interpolation'):
            with self.assertRaises(ValueError): validate_decision(command, condition, 120, self.settings)
        for update in ({'sequence': 119}, {'sequence': True}, {'code': 'evil'}, {'skill': 'unknown'}):
            with self.assertRaises(ValueError):
                validate_decision(dict(command, **update), 'combined', 120, self.settings)

    def test_payload_allowlist_and_three_cameras(self):
        payload = request_payload(observation(), [0]*14, 'combined', self.settings)
        text = json.dumps(payload)
        self.assertNotIn('evaluator-only', text)
        self.assertEqual(sum('inlineData' in p for p in payload['contents'][0]['parts']), 3)
        with self.assertRaises(ValueError): request_payload(observation(), [0]*14, 'baseline', self.settings)

    def test_provider_validates_missing_camera_and_truncation(self):
        response = {'modelVersion': 'fixed', 'usageMetadata': {'promptTokenCount': 12},
                    'candidates': [{'finishReason': 'STOP', 'content': {'parts': [
                        {'text': json.dumps(decision('skill', arm='left', skill='open_gripper'))}]}}]}
        supervisor = Supervisor(lambda _: copy.deepcopy(response), 'model', 'fixed')
        command, usage = supervisor.decide(observation(), [0]*14, 'combined', self.settings)
        self.assertEqual(command['kind'], 'skill')
        self.assertEqual(usage['input_tokens'], 12)
        command, usage = supervisor.decide(observation(missing='head_camera'), [0]*14, 'combined', self.settings)
        self.assertIsNone(command)
        self.assertEqual(usage['rejected'], 'invalid_decision')
        response['candidates'][0]['finishReason'] = 'MAX_TOKENS'
        self.assertIsNone(supervisor.decide(observation(), [0]*14, 'combined', self.settings)[0])


class ExecutionTests(unittest.TestCase):
    def test_recipe_preserves_other_arm_and_counts_settle(self):
        targets = []
        def planner(arm, pose):
            targets.append((arm, pose))
            return [[.1]*6, [.2]*6]
        actions = compile_skill('release_and_retract', 'left', observation(), planner,
                                ([-2]*14, [2]*14))
        self.assertEqual(len(actions), 10)  # 4 open + 2 settle + 2 path + 2 hold
        self.assertTrue(all(a[7:] == [0]*7 for a in actions))
        self.assertEqual(actions[-1][6], 1.)
        self.assertEqual(targets[0][1][2], .04)
        with self.assertRaises(ValueError):
            compile_skill('release_and_retract', 'left', observation(), planner,
                          ([-2]*14, [2]*14), maximum=3)

    def execute(self, condition, fail=False, transient=0, call_limit=10, error_code='gemini_http_503', reset_fail=False):
        settings = PilotSettings(seeds=(0,), action_horizon=8, assessment_interval=2,
                                 max_interventions=1, max_skill_actions=3, max_supervisor_calls=call_limit)
        events = []
        class Policy:
            resets = 0
            def reset(self):
                self.resets += 1
                if reset_fail and self.resets > 1:
                    raise ValueError('action chunk reset failed')
            def propose(self, obs): return [0.1]*14
        class Environment:
            sequence = 0
            def sample(self):
                return observation(self.sequence), {'success': False, 'limits': ([-2]*14, [2]*14)}
            def reset(self): return self.sample()
            def evidence(self, obs, evaluator): return {'sequence': obs.sequence}
            def step(self, sequence, action):
                self.sequence += 1
                return self.sample()
            def plan_skill(self, command, obs, maximum):
                return [[.2]*14]*3
        class Coach:
            calls = 0
            def decide(self, obs, proposal, condition, settings, previous):
                self.calls += 1
                if self.calls <= transient: raise ProviderError(error_code)
                if fail: raise TimeoutError('provider unavailable')
                return dict(decision('skill', arm='left', skill='open_gripper'),
                            sequence=obs.sequence), {'input_tokens': 7, 'output_tokens': 3}
        policy = Policy()
        result = run_trial(settings, condition, policy, Environment(), Coach(),
                           lambda kind,payload: events.append((kind,payload)))
        return result, events, policy

    def test_baseline_never_calls_supervisor(self):
        result, events, policy = self.execute('baseline', fail=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['actions'], 8)
        self.assertEqual(result['supervisor_calls'], 0)
        self.assertEqual(policy.resets, 1)

    def test_skill_actions_share_horizon_and_reset_chunk(self):
        result, events, policy = self.execute('skills')
        self.assertEqual(result['actions'], 8)
        self.assertEqual(result['interventions'], 1)
        self.assertEqual(result['supervisor_calls'], 1)
        self.assertEqual(policy.resets, 2)
        executed = [p for k,p in events if k == 'action_intent']
        self.assertEqual(sum(p['source'] == 'skill' for p in executed), 3)

    def test_provider_failure_invalidates_trial(self):
        result, events, policy = self.execute('skills', fail=True)
        self.assertEqual(result['status'], 'invalid')
        self.assertIsNone(result['success'])
        self.assertEqual(result['actions'], 2)
        self.assertEqual(result['supervisor_calls'], 1)

    def test_failed_chunk_reset_invalidates_without_dispatch(self):
        result, events, policy = self.execute('skills', reset_fail=True)
        self.assertEqual(result['status'], 'invalid')
        self.assertIsNone(result['success'])
        self.assertEqual(result['actions'], 2)
        self.assertEqual(policy.resets, 2)
        self.assertFalse(any(p['source'] == 'skill' for k, p in events if k == 'action_intent'))

    @patch('agent_vla.robotwin.episode.time.sleep')
    def test_transient_retries_are_charged_and_visible(self, sleep):
        result, events, _ = self.execute('skills', transient=1)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['supervisor_calls'], 2)
        self.assertEqual(result['provider_errors'], 1)
        self.assertTrue(result['usage_incomplete'])
        self.assertEqual(sum(k == 'provider_error' for k,p in events), 1)
        sleep.assert_called_once_with(5)

    @patch('agent_vla.robotwin.episode.time.sleep')
    def test_retry_cap_quota_and_request_cap_stop(self, sleep):
        result, _, _ = self.execute('skills', transient=10)
        self.assertEqual((result['status'], result['supervisor_calls']), ('invalid', 3))
        result, _, _ = self.execute('skills', transient=10, call_limit=1)
        self.assertEqual((result['status'], result['supervisor_calls']), ('invalid', 1))
        result, _, _ = self.execute('skills', transient=10, error_code='gemini_http_429')
        self.assertEqual((result['status'], result['supervisor_calls']), ('invalid', 1))


if __name__ == '__main__':
    unittest.main()
