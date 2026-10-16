"""Execute one allocated trial, preserving client policy preprocessing exactly."""

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import random
import urllib.request
import urllib.error

import numpy as np
from PIL import Image

from run_inference import load_policy
from agent_vla.evaluation.pilot import validate_plan
from agent_vla.robotwin.contracts import Observation, CAMERAS
from agent_vla.robotwin.episode import run_trial
from agent_vla.robotwin.supervisor import Supervisor, GeminiTransport


class Simulator:
    def __init__(self, seed, output, port=8110):
        self.seed, self.output, self.port = seed, output, port
        self.latest = None
        self.video = None

    def call(self, endpoint, payload):
        request = urllib.request.Request(f'http://127.0.0.1:{self.port}/{endpoint}',
                                         json.dumps(payload, allow_nan=False).encode(),
                                         {'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(request, timeout=180) as reply:
                return json.load(reply)
        except urllib.error.HTTPError as error:
            detail = json.loads(error.read()).get('detail', 'simulator rejected request')
            raise ValueError(detail) from None

    def decode(self, wire):
        observation = Observation(wire['sequence'],
                    {k: base64.b64decode(wire['images'][k], validate=True)
                     if wire['images'][k] else None for k in CAMERAS},
                    tuple(wire['joint_targets']), tuple(wire['measured_arm_joints']),
                    wire['end_effector_poses_xyz_wxyz'], wire['initial_fingerprint'])
        if any(image is None for image in observation.images.values()):
            raise ValueError('client policy requires all three cameras')
        self.latest = observation
        return observation, {'success': wire['success'], 'limits': wire['limits'],
                              'simulator_actions': wire['simulator_actions']}

    def reset(self):
        decoded = self.decode(self.call('reset', {'seed': self.seed}))
        self.save_images()
        return decoded

    def step(self, sequence, action):
        if self.video:
            self.video.write_frame(self.image('head_camera'))
        return self.decode(self.call('step', {'sequence': sequence, 'action': action}))

    def image(self, camera):
        return np.asarray(Image.open(io.BytesIO(self.latest.images[camera])).convert('RGB'))

    def plan_skill(self, decision, observation, maximum):
        return self.call('plan_skill', {'sequence': observation.sequence, 'maximum': maximum,
                                       'skill': decision['skill'], 'arm': decision['arm']})['actions']

    def save_images(self):
        for camera, data in self.latest.images.items():
            if data:
                (self.output / f'{self.latest.sequence:04d}-{camera}.png').write_bytes(data)

    def evidence(self, observation, evaluator):
        return dict(observation.metadata(), evaluator=evaluator,
                    image_sha256={k: hashlib.sha256(v).hexdigest() if v else None
                                  for k,v in observation.images.items()})


class FrozenPolicy:
    def __init__(self, weights, device):
        self.device = device
        self.policy, self.preprocessor, self.postprocessor = load_policy(weights, device)

    def reset(self):
        self.policy.reset()

    def propose(self, observation):
        import torch
        batch = {'observation.images.' + target:
                 np.asarray(Image.open(io.BytesIO(observation.images[source])).convert('RGB')).copy()
                 for source,target in zip(CAMERAS, ('cam_high', 'cam_left_wrist', 'cam_right_wrist'))}
        batch['observation.state'] = np.asarray(observation.joint_targets, dtype=np.float32)
        batch = {k: torch.as_tensor(v).to(self.device).unsqueeze(0) for k,v in batch.items()}
        for key in list(batch):
            if 'images' in key:
                batch[key] = batch[key].permute(0, 3, 1, 2).float() / 255.0
        batch['task'] = ['hang the mug on the rack']
        with torch.no_grad():
            action = self.postprocessor(self.policy.select_action(self.preprocessor(batch)))
        return action.squeeze(0).cpu().numpy().astype(float).tolist()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', required=True)
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--port', type=int, default=8110)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    settings = validate_plan(plan)
    trial = next(t for t in plan['trials'] if t['trial_id'] == args.trial)
    args.output.mkdir(parents=True, exist_ok=False)
    import torch
    import imageio.v3 as imageio
    random.seed(trial['seed']); np.random.seed(trial['seed']); torch.manual_seed(trial['seed'])
    torch.cuda.manual_seed_all(trial['seed'])
    environment = Simulator(trial['seed'], args.output, args.port)
    journal = (args.output / 'trace.jsonl').open('x', encoding='utf-8')
    chain = '0' * 64
    def record(kind, payload):
        nonlocal chain
        if kind == 'supervisor_request':
            environment.save_images()
        event = {'kind': kind, 'payload': payload, 'previous_sha256': chain}
        chain = hashlib.sha256(json.dumps(event, sort_keys=True, allow_nan=False).encode()).hexdigest()
        event['sha256'] = chain
        journal.write(json.dumps(event, allow_nan=False) + '\n'); journal.flush()
    result = dict(trial, plan_sha256=plan['plan_sha256'], status='invalid', success=None,
                  actions=0, interventions=0)
    try:
        identity = plan['supervisor']
        supervisor = None
        if trial['condition'] != 'baseline':
            supervisor = Supervisor(GeminiTransport(os.environ['GEMINI_API_KEY'], identity['model']),
                                    identity['model'], identity['model_version'])
            if supervisor.identity() != identity:
                raise ValueError('supervisor identity differs from frozen plan')
        policy = FrozenPolicy(args.weights, args.device)
        environment.video = imageio.imopen(str(args.output / 'episode.mp4'), 'w', plugin='pyav')
        environment.video.init_video_stream('libx264', fps=30)
        result.update(run_trial(settings, trial['condition'], policy, environment, supervisor, record))
    except Exception as error:
        result['error'] = type(error).__name__
    finally:
        if environment.video:
            try:
                environment.video.close()
            except Exception:
                result.update(status='invalid', success=None, error='video_finalize_failed')
        journal.close()
        result['trace_terminal_sha256'] = chain
        result['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in args.output.iterdir() if p.is_file()}
        with (args.output / 'result.json').open('x') as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
        print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
