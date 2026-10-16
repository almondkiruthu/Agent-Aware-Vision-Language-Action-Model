"""Live integration gates on development seeds only; not evaluation results."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import time

from pilot_runtime import ROOT, identity, simulator, policy_command, digest
from run_supervised_trial import Simulator
from agent_vla.evaluation.pilot import PilotSettings, make_plan, write_plan
from agent_vla.robotwin.contracts import SKILLS, interpolate
from agent_vla.robotwin.supervisor import Supervisor, GeminiTransport, ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reference', type=Path, help='Reuse a recorded client baseline with matching runtime')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    supervisor = Supervisor(GeminiTransport(os.environ['GEMINI_API_KEY']),
                            'gemini-3.8-flash', 'gemini-3.8-flash')
    report = {'passed': False, 'runtime': identity(), 'supervisor': supervisor.identity(), 'checks': {}}
    def save():
        (output / 'readiness.json').write_text(json.dumps(report, indent=2))
    save()
    try:
        client_path = output / 'client.json'
        if args.reference:
            prior = json.loads((args.reference / 'readiness.json').read_text())['runtime']
            for key in ('pins', 'installed_robotwin_revision', 'environments', 'checkpoint_sha256'):
                if prior[key] != report['runtime'][key]:
                    raise ValueError('client reference runtime changed')
            for path, value in report['runtime']['source_sha256'].items():
                if path.endswith(('/run_inference.py', '/capture_client_baseline.py')) and prior['source_sha256'][path] != value:
                    raise ValueError('client reference capture code changed')
            client_path = args.reference / 'client.json'
            report['client_reference'] = {'path': str(client_path), 'sha256': digest(client_path)}
        else:
            with simulator(output / 'client-simulator.log', original=True):
                subprocess.run(policy_command('capture_client_baseline.py', '--output', client_path,
                                               '--weights', ROOT / 'weights'), cwd=ROOT, check=True, timeout=600)
        settings = PilotSettings(seeds=(0,), action_horizon=30)
        plan = make_plan(settings, report['runtime'], report['supervisor'])
        plan_path = output / 'parity-plan.json'; write_plan(plan_path, plan)
        with simulator(output / 'adapter-simulator.log'):
            subprocess.run(policy_command('run_supervised_trial.py', '--plan', plan_path,
                '--trial', 'seed-00000-baseline', '--output', output / 'adapter',
                '--weights', ROOT / 'weights'), cwd=ROOT, check=True, timeout=600)
        original = json.loads(client_path.read_text())
        trace = [json.loads(line) for line in (output / 'adapter/trace.jsonl').read_text().splitlines()]
        initial = next(e['payload'] for e in trace if e['kind'] == 'observation')
        actions = [e['payload']['action'] for e in trace if e['kind'] == 'action_intent']
        if (initial['image_sha256'] != original['initial_image_sha256']
                or initial['joint_targets'] != original['initial_state']
                or actions != original['actions']):
            raise ValueError('baseline parity failed: reset evidence or action sequence differs')
        report['checks']['client_baseline_parity_30_actions'] = True
        save()
        for arm in ('left', 'right'):
            for skill in SKILLS:
                name = f'{arm}-{skill}'
                folder = output / name; folder.mkdir()
                with simulator(output / f'{name}-simulator.log'):
                    environment = Simulator(2, folder)
                    observation, evaluator = environment.reset()
                    frame = environment.call('framecheck', {'sequence': 0})
                    if not frame['passed']: raise ValueError('end-effector/planner frame mismatch')
                    start_pose = list(observation.ee_poses[arm])
                    command = {'skill': skill, 'arm': arm}
                    actions = environment.plan_skill(command, observation, settings.max_skill_actions)
                    for action in actions:
                        observation, evaluator = environment.step(observation.sequence, action)
                    end_pose = observation.ee_poses[arm]
                    rise = end_pose[2] - start_pose[2]
                    if skill != 'open_gripper' and abs(rise - .04) > .02:
                        raise ValueError('retreat did not track requested upward motion')
                    grip = observation.joint_targets[6 if arm == 'left' else 13]
                    if skill != 'retreat_up' and grip < .95:
                        raise ValueError('open-gripper target not reached')
                    environment.save_images()
                    if skill == 'release_and_retract':
                        start = 0 if arm == 'left' else 7
                        proposal = list(observation.joint_targets)
                        delta = [.04 if proposal[start] + .01 < evaluator['limits'][1][start] else -.04] + [0.]*5
                        action = interpolate(proposal, {'arm': arm, 'joint_delta': delta},
                                             settings, evaluator['limits'])
                        observation, evaluator = environment.step(observation.sequence, action)
                        measured_index = 0 if arm == 'left' else 6
                        error = abs(observation.measured_joints[measured_index] - action[start])
                        if error > .02:
                            raise ValueError('interpolation did not track bounded target')
                        report['checks'][f'{arm}-interpolation'] = {'tracking_error_rad': error,
                                                                  'action': action}
                    report['checks'][name] = {'frame': frame, 'actions': len(actions),
                                              'rise_m': rise}
                    save()
                    if arm == 'right' and skill == 'release_and_retract':
                        report['provider_attempts'] = []
                        for attempt in range(3):
                            try:
                                decision, usage = supervisor.decide(observation, list(observation.joint_targets),
                                                                   'combined', settings)
                                report['provider_attempts'].append({'usage': usage, 'decision': decision})
                                if decision is None: raise ValueError('observation-only VLM response invalid')
                                break
                            except ProviderError as error:
                                report['provider_attempts'].append({'error': error.code, 'usage_unknown': True})
                                save()
                                if error.code not in ('gemini_http_503', 'gemini_transport_error') or attempt == 2:
                                    raise
                                time.sleep(5 * (attempt + 1))
                        report['checks']['observation_only_supervisor'] = True
                        save()
        report['passed'] = True
    except Exception as error:
        report['error'] = str(error)[:500]
        raise
    finally:
        save()
    print('Development gates passed; pilot may now freeze this runtime identity.', flush=True)


if __name__ == '__main__': main()
