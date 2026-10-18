# Client references: RoboTwin intervention pilot

Inspected 2026-10-16. This is a source audit and implementation recommendation,
not evidence that an upstream method has run in our environment. The client
supplied three references: open-robot-skills, GPT-Policy, and Harness VLA. None
defines the client's intended interpolation experiment unambiguously.

## Exact source revisions

| Reference | Inspected revision | Reuse status |
| --- | --- | --- |
| [open-robot-skills](https://github.com/graph-robots/open-robot-skills/tree/752dfbd96968d4d08379f8111765efbf6457800b) | `752dfbd96968d4d08379f8111765efbf6457800b` | Apache-2.0 repository; wrapped dependencies retain their own licenses |
| [GPT-Policy](https://github.com/cheng-haha/GPT-Policy/tree/2ca201638e1139fe35973c8a2d209a894b389db1) | `2ca201638e1139fe35973c8a2d209a894b389db1` | Review/evaluation source; redistribution/commercial license not selected |
| [Harness VLA website and paper source](https://github.com/harnessvla/harnessvla.github.io/tree/ddca453cceb7c60456d54d5f7220a6b2eb0dcfc4) | `ddca453cceb7c60456d54d5f7220a6b2eb0dcfc4` | Read for method; no repository license identified |
| [RPent, linked by Harness VLA's Code button](https://github.com/RLinf/RPent/tree/efc392adc98a30045d8fb83c4097917f28e20a94) | `efc392adc98a30045d8fb83c4097917f28e20a94` | Apache-2.0, with actual RoboTwin primitives |

Pins were obtained through GitHub's commits API; files were read through its
contents API at those revisions. No upstream repository was installed, no
checkpoint was downloaded, and no upstream implementation was copied by this
research task. The website browser fetch failed; its public `index.html` and
paper's TeX source were inspected through GitHub instead.

## 1. open-robot-skills: reusable recipes, not a ready RoboTwin controller

This repository packages manipulation recipes around GaP's `NodeContext` and
named robot/perception tools. Its directory-per-skill format is useful, but
installing it alone does not connect those tools to our simulator. Its root
license also explicitly preserves upstream dependency licenses. See the pinned
[README](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/README.md)
and [license](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/LICENSE).

Concrete candidates:

| Script | Actual inputs/dependencies | Relevance and missing work |
| --- | --- | --- |
| [`release_and_retract.py`](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/executing-feature-mating/scripts/release_and_retract.py) | NumPy, `gap.NodeContext`; final SE3 pose, optional fixture axis, attachment spheres, relation and arm; calls `robot.open_gripper`, `robot.go_to_pose_cartesian`, `robot.wait_steps` | Strongest small recipe candidate. Release and clear a fixture after placement. Needs a verified Cartesian adapter and valid pose; it does not infer when releasing a mug is appropriate. |
| [`execute_placement_plan.py`](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/executing-feature-mating/scripts/execute_placement_plan.py) | The [skill contract](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/executing-feature-mating/SKILL.md) declares ordered poses, planner, Cartesian servo and contact-controlled seating tools | Relevant to putting a handle over a support. Requires a complete geometry/trajectory adapter; a planned leg and a contact leg have different semantics. |
| [`plan_linear_engagement.py`](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/planning-held-object-motion/scripts/plan_linear_engagement.py) | NumPy, SciPy rotations, held-feature transform, fixture axis/pose, collision world, attached object; optional SAM3 plus calibrated depth for tip refinement | Produces approach and engagement waypoints. The starter's RGB images alone do not supply these metric inputs. This is geometry-based planning, not evidence of the requested action-blending method. |
| [`lift_grasped.py`](https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/transporting-objects/scripts/lift_grasped.py) | `gap`, `gap_core.types`, current end-effector pose; reads arm 0 and imposes a downward orientation | Do not transplant blindly: the arm and orientation assumptions can invalidate a bimanual mug recovery. |

The release recipe preserves orientation, chooses a retreat distance using an
optional object envelope, opens, moves away, and waits. Its reported release
flag reflects execution of that recipe; it is not proof of task completion.
Parameters such as settle steps are backend-specific and must not be copied as
equivalent durations without measuring our simulator.

## 2. GPT-Policy: useful control design, restricted source reuse

GPT-Policy drives robot tools from a fixed VLM using observations and contextual
references. It is not the same architecture as putting a supervisor around our
existing DiT policy. The published adapters target ARX, YAM, and RoboDojo.
See its [README](https://github.com/cheng-haha/GPT-Policy/blob/2ca201638e1139fe35973c8a2d209a894b389db1/README.md).

Its motion code gives a concrete meaning of interpolation:
[`sample_pose_segment`](https://github.com/cheng-haha/GPT-Policy/blob/2ca201638e1139fe35973c8a2d209a894b389db1/src/gpt_policy/motion/trajectory.py)
densifies an endpoint-defined Cartesian path, interpolating translation and
rotation, then retimes joint samples under motion limits. This is different
from predicting a replacement action or blending a VLA output with a correction.
Do not claim that the client's interpolation requirement has been resolved by
this example.

The [RoboDojo path validator](https://github.com/cheng-haha/GPT-Policy/blob/2ca201638e1139fe35973c8a2d209a894b389db1/src/gpt_policy/simulation/robodojo/control.py)
checks observation identity and validates an entire requested sequence before
submission. It separately reports measured post-execution tracking, rather than
treating a planned pose as evidence of arrival. These are useful design ideas
for our own implementation.

The [LICENSE](https://github.com/cheng-haha/GPT-Policy/blob/2ca201638e1139fe35973c8a2d209a894b389db1/LICENSE)
says redistribution/commercial licensing has not been selected. Do not vendor
this implementation into the client repository without resolving that license.
An independently implemented standard interpolation formula does not require
copying this source.

## 3. Harness VLA and RPent: closest methodological match

Harness VLA composes a frozen policy with analytic primitives and memory. Its
paper describes RGB-D grounding and staged contact-rich policy calls, including
RoboTwin experiments. Our RGB-only starter and single-task checkpoint do not
constitute a reproduction. The paper's memory-enabled, multiple-task protocol
also differs from our proposed memory-disabled four-condition pilot. See the
[paper source](https://github.com/harnessvla/harnessvla.github.io/blob/ddca453cceb7c60456d54d5f7220a6b2eb0dcfc4/HarnessVLA/example.tex).

The site's [Code link](https://github.com/harnessvla/harnessvla.github.io/blob/ddca453cceb7c60456d54d5f7220a6b2eb0dcfc4/index.html)
points to RPent. Its
[`robots/robotwin/primitives.py`](https://github.com/RLinf/RPent/blob/efc392adc98a30045d8fb83c4097917f28e20a94/robots/robotwin/primitives.py)
is especially relevant:

- `apply_qpos_updates` builds joint/gripper commands from fresh state, updating
  six joints plus a gripper for the selected arm and preserving the other arm.
- `move_to` asks the native planner for a path, handles planner failure, and
  executes joint waypoints; it returns final end-effector tracking error.
- `set_gripper` changes one gripper over multiple actions; `release` uses it.
- `lingbot_act` is model-specific: its action representation and chunk length
  must not be substituted for our client policy's interface.

This is a better reference for the missing RoboTwin motion adapter than a
generic skill description. The [RPent setup](https://github.com/RLinf/RPent/blob/efc392adc98a30045d8fb83c4097917f28e20a94/docs/source-en/rst_source/simulators/robotwin.rst)
uses a different simulator/model stack, including Python 3.11, SAPIEN 3,
RLinf and LingBot. Preserve our validated client runtime; adapt only a small,
tested interface. Its [license](https://github.com/RLinf/RPent/blob/efc392adc98a30045d8fb83c4097917f28e20a94/LICENSE)
and primitive file header require preserving Apache attribution on adapted code.

The [client-pinned native robot implementation](https://github.com/RoboTwin-Platform/RoboTwin/blob/ea8b21121ebb3cd201ff5b3fe361944ac94eda3f/envs/robot/robot.py)
already exposes `left_plan_path` / `right_plan_path`, `get_left_ee_pose` /
`get_right_ee_pose`, and both target and measured joint-state readers. The native
planner transforms a requested gripper-frame pose to its end-link target before
planning. Verify that frame convention against the selected pose reader in a
simulator smoke test. `get_*_arm_jointState` reads drive targets, whereas
`get_*_arm_real_jointState` reads articulation positions; gripper values are a
stored control proxy. Do not label target values measured arrival evidence.
The exposed point-cloud/attachment arguments are not proof that a complete scene
collision model is active; a successful planner status alone does not establish
collision-free execution in our configuration.

For a minimal library-backed prototype, adapt GaP's `release_and_retract` with
a narrow tool dispatcher and explicit arm binding. Use robot proprioception for
the starting pose, omit the unknown fixture axis, and retain the recipe's
orientation-preserving vertical retreat. Preserve and account for release,
motion and settling actions rather than silently making wait calls no-ops.
Its applicability to a particular mug failure still requires observed evidence
and separate development trials. Preserve the upstream license and mark changes
if the implementation is copied or adapted.

## Decision for our 40-episode pilot

These are project recommendations, not claims made by the cited authors:

1. Keep the four matched conditions: baseline, recovery skills, interpolation,
   and combined. Use ten held-out starting conditions after separate development
   runs, and record initialization evidence to verify matching.
2. Implement a narrow RoboTwin adapter first: camera/state validation, joint14
   actions, exact step accounting, terminal handling, and stale-chunk disposal
   after interventions. Never expose evaluator success or hidden object poses
   in the supervisor observation.
3. Use explicit skill contracts: applicable state, selected arm, bounded action
   sequence, abort conditions, completion evidence and provenance. A grasp
   release is a candidate operation, not an automatically useful recovery.
4. Before enabling a metric retreat skill, expose verified end-effector
   proprioception plus native motion planning and validate frames, arm mappings,
   joint limits and gripper conventions. If geometry comes from images, add
   calibrated depth or another validated estimation method. Do not invent metric
   targets from uncalibrated RGB or borrow hidden simulator object coordinates.
5. Declare interpolation as an explicit experimental hypothesis. If using
   action blending, define its target source, coefficient, duration, gripper
   treatment and per-step limits. Smooth transitions alone do not constitute an
   agentic correction; changing the target source changes the intervention.
6. Combined mode must have a deterministic arbitration rule. Recovery action
   sequencing and interpolation of ordinary VLA actions must not both own the
   robot at the same instant. Count every recovery movement in the same horizon.
7. Do not launch held-out episodes until development episodes demonstrate that
   each condition can execute, log its decisions, and stop correctly. A generated
   40-row schedule is preparation, not 40 completed evaluations.

For all conditions, pin the policy checkpoint, supervisor model, prompt,
controller parameters, simulator revision and configuration. Use native task
success only in evaluation accounting. Report infrastructure failures separately
from task failures and preserve the paired comparison when replacing invalid
attempts. External published success rates are not expected scores for this
pilot.
