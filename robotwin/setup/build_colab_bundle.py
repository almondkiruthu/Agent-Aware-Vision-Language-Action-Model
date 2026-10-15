"""Build a small, secret-free upload bundle and staged Colab notebook."""
import json
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
cells = []

def md(text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.splitlines(True)})

def code(text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "outputs": [], "source": text.splitlines(True)})

md("""# RoboTwin client starter — Colab setup and first episode
Prepared 2026-10-15. **NVIDIA L4 Vulkan, SAPIEN rendering, and an end-to-end policy episode verified.**
Select Runtime → Change runtime type → GPU using your existing Colab plan.
Run cells in order. A CUDA GPU alone does not prove NVIDIA Vulkan rendering works.
Do not continue past a failed cell or interpret the supplied videos as new results.
The model is the client's public checkpoint; no API key or Hugging Face token is needed.
""")
code("""from google.colab import files
from pathlib import Path
import zipfile, io, os, subprocess, sys
bundle = Path('/content/robotwin-colab-input.zip')
if not bundle.is_file():
    uploaded = files.upload()  # Or upload using the Files sidebar before running this cell.
    assert 'robotwin-colab-input.zip' in uploaded
    bundle.write_bytes(uploaded['robotwin-colab-input.zip'])
root = Path('/content/robotwin-agent')
root.mkdir(exist_ok=True)
with zipfile.ZipFile(bundle) as z:
    for member in z.infolist():
        assert (root / member.filename).resolve().is_relative_to(root.resolve())
    z.extractall(root)
os.chdir(root)
def run(*args):
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        print(line, end='', flush=True)
    if process.wait():
        raise subprocess.CalledProcessError(process.returncode, args)
print(root)
""")
md("""## 1. Check the assigned runtime before large downloads
Installs only Vulkan diagnostics and basic system libraries. If the next cell fails,
retain evidence/preflight.json. Do not install a replacement NVIDIA kernel driver
inside Colab. A software renderer is not an acceptable pass.
""")
code("""run('apt-get', 'update', '-qq')
run('apt-get', 'install', '-y', '-qq', 'vulkan-tools', 'libvulkan1', 'libgl1', 'libglib2.0-0', 'ffmpeg', 'git', 'unzip', 'build-essential')
import runpy
runpy.run_path('setup/colab_graphics.py', run_name='__main__')
run(sys.executable, 'setup/preflight.py')
""")
md("""## 2. Check compiler prerequisites
The client specifies CUDA 12.x with development headers and GCC/G++ 13 or newer.
If the runtime lacks these, stop and resolve the toolchain before installing CuRobo.
Do not assume the CUDA version printed by nvidia-smi is an installed toolkit.
""")
code("""import shutil, re
run('apt-get', 'install', '-y', '-qq', 'cuda-nvcc-12-8', 'cuda-cudart-dev-12-8', 'cuda-cccl-12-8')
os.environ['PATH'] = '/usr/local/cuda-12.8/bin:' + os.environ['PATH']
nvcc = shutil.which('nvcc')
assert nvcc, 'CUDA development toolkit is missing'
cuda_home = Path(nvcc).resolve().parent.parent
os.environ['CUDA_HOME'] = str(cuda_home)
assert (cuda_home / 'include/cuda_runtime_api.h').is_file(), 'CUDA headers missing'
nvcc_version = subprocess.check_output([nvcc, '--version'], text=True)
assert 'release 12.' in nvcc_version, nvcc_version
cxx = shutil.which('g++-13') or shutil.which('g++')
assert cxx
major = int(subprocess.check_output([cxx, '-dumpversion'], text=True).split('.')[0])
assert major >= 13, 'Client requires GCC/G++ >=13; this runtime needs toolchain work'
os.environ['CXX'] = cxx
os.environ['CC'] = cxx.replace('g++', 'gcc')
run(sys.executable, '-m', 'pip', 'install', 'uv')
""")
md("""## 3. Install isolated environments and test real SAPIEN rendering
The first render precedes the full dependency stack. A produced smoke image is only
a renderer check, not a RoboTwin task episode. Installation can take substantial time.
""")
code("run('bash', 'setup/install_linux.sh', 'environments')\n")
code("""from IPython.display import display, Image
display(Image(filename='evidence/sapien-smoke.png'))
""")
md("## 4. Fetch pinned source, compile CuRobo, and download assets\nThe client estimates the asset download at roughly 16 GB.\n")
code("""run('bash', 'setup/install_linux.sh', 'source')
run('bash', 'setup/install_linux.sh', 'curobo')
run('bash', 'setup/install_linux.sh', 'assets')
run('bash', 'setup/install_linux.sh', 'weights')
""")
md("""## 5. Run one frozen-policy episode
First use 30 steps to check the complete pipeline, then 1200 for a full attempt.
A short run is not a baseline measurement. The launcher stops its simulator afterward.
""")
code("run('bash', 'setup/run_smoke.sh', '0', '30')\n")
code("for seed in ('0', '1'):\n    run('bash', 'setup/run_smoke.sh', seed, '1200')\n")
md("## 6. Inspect and download evidence before the runtime expires\n")
code("""from IPython.display import Video
run(sys.executable, 'setup/collect_evidence.py')
videos = sorted(Path('outputs').glob('*/episode_*.mp4'))
assert videos, 'No generated episode video exists'
display(Video(str(videos[-1]), embed=True))
files.download('/content/robotwin-results.zip')
""")
notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
             "accelerator": "GPU", "colab": {"name": "RoboTwin_Colab.ipynb"}}, "nbformat": 4, "nbformat_minor": 5}
for i, cell in enumerate(cells):
    cell['id'] = f'robotwin-{i:02d}'
    if cell['cell_type'] == 'code': compile(''.join(cell['source']), f'cell-{i}', 'exec')
(root / 'RoboTwin_Colab.ipynb').write_text(json.dumps(notebook, indent=2) + '\n', encoding='utf-8')
with zipfile.ZipFile(root / 'robotwin-colab-input.zip', 'w', zipfile.ZIP_DEFLATED) as z:
    names = ['run_inference.py', 'requirements-sim.txt', 'requirements-policy.txt']
    names += [p.relative_to(root).as_posix() for p in (root / 'setup').glob('*') if p.is_file()]
    for name in names:
        z.write(root / name, name)
print('Built notebook (code cells compile) and small upload bundle; no weights, secrets, or legacy code included.')
