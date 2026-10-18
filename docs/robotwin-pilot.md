# RoboTwin supervisor pilot

This is an exploratory comparison on `hanging_mug`. It is not a reproduction of
Harness VLA or a claim that the supervisor improves performance. A completed
implementation, a passed development gate, and a completed pilot are separate
milestones. See the downloaded `readiness.json` and `verified-summary.json` for
execution evidence; absent files mean that milestone has not been verified.

## Frozen comparison

Ten seeds (100–109), each under baseline, skills, interpolation, and combined:
40 episodes. Condition order rotates across seeds. Every condition uses the
same public client checkpoint and pinned simulator source. Policy sampling is
seeded identically per starting seed. Memory is disabled across episodes.

Each episode permits 1,200 executed actions, including recovery and settle
actions, and 1,800 seconds of episode time. The supervisor first assesses after
120 actions, then after at least another 120. It gets at most ten requests and
three interventions. Attempts are charged before planning, including rejected
plans. No requests are made after the intervention allowance is exhausted.
Policy action chunks are reset after accepted corrections.

The selected supervisor is Gemini 3.5 Flash-Lite, with exact returned model version, prompt
hash, generation settings, checkpoint hashes, and source hashes frozen in the
plan. There is no automatic provider or model switch within a pilot. Colab reads
`GEMINI_API_KEY` through `google.colab.userdata`; never put its value in a cell.
Before evaluation, Gemini 3.8 Flash repeatedly returned HTTP 503, including a
minimal text-only request. The provider reported high demand. A three-image
probe succeeded with 3.5 Flash-Lite, so the development gate explicitly selects
that model; this is a pre-pilot choice, not a fallback during evaluation.
Transient HTTP 503/transport failures receive at most two retries, after 5 and
10 seconds. Every attempt consumes the same ten-request episode allowance and
is logged; failed requests have unknown token usage, not assumed zero cost.
Quota errors and exhausted retries stop the batch and invalidate the trial. Malformed or
truncated decisions are recorded as rejections and leave the policy in control.

## Observations and corrections

The model sees head, left-wrist and right-wrist RGB images, current joint command
targets, measured arm joints, and proprioceptive end-effector poses. At later
assessments it also sees the preceding assessment. Evaluator success, hidden
object positions and reset fingerprints are excluded from the request.
Gripper values are command targets, not measured contact or grasp confirmation.

The skills are `open_gripper`, `retreat_up`, and `release_and_retract`, each with
an explicit arm. The last uses a pinned Apache-2.0 open-robot-skills recipe;
see its packaged notice and license and the [source audit](client-reference-research.md).
The adapter compiles the entire recipe before dispatch. Upward retreat is
0.04 m from current proprioception, preserving orientation, with native joint
planning. All waypoints and settle actions count toward the same action horizon.
Overlong plans are rejected, not downsampled. The maximum is 160 actions.
This limit was selected before evaluation: planning-only checks on development
seed 2 produced 131–132 waypoints for retreat and 139 actions for release and
retract. All skill actions count toward the shared 1,200-action episode horizon.
Native planner success is not a guarantee of scene collision avoidance.

Interpolation is the explicitly provisional definition
`corrected_arm_target = policy_arm_target + 0.25 * joint_delta`, with each of
six deltas bounded to ±0.15 rad. Both grippers and the other arm remain unchanged.
The corrected target must satisfy native limits. This is action blending,
not learned next-action prediction or trajectory densification. The client's
meaning remains unconfirmed; results must retain this qualification.

## Reuse and integration seam

The original `robotwin/run_inference.py` remains unchanged. The new scripts
import its task builder and checkpoint loader. `agent_vla.robotwin.episode`
reuses the existing `InterventionBudget` and `EpisodeDeadline` primitives.
The legacy harness's two-view observation and exactly-two-action recovery
contract cannot represent three cameras and variable-length joint-space skills.
The RoboTwin seam therefore has its own typed observation/decision contract and
hash-chained journal. It is not compatible with the older replay command and
does not claim replay verification that was never performed.

Each trial gets a fresh simulator process and planner process group. On timeout
or failure the owner terminates that group before starting another trial. HTTP
requests are serialized in the simulator; stale sequence numbers are rejected.

## Execute after the standard Colab setup

Build the small overlay locally:

```powershell
.venv\Scripts\python.exe robotwin/setup/build_pilot_bundle.py
```

Upload `robotwin-pilot-code.zip` to session storage. Run the existing setup
notebook through the asset/checkpoint installation cell, then this code:

```python
from pathlib import Path
from google.colab import userdata
import os, zipfile
with zipfile.ZipFile('/content/robotwin-pilot-code.zip') as archive:
    for item in archive.infolist():
        assert (Path('/content') / item.filename).resolve().is_relative_to(Path('/content'))
    archive.extractall('/content')
os.environ['PYTHONPATH'] = '/content/src'
os.environ['GEMINI_API_KEY'] = userdata.get('GEMINI_API_KEY')
run('.venv-policy/bin/python', '-m', 'unittest', 'discover', '-s', '/content/pilot-tests')
run('.venv-policy/bin/python', '-u', 'run_development.py', '--output', 'outputs/development')
run('.venv-policy/bin/python', '-u', 'run_pilot.py', '--readiness',
    'outputs/development/readiness.json', '--output', 'outputs/pilot')
run('.venv-policy/bin/python', 'setup/verify_pilot_results.py', 'outputs/pilot')
```

Use fresh development directories when code changes. The gate compares 30
baseline actions and initial camera/state evidence against the unchanged client,
checks planner coordinate conventions, exercises every skill on both arms, and
obtains valid observation-only VLM responses. It uses development seeds 0 and 2,
never the pilot seeds. Any failure prevents the pilot launch.

The pilot refuses configuration changes on resume, retains invalid/partial
attempts, and does not silently replace them. Resume is for unattempted trials
under an unchanged plan. Investigating an invalid trial requires an explicit
disposition and a new run identity; never overwrite evidence to improve a score.

## Evidence and interpretation

Each trial records proposed and dispatched actions, sequence-linked observations,
supervisor responses/usage, admissions/rejections, a head-camera video, and PNGs
at initial state and supervisor assessments. A SHA-256 chain protects journal
ordering; the final result inventories file hashes. Verification checks hashes,
counter agreement and video frame count. Download all evidence before releasing
the runtime, then verify the downloaded archive and artifacts locally.

Report all planned, completed, invalid and missing trials separately. Success
rates use completed episodes; missing or infrastructure-invalid trials are not
robot failures. Exact observed reset fingerprints establish whether pairs match.
The summary includes Wilson 95% intervals and paired win/loss counts only for
complete matched seeds. With ten starts, uncertainty is substantial: this pilot
can expose integration problems and suggest a larger study, not establish a
population-level improvement. Skill return flags never establish task success.
