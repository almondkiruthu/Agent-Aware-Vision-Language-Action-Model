"""Record actual episode outputs and package small artifacts before Colab expires."""
import hashlib
import json
import re
import subprocess
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
episodes = []
for folder in sorted((root / 'outputs').glob('*')):
    if not folder.is_dir():
        continue
    policy = folder / 'policy.log'
    log = policy.read_text(errors='replace') if policy.exists() else ''
    verdict = re.findall(r'success rate:\s*([^\n]+)', log)
    entry = {'run': folder.name, 'reported_result': verdict[-1] if verdict else None,
             'videos': []}
    simulator = folder / 'simulator.log'
    sim_text = simulator.read_text(errors='replace') if simulator.exists() else ''
    sim_text = re.sub(r'\x1b\[[0-9;]*m', '', sim_text)
    steps = re.findall(r'step:\s*(\d+)', sim_text)
    entry['last_reported_step'] = int(steps[-1]) if steps else None
    for video in folder.glob('episode_*.mp4'):
        metadata = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,nb_frames,duration', '-of', 'json',
            str(video)], text=True))
        entry['videos'].append({'path': video.relative_to(root).as_posix(),
                                'bytes': video.stat().st_size,
                                'sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
                                'metadata': metadata})
    episodes.append(entry)
evidence = root / 'evidence'
evidence.mkdir(exist_ok=True)
(evidence / 'episodes.json').write_text(json.dumps(episodes, indent=2) + '\n')
for name in ('sim', 'policy'):
    result = subprocess.check_output(['uv', 'pip', 'freeze', '--python',
                                     str(root / f'.venv-{name}/bin/python')], text=True)
    (evidence / f'{name}-packages.txt').write_text(result)
destination = root.parent / 'robotwin-results.zip'
with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
    for directory in ('evidence', 'outputs'):
        for path in (root / directory).rglob('*'):
            if path.is_file():
                archive.write(path, path.relative_to(root))
print(json.dumps(episodes, indent=2))
print(f'Evidence archive: {destination} ({destination.stat().st_size} bytes)')
