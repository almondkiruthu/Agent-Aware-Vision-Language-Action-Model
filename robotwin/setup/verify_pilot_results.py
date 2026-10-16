"""Verify downloaded trial hashes, action accounting, videos and matched results."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from agent_vla.evaluation.pilot import summarize


def verify_trial(folder, result):
    for name, expected in result['artifacts'].items():
        path = folder / name
        if path.parent != folder or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'artifact hash mismatch: {name}')
    previous = '0' * 64
    observations = 0
    admissions = 0
    calls = 0
    for line in (folder / 'trace.jsonl').read_text().splitlines():
        event = json.loads(line)
        supplied = event.pop('sha256')
        if event['previous_sha256'] != previous:
            raise ValueError('broken journal chain')
        previous = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        if supplied != previous: raise ValueError('modified journal event')
        if event['kind'] == 'observation': observations += 1
        if event['kind'] == 'intervention_admission' and event['payload']['admitted']: admissions += 1
        if event['kind'] == 'supervisor_request': calls += 1
    if previous != result['trace_terminal_sha256']:
        raise ValueError('journal terminal hash mismatch')
    if result['status'] == 'completed':
        if (observations != result['actions'] + 1 or admissions != result['interventions']
                or calls != result['supervisor_calls']):
            raise ValueError('result counters differ from journal')
        if result['actions']:
            info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-count_frames',
                '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'json',
                str(folder / 'episode.mp4')], text=True))
            if int(info['streams'][0]['nb_read_frames']) != result['actions']:
                raise ValueError('video frame count differs from executed action count')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    plan = json.loads((args.directory / 'plan.json').read_text())
    results = []
    for trial in plan['trials']:
        folder = args.directory / trial['trial_id']
        path = folder / 'result.json'
        if path.exists():
            result = json.loads(path.read_text())
            if not result.get('accounting_incomplete'):
                verify_trial(folder, result)
            results.append(result)
    report = summarize(plan, results)
    report['artifact_verification'] = 'passed_for_available_complete_artifact_sets'
    (args.directory / 'verified-summary.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
