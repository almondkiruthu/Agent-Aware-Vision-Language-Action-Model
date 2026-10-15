"""Download and safely extract RoboTwin assets with current Hugging Face APIs."""
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[1]
destination = root / 'RoboTwin/assets'
names = ['background_texture.zip', 'embodiments.zip', 'objects.zip']
revision = json.loads((root / 'setup/pins.json').read_text())['assets_revision']
snapshot_download(repo_id='TianxingChen/RoboTwin2.0', repo_type='dataset',
                  revision=revision, allow_patterns=names, local_dir=destination,
                  token=False, max_workers=2)
for name in names:
    print(f'Extracting {name}', flush=True)
    with zipfile.ZipFile(destination / name) as archive:
        for member in archive.infolist():
            if not (destination / member.filename).resolve().is_relative_to(destination.resolve()):
                raise RuntimeError(f'Unsafe archive entry: {member.filename}')
        archive.extractall(destination)
subprocess.run([sys.executable, 'scripts/update_embodiment_config_path.py'],
               cwd=root / 'RoboTwin', check=True)
(root / 'evidence').mkdir(exist_ok=True)
(root / 'evidence/assets.json').write_text(json.dumps({
    'repo': 'TianxingChen/RoboTwin2.0', 'revision': revision,
    'archives': names, 'extracted': True}, indent=2) + '\n')
print('Assets extracted; source revision recorded in evidence/assets.json')
