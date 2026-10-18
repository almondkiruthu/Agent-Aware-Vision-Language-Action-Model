"""Single-owner simulator bridge around the unchanged client task builder.

Start a fresh process per trial. A timed-out process must be terminated before
another trial; never reuse a simulator with an uncertain in-flight action.
"""

import argparse
import base64
import hashlib
import io
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

import numpy as np
from PIL import Image

from run_inference import build_task
from agent_vla.robotwin.contracts import CAMERAS, Observation, vector
from agent_vla.robotwin.skills import compile_skill


def serve(root, port):
    import torch
    task, setup = build_task(root, 'hanging_mug')
    state = {'reset': False, 'sequence': 0, 'initial_fingerprint': None}

    def limits():
        lower, upper = [], []
        for side in ('left', 'right'):
            joints = getattr(task.robot, side + '_arm_joints')
            if len(joints) != 6:
                raise ValueError('expected six arm joints')
            for joint in joints:
                pair = np.asarray(joint.get_limits()).reshape(-1).tolist()
                if len(pair) != 2:
                    raise ValueError('unexpected joint limit shape')
                lower.append(pair[0]); upper.append(pair[1])
            lower.append(0.); upper.append(1.)
        return [list(vector(lower, 14)), list(vector(upper, 14))]

    def observe():
        raw = task.get_obs()
        targets = np.asarray(raw['joint_action']['vector'], dtype=np.float32).reshape(-1).tolist()
        targets = vector(targets, 14)
        images = {}
        for camera in CAMERAS:
            rgb = (raw.get('observation', {}).get(camera) or {}).get('rgb')
            if rgb is None:
                images[camera] = None
            else:
                array = np.asarray(rgb, dtype=np.uint8)
                if array.ndim != 3 or array.shape[2] < 3:
                    raise ValueError('camera must expose RGB')
                buffer = io.BytesIO()
                Image.fromarray(array[:, :, :3]).save(buffer, format='PNG')
                images[camera] = buffer.getvalue()
        measured = []
        poses = {}
        for side in ('left', 'right'):
            measured.extend(float(v) for v in
                            getattr(task.robot, f'get_{side}_arm_real_jointState')()[:6])
            poses[side] = np.asarray(getattr(task.robot, f'get_{side}_ee_pose')()).tolist()
        sensor = Observation(state['sequence'], images, targets, tuple(measured), poses,
                             state['initial_fingerprint'] or '')
        wire = dict(sensor.metadata(), images={k: base64.b64encode(v).decode() if v else None
                                              for k, v in images.items()})
        if state['initial_fingerprint'] is None:
            state['initial_fingerprint'] = hashlib.sha256(
                json.dumps(wire, sort_keys=True, allow_nan=False).encode()).hexdigest()
        wire.update(initial_fingerprint=state['initial_fingerprint'], limits=limits(),
                    success=bool(getattr(task, 'eval_success', False)) or bool(task.check_success()),
                    simulator_actions=int(task.take_action_cnt))
        return wire, sensor

    def plan(arm, pose):
        result = getattr(task.robot, f'{arm}_plan_path')(np.asarray(vector(pose, 7)))
        if result.get('status') != 'Success':
            raise ValueError('native planner failed')
        path = np.asarray(result['position']).tolist()
        return [list(vector(row, 6)) for row in path]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size < 100_000:
                    raise ValueError('invalid request size')
                body = json.loads(self.rfile.read(size))
                if self.path == '/health':
                    reply = {'ready': True}
                elif self.path == '/reset':
                    if state['reset'] or type(body.get('seed')) is not int:
                        raise ValueError('one integer-seed reset per simulator process')
                    state['reset'] = True
                    with torch.enable_grad():
                        task.setup_demo(**dict(setup, seed=body['seed'], is_test=True))
                    reply, _ = observe()
                else:
                    if not state['reset'] or body.get('sequence') != state['sequence']:
                        raise ValueError('stale observation or missing reset')
                    if self.path == '/step':
                        action = vector(body['action'], 14)
                        with torch.enable_grad():
                            task.take_action(np.asarray(action, dtype=np.float64))
                        state['sequence'] += 1
                        reply, _ = observe()
                        if reply['simulator_actions'] != state['sequence']:
                            raise ValueError('simulator did not consume exactly one action')
                    elif self.path == '/plan_skill':
                        _, sensor = observe()
                        reply = {'actions': compile_skill(body['skill'], body['arm'], sensor,
                                                          plan, limits(), body['maximum'])}
                    elif self.path == '/framecheck':
                        _, sensor = observe()
                        errors = {}
                        for index, side in enumerate(('left', 'right')):
                            path = plan(side, sensor.ee_poses[side])
                            errors[side] = max(abs(a-b) for a,b in zip(
                                path[-1], sensor.measured_joints[index*6:index*6+6]))
                        reply = {'max_joint_error': errors,
                                 'passed': all(v < .05 for v in errors.values())}
                    else:
                        raise ValueError('unknown endpoint')
                payload = json.dumps(reply, allow_nan=False).encode()
                status = 200
            except Exception as error:
                payload = json.dumps({'error': type(error).__name__, 'detail': str(error)[:300]}).encode()
                status = 422
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    print(f'supervised simulator ready on 127.0.0.1:{port}', flush=True)
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--robotwin-root', required=True)
    parser.add_argument('--port', type=int, default=8110)
    args = parser.parse_args()
    serve(args.robotwin_root, args.port)
