"""One synthetic three-image probe; never a robot episode or pilot result."""

import argparse
import json
import os
from pathlib import Path
import struct
import zlib

from agent_vla.evaluation.pilot import PilotSettings
from agent_vla.robotwin.contracts import Observation, CAMERAS
from agent_vla.robotwin.supervisor import Supervisor, GeminiTransport, ProviderError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--model', default='gemini-3.8-flash')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    key = os.environ.get('GEMINI_API_KEY')
    if args.env_file:
        for line in args.env_file.read_text().splitlines():
            if line.startswith('GEMINI_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"').strip("'")
    def chunk(kind, body):
        return struct.pack('!I', len(body)) + kind + body + struct.pack('!I', zlib.crc32(kind + body) & 0xffffffff)
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 32, 32, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress((b'\0' + b'\0' * 96) * 32)) + chunk(b'IEND', b''))
    observation = Observation(0, {c: png for c in CAMERAS}, (0.,)*14, (0.,)*12,
                              {s: (0., 0., 0., 1., 0., 0., 0.) for s in ('left', 'right')},
                              'synthetic')
    supervisor = Supervisor(GeminiTransport(key, args.model), args.model)
    result = {'probe': 'synthetic_black_images_not_robot_episode', 'identity': supervisor.identity()}
    try:
        decision, usage = supervisor.decide(observation, [0.]*14, 'combined', PilotSettings())
        result.update(decision=decision, usage=usage)
    except ProviderError as error:
        result['error'] = error.code
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return 0 if (result.get('decision') or {}).get('kind') == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
