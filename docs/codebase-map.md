# Codebase map for the RoboTwin transition

## Active execution

`robotwin/run_inference.py` is the unchanged client starter. The simulator runs
in Python 3.10/NumPy 1, the policy in Python 3.12/NumPy 2, communicating over
localhost HTTP. `robotwin/setup/` owns installation and episode/export commands;
the notebook orchestrates them. The public checkpoint and upstream revisions
are recorded in `robotwin/setup/pins.json`.

The starter presents head, left, and right camera images, a 14-value state, and
14-value actions for the bimanual robot. Its `supervise()` hook passes actions
through. Successful installation and completed videos are verified; the shared
supervisor implementation is not wired into this path.

## Shared package

The implementation installs from `src/agent_vla/`. See the
[architecture guide](architecture.md) for module responsibilities and the
[migration table](import-migration.md) for exact old-to-new imports.
The table below uses the earlier names to connect existing research concepts
to the integration work still required.

| Modules | Existing responsibility | RoboTwin integration consideration |
| --- | --- | --- |
| `episode_harness`, `policy_adapter`, `environment_interruption` | Episode lifecycle, proposals, execution ownership, policy resume, interruption | Define adapters for the two-process runner and preserve action-chunk reset behavior |
| `camera_evidence`, `robot_state_evidence`, `observation_window` | Observation identity, freshness, camera/state evidence | Add explicit mapping for all three cameras and joint state; existing LIBERO field mappings are not a RoboTwin contract |
| `supervisor_*`, `temporal_*`, progress detectors | Decisions, diagnosis, retries, eligibility, provider abstraction | Filter evaluator-only success and retain missing-sensor information before exposing observations |
| `action_capabilities`, `correction_*`, recovery/adjustment modules | Validated bounded interventions and accounting | Define joint-target capabilities and limits; old end-effector translation/gripper tools cannot transfer unchanged |
| `recorded_replay`, `artifact_*`, `episode_timeline`, `shareable_report` | Traces, replay, integrity, reports | Map new runtime traces into the established evidence contract |
| Memory modules | Outcome-linked experience, snapshots, fixed/adaptive memory | Start with task-compatible memory and explicit policy/environment identity |
| `evaluation_*`, `detector_metrics` | Allocation, accounting, acceptance, comparison | Review LIBERO-10 task lists and assumptions before measuring RoboTwin |

Observation filtering, freshness, and ingestion now live independently of the
episode loop in `agent_vla.observations.contracts`. Existing behavioral tests
are retained. Passing them establishes preserved behavior, not applicability
of every capability to RoboTwin.

## Isolated historical implementation

`legacy/libero/` contains the former root CLI, `libero_adapter`,
`libero_initial_state`, `baseline_environment`, `pinned_policy`, the checkpoint
asset lock, and `inspect_simulator_controller`. Tests import these explicitly
through `legacy.libero`. The former root README is preserved as
[legacy-libero.md](legacy-libero.md); historical guides remain reachable from it.

## Next integration work

1. Specify the starter observation/action contract, including missing cameras,
   joint ordering, limits, success handling, and chunk-resumption behavior.
2. Add an observation-only adapter and trace recording around the unchanged
   baseline. Keep evaluator success out of supervisor requests.
3. Verify baseline parity before enabling bounded corrections or memory.
4. Define RoboTwin-specific correction capabilities and evaluation allocation.

The inherited AFK queue and its old spending/model assumptions are historical.
The fork has Issues disabled as of 2026-10-15. No issue IDs were migrated or
reopened, no queue was launched, and no paid supervisor calls were made during
this cleanup.

## Cleanup verification (2026-10-15)

All 587 offline tests passed before and after relocating the legacy integration.
Both relocated command-line help entry points work; Python compilation, Bash
syntax checks, CI YAML parsing, and the new documentation links pass. All ten
original client file hashes still match the starter manifest. The updated CI
workflow is configured but has not run on GitHub; no new GPU or paid-provider
execution was needed for this structural cleanup.
