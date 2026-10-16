# open-robot-skills attribution

`release_and_retract.py` is from graph-robots/open-robot-skills, revision
752dfbd96968d4d08379f8111765efbf6457800b, path
skills/executing-feature-mating/scripts/release_and_retract.py.

Source: https://github.com/graph-robots/open-robot-skills/blob/752dfbd96968d4d08379f8111765efbf6457800b/skills/executing-feature-mating/scripts/release_and_retract.py

License: Apache-2.0, reproduced in OPEN_ROBOT_SKILLS_LICENSE.
Modification on 2026-10-16: postpone annotations and move the GaP type-only
import under TYPE_CHECKING; move the NumPy import into run. The recipe's
algorithm is unchanged. NumPy is imported only when the optional recipe is
used. No GaP runtime is installed.

Our adapter compiles the recipe into a bounded plan. It uses current robot
proprioception, explicit arm, 0.04 m upward retreat, two gripper-settle actions,
and two final hold actions. These action counts are our RoboTwin parameters,
not equivalent durations to the original backend's defaults. The recipe's
`released` flag is never used as task success or measured grasp evidence.
