# Work with the shared harness

Use Python 3.13 for the tested development environment. The package declares
Python 3.10 or later; GPU runtime setup remains separate in
[ROBOTWIN_SETUP.md](../ROBOTWIN_SETUP.md).

## Install

From the repository root:

```bash
python -m venv .venv
# PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m agent_vla --help
```

The core package uses only the standard library. The development extra installs
NumPy for array-behavior tests. For library use without those tests, install with
`python -m pip install .`. No model weights or simulator packages are installed.

## Record, replay, and inspect an episode

```bash
python examples/record_episode.py outputs/example-trace
agent-vla replay outputs/example-trace
agent-vla timeline outputs/example-trace outputs/example-timeline.html
```

The example uses deterministic CPU adapters and scripted success. It demonstrates
recording and replay, not robot performance. Use a new output directory each run;
recording and timeline commands refuse to overwrite previous research evidence.
`python -m agent_vla` is equivalent to the installed `agent-vla` command.

For a full artifact bundle with `bundle.json`, use:

```bash
agent-vla verify-bundle /path/to/bundle --replay
```

A trace has `manifest.json`; a full bundle additionally inventories run artifacts.
Do not pass a plain trace to `verify-bundle`. Invalid evidence produces a nonzero
exit status and a diagnostic on stderr. Successful commands emit JSON on stdout.

From a notebook or another project:

```python
from agent_vla.evidence.replay import load_recorded_replay

replay = load_recorded_replay("/absolute/path/to/sealed-trace")
report = replay.report()
assert report["primary_acceptance_evidence"] is False
```

Install the package into the notebook kernel's environment first. Imports do not
require changing its working directory to this repository.

## Change execution behavior

Start with `agent_vla.runtime.harness.EpisodeConfig` and `run_episode`. Supply a
policy, environment, and recorder satisfying the documented protocols in that
module. Use `agent_vla.observations.contracts` for observation types and validation.
The example demonstrates this composition with the existing replay adapters.
For supervised execution, read the [supervisor guide](supervisor-vlm.md) and
[observation-only workflow](observation-only.md) before adding interventions.

The RoboTwin runner is not connected to these interfaces yet. Its baseline
episodes and videos remain governed by the separate setup guide.

## Verify a change

```bash
python -m unittest discover -s tests
python -m compileall -q src examples robotwin/setup legacy
python -m pip wheel . --no-deps --wheel-dir dist
python tools/check_wheel.py dist/agent_vla-0.1.0-py3-none-any.whl
```

The wheel check creates a temporary environment, installs only the built wheel,
imports every packaged module, exercises the installed command, and replays a
fixture from outside the checkout. It removes that temporary environment when
finished. CI runs the behavioral suite and this distribution check on Windows
and Linux. CI configuration is not evidence of a completed hosted CI run.

The historical LIBERO commands stay available from a checkout after installing
the shared package. See [the legacy guide](legacy-libero.md). Update old root
imports using [the migration table](import-migration.md).
