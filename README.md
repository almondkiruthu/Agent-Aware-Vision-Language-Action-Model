# Agent-Aware Vision-Language-Action Model

A frozen robot policy with an external supervisor for failure detection, bounded
interventions, and experience retained across episodes.

**Current runtime: RoboTwin `hanging_mug` with the client's public DiT checkpoint.**
The clean Colab notebook has been verified from an empty L4 runtime through
installation, rendering, a 30-step check, two 1,200-step attempts, and video export.
Both full attempts reported 0 successes. This verifies execution; it does not
establish a success-rate baseline or demonstrate improvement from supervision.

## Start here

- [RoboTwin setup and verified results](ROBOTWIN_SETUP.md): Colab instructions,
  resource requirements, pinned versions, videos, and evidence.
- [Clean Colab notebook](robotwin/RoboTwin_Colab.ipynb) and
  [upload bundle](robotwin/robotwin-colab-input.zip).
- [Codebase map and integration work](docs/codebase-map.md): reusable modules,
  legacy assumptions, and the next adapter work.
- [Research workflow](docs/research-workflow.md): install the shared package,
  record a CPU example, replay traces, and inspect evidence.
- [Architecture](docs/architecture.md) and [import migration](docs/import-migration.md).
- [Documentation index](docs/README.md): current guides and historical evidence.

The original client files in `robotwin/` remain unchanged. Its `supervise()` hook
currently passes actions through; the shared supervisor and memory modules are
not connected to this runner yet. RoboTwin uses two separate Python environments
because the simulator and policy require different NumPy versions.

## Repository layout

| Location | Purpose |
| --- | --- |
| `robotwin/` | Active client runner, setup scripts, notebook, pinned revisions, and verified evidence |
| `src/agent_vla/` | Installable shared package: runtime, observations, supervision, interventions, memory, evidence, evaluation |
| `examples/` | Runnable CPU recording and replay example |
| `tools/` | Distribution verification outside the checkout |
| `tests/` | Offline behavioral and replay tests, including legacy adapter regressions |
| `legacy/libero/` | Previous SmolVLA/LIBERO runner, simulator adapters, asset lock, and controller probe |
| `docs/` | Module guides, evaluation contracts, provenance, and architectural decisions |
| `ralph/` | Retained AFK tooling and historical queue; inactive during migration |

## Run offline checks

Use a separate development environment; these checks do not install either live
simulator, download model weights, or call paid supervisor APIs:

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m unittest discover -s tests
python -m compileall -q src examples robotwin/setup legacy
```

For shell syntax, use Bash (Git Bash or WSL on Windows):

```bash
bash -n ralph/afk.sh
bash -n robotwin/setup/install_linux.sh
bash -n robotwin/setup/run_smoke.sh
```

A passing offline suite does not validate RoboTwin physics, action semantics,
model quality, or the live supervisor. GPU execution evidence is documented
separately in the setup guide.

After installation, try the shared harness without a GPU:

```bash
python examples/record_episode.py outputs/example-trace
agent-vla replay outputs/example-trace
agent-vla timeline outputs/example-trace outputs/example-timeline.html
```

This example uses scripted CPU adapters; its result is not robot performance.
The installed package and commands work outside the checkout. Existing root
imports have moved; use the [migration table](docs/import-migration.md) to update
research notebooks.

## Previous implementation

The [historical LIBERO guide](docs/legacy-libero.md) preserves its commands,
results, and detailed shared-harness documentation. Run its CLI as a module from
the repository root: `python -m legacy.libero.run_smolvla_episode --help`.
Its seven-dimensional end-effector corrections and LIBERO task allocations must
not be reused as RoboTwin's fourteen-dimensional joint-target actions.

The active remote is
`https://github.com/almondkiruthu/Agent-Aware-Vision-Language-Action-Model.git`.
GitHub Issues were disabled on this fork when checked on 2026-10-15. Reconcile
issue tracking and migration scope before resuming the historical AFK queue.
