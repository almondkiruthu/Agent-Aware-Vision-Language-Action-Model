"""Register matching NVIDIA userspace Vulkan and EGL files for Colab.

Execute with runpy.run_path(..., run_name='__main__') in the notebook so
environment variables propagate to subsequent subprocesses. No kernel install.
"""
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path


def configure():
    root = Path(__file__).resolve().parents[1]
    version = subprocess.check_output(
        ['nvidia-smi', '--query-gpu=driver_version', '--format=csv,noheader'],
        text=True).splitlines()[0].strip()
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise RuntimeError(f'Unexpected driver version: {version!r}')
    cache = root / '.cache/nvidia'
    cache.mkdir(parents=True, exist_ok=True)
    graphics = cache / f'NVIDIA-Linux-x86_64-{version}-no-compat32'
    if not graphics.is_dir():
        archive = cache / (graphics.name + '.run')
        url = f'https://download.nvidia.com/XFree86/Linux-x86_64/{version}/{archive.name}'
        print(f'Downloading matching NVIDIA userspace files: {version}', flush=True)
        urllib.request.urlretrieve(url, archive)
        subprocess.run(['sh', str(archive), '--extract-only'], cwd=cache, check=True)
    glx = graphics / f'libGLX_nvidia.so.{version}'
    egl = graphics / f'libEGL_nvidia.so.{version}'
    if not glx.is_file() or not egl.is_file():
        raise RuntimeError('Matching graphics libraries are missing')
    icd_data = json.loads((graphics / 'nvidia_icd.json').read_text())
    icd_data['ICD']['library_path'] = str(glx)
    icd = cache / 'nvidia_icd.json'
    icd.write_text(json.dumps(icd_data))
    vendor = cache / '10_nvidia.json'
    vendor.write_text(json.dumps({'file_format_version': '1.0.0',
                                 'ICD': {'library_path': str(egl)}}))
    os.environ['VK_ICD_FILENAMES'] = str(icd)
    os.environ['__EGL_VENDOR_LIBRARY_FILENAMES'] = str(vendor)
    os.environ['LD_LIBRARY_PATH'] = str(graphics) + ':' + os.environ.get('LD_LIBRARY_PATH', '')
    print('NVIDIA Vulkan and EGL registered; run preflight and render smoke next.')


if __name__ == '__main__':
    configure()
