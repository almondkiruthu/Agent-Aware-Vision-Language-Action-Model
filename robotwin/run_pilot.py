"""Freeze, execute, resume and summarize the matched forty-trial pilot.

Never retries invalid trials silently. A provider or infrastructure error stops
the batch with the attempted trial preserved, so it cannot become a task failure.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess

from pilot_runtime import ROOT, identity, simulator, policy_command
from agent_vla.evaluation.pilot import PilotSettings, make_plan, write_plan, summarize
from agent_vla.robotwin.supervisor import Supervisor, GeminiTransport


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--readiness', type=Path, required=True)
    parser.add_argument('--key-file', type=Path, help='Optional temporary file; otherwise GEMINI_API_KEY')
    args = parser.parse_args()
    readiness = json.loads(args.readiness.read_text())
    runtime = identity()
    if not readiness.get('passed') or readiness.get('runtime') != runtime:
        raise ValueError('development verification missing or code/runtime changed')
    key = args.key_file.read_text().strip() if args.key_file else os.environ['GEMINI_API_KEY']
    supervisor = readiness['supervisor']
    settings = PilotSettings()
    plan = make_plan(settings, runtime, supervisor)
    args.output.mkdir(parents=True, exist_ok=True)
    plan_path = args.output / 'plan.json'
    if plan_path.exists():
        if json.loads(plan_path.read_text()) != json.loads(json.dumps(plan)):
            raise ValueError('existing pilot has a different frozen configuration')
    else:
        write_plan(plan_path, plan)
    env = dict(os.environ, GEMINI_API_KEY=key)
    results = []
    for trial in plan['trials']:
        folder = args.output / trial['trial_id']
        result_path = folder / 'result.json'
        if result_path.exists():
            result = json.loads(result_path.read_text())
        else:
            if folder.exists():
                raise ValueError('partial trial directory needs explicit disposition')
            try:
                with simulator(args.output / (trial['trial_id'] + '-simulator.log')):
                    subprocess.run(policy_command('run_supervised_trial.py', '--plan', plan_path,
                        '--trial', trial['trial_id'], '--output', folder, '--weights', ROOT / 'weights'),
                        cwd=ROOT, env=env, check=True, timeout=settings.max_episode_seconds + 180)
            except (subprocess.SubprocessError, RuntimeError, TimeoutError) as error:
                if not result_path.exists():
                    folder.mkdir(exist_ok=True)
                    result = dict(trial, plan_sha256=plan['plan_sha256'], status='invalid', success=None,
                                  actions=0, interventions=0, error=type(error).__name__,
                                  accounting_incomplete=True)
                    result_path.write_text(json.dumps(result, indent=2))
            result = json.loads(result_path.read_text())
        results.append(result)
        report = summarize(plan, results)
        (args.output / 'summary.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({'trial': trial['trial_id'], 'status': result['status'],
                          'success': result.get('success'), 'actions': result.get('actions')}), flush=True)
        if result['status'] != 'completed':
            print('Batch stopped: invalid trial retained. No automatic replacement.', flush=True)
            return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
