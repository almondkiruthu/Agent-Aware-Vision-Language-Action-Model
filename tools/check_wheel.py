"""Check the built distribution in a disposable environment outside the checkout."""

import argparse
import json
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    wheel = args.wheel.resolve(strict=True)
    fixture = Path(__file__).resolve().parents[1] / "tests/fixtures/recorded_episode"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)

    with TemporaryDirectory(prefix="agent-vla-wheel-") as directory:
        root = Path(directory).resolve()
        venv.EnvBuilder(with_pip=True).create(root / "environment")
        binaries = root / "environment" / ("Scripts" if os.name == "nt" else "bin")
        python = binaries / ("python.exe" if os.name == "nt" else "python")

        def run(*command):
            return subprocess.run(command, cwd=root, env=environment, check=True,
                                  capture_output=True, text=True)

        run(str(python), "-I", "-m", "pip", "install", "--no-index", "--no-deps", str(wheel))
        imported = run(str(python), "-I", "-c", """
import importlib
import pkgutil
import sys
from pathlib import Path
import agent_vla
assert Path(agent_vla.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
names = [item.name for item in pkgutil.walk_packages(agent_vla.__path__, 'agent_vla.')
         if not item.name.endswith('.__main__')]
for name in names:
    importlib.import_module(name)
assert not any(name in sys.modules for name in ('torch', 'numpy', 'sapien', 'lerobot'))
print(f'Imported {len(names)} modules from the installed wheel without ML dependencies.')
""")
        print(imported.stdout.strip())
        command = binaries / ("agent-vla.exe" if os.name == "nt" else "agent-vla")
        result = json.loads(run(str(command), "replay", str(fixture)).stdout)
        assert result["replay_outcome"]["steps"] == 2
        assert result["replay_outcome"]["success"] is False
        assert result["primary_acceptance_evidence"] is False
        print("Installed command replayed the sealed fixture outside the checkout.")


if __name__ == "__main__":
    main()
