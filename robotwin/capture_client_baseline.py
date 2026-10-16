"""Instrument the unchanged starter's HTTP seam for a development parity check."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import random

import numpy as np
from PIL import Image
import torch
import run_inference as client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--weights', required=True)
    args = parser.parse_args()
    random.seed(0); np.random.seed(0); torch.manual_seed(0); torch.cuda.manual_seed_all(0)
    call = client.call
    result = {'actions': []}
    def capture(path, payload):
        response = call(path, payload)
        if path == '/reset':
            hashes = {}
            for camera in client.CAMERAS:
                stream = io.BytesIO(); Image.fromarray(response[camera]).save(stream, format='PNG')
                hashes[camera] = hashlib.sha256(stream.getvalue()).hexdigest()
            result['initial_image_sha256'] = hashes
            result['initial_state'] = response['state'].astype(float).tolist()
        else:
            result['actions'].append(payload['action'])
        return response
    client.call = capture
    result['success'] = bool(client.run_episode(args.weights, 0, 30, 'cuda', args.output.with_suffix('.mp4')))
    with args.output.open('x') as stream: json.dump(result, stream, indent=2)


if __name__ == '__main__': main()
