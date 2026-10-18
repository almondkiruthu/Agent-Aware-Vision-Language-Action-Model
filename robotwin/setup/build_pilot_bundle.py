"""Build a small code-only overlay for the already verified Colab setup."""

from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def main():
    target = ROOT / 'robotwin-pilot-code.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((REPO / 'src/agent_vla').rglob('*')):
            if path.is_file() and ('__pycache__' not in path.parts) and (
                    path.suffix in ('.py', '.md') or path.name == 'OPEN_ROBOT_SKILLS_LICENSE'):
                archive.write(path, path.relative_to(REPO).as_posix())
        for path in sorted(ROOT.glob('*.py')):
            archive.write(path, 'robotwin-agent/' + path.name)
        archive.write(ROOT / 'setup/probe_supervisor.py', 'robotwin-agent/setup/probe_supervisor.py')
        archive.write(ROOT / 'setup/verify_pilot_results.py', 'robotwin-agent/setup/verify_pilot_results.py')
        archive.write(ROOT / 'setup/probe_socket_reuse.py', 'robotwin-agent/setup/probe_socket_reuse.py')
        archive.write(REPO / 'tests/test_robotwin_pilot.py', 'pilot-tests/test_robotwin_pilot.py')
    print(f'{target}: {target.stat().st_size} bytes; explicit code allowlist, no credentials')


if __name__ == '__main__': main()
