"""Owned simulator processes and immutable runtime identity for pilot scripts."""

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): value.update(block)
    return value.hexdigest()


def identity():
    pins = json.loads((ROOT / 'setup' / 'pins.json').read_text())
    revision = subprocess.check_output(['git', '-C', str(ROOT / 'RoboTwin'),
                                        'rev-parse', 'HEAD'], text=True).strip()
    if revision != pins['robotwin']:
        raise ValueError('installed RoboTwin revision differs from pin')
    if digest(ROOT / 'run_inference.py') != '242c728f2ff8761156d3ed162b4fc706a4aa4931e15b30075e4cef5d34d4e0a1':
        raise ValueError('original client runner changed')
    sources = sorted((REPO / 'src' / 'agent_vla').rglob('*.py'))
    sources += sorted(ROOT.glob('*.py'))
    sources += [ROOT / 'setup' / 'pins.json']
    weights = sorted(p for p in (ROOT / 'weights').iterdir() if p.is_file() and not p.name.endswith('.partial'))
    if not (ROOT / 'weights' / 'model.safetensors').is_file():
        raise ValueError('checkpoint missing')
    environments = {}
    for name in ('sim', 'policy'):
        query = ('import importlib.metadata as m,json,sys; '
                 'print(json.dumps({"python":sys.version,"packages":'
                 '{d.metadata["Name"]:d.version for d in m.distributions()}}))')
        environments[name] = json.loads(subprocess.check_output(
            [str(ROOT / f'.venv-{name}/bin/python'), '-c', query], text=True))
    return {'pins': pins, 'installed_robotwin_revision': revision,
            'environments': environments,
            'source_sha256': {str(p.relative_to(REPO)).replace('\\', '/'): digest(p) for p in sources},
            'checkpoint_sha256': {p.name: digest(p) for p in weights}}


@contextmanager
def simulator(log, original=False):
    with socket.socket() as sock:
        # A closed HTTP connection can retain TIME_WAIT without a live owner.
        # SO_REUSEADDR permits that state but still refuses an active listener.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('127.0.0.1', 8110))
    command = [str(ROOT / '.venv-sim/bin/python'), '-u']
    command += (['run_inference.py', 'sim'] if original else ['supervised_simulator.py'])
    command += ['--robotwin-root', str(ROOT / 'RoboTwin')]
    with Path(log).open('x') as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            deadline = time.monotonic() + 180
            while True:
                if process.poll() is not None:
                    raise RuntimeError('simulator exited before readiness')
                try:
                    with socket.create_connection(('127.0.0.1',8110), timeout=1): break
                except OSError:
                    if time.monotonic() > deadline: raise TimeoutError('simulator startup')
                    time.sleep(1)
            yield process
        finally:
            # Includes planner children. Never reset or reuse an uncertain process.
            try: os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()


def policy_command(script, *args):
    return [str(ROOT / '.venv-policy/bin/python'), '-u', str(ROOT / script), *map(str,args)]
