"""Compile finite recovery plans before any simulator action is dispatched."""

from .contracts import SKILLS, vector


def compile_skill(name, arm, observation, plan_cartesian, limits, maximum=160):
    """Planner is injected; only proprioception crosses into this recipe.

    A successful native plan is not a scene-collision guarantee. This adapter
    is for simulation and requires a live frame/endpoint check before a pilot.
    """
    if name not in SKILLS or arm not in ('left', 'right'):
        raise ValueError('unknown skill or arm')
    lower, upper = (vector(x, 14) for x in limits)
    start = 0 if arm == 'left' else 7
    current = list(observation.joint_targets)
    actions = []

    def append(action):
        target = list(vector(action, 14))
        if any(not lo <= value <= hi for lo, value, hi in zip(lower, target, upper)):
            raise ValueError('skill target outside native limits')
        if len(actions) >= maximum:
            raise ValueError('complete skill exceeds action budget')
        actions.append(target)

    class Context:
        def tool(self, tool, **kwargs):
            if tool != 'robot.wait_steps' and kwargs.get('arm_id') != (0 if arm == 'left' else 1):
                raise ValueError('recipe arm mismatch')
            if tool == 'robot.open_gripper':
                initial = current[start + 6]
                for index in range(1, 5):
                    current[start + 6] = initial + (1.0 - initial) * index / 4
                    append(current)
                for _ in range(kwargs['settle_steps']): append(current)
            elif tool == 'robot.go_to_pose_cartesian':
                pose = kwargs['pose']
                target = [pose['position'][k] for k in ('x', 'y', 'z')]
                target += [pose['rotation'][k] for k in ('w', 'x', 'y', 'z')]
                path = plan_cartesian(arm, target)
                if not path:
                    raise ValueError('native planner returned no waypoints')
                for waypoint in path:
                    current[start:start + 6] = vector(waypoint, 6)
                    append(current)
            elif tool == 'robot.wait_steps':
                for _ in range(kwargs['steps']): append(current)
            else:
                raise ValueError('recipe requested an unsupported tool')
            return {'compiled': True}

    pose = observation.ee_poses[arm]
    final_pose = {'position': dict(zip(('x', 'y', 'z'), pose[:3])),
                  'rotation': dict(zip(('w', 'x', 'y', 'z'), pose[3:]))}
    context = Context()
    arm_id = 0 if arm == 'left' else 1
    if name == 'release_and_retract':
        from .vendor.release_and_retract import run
        run(context, final_pose, retract_m=.04, open_settle_steps=2,
            settle_steps=2, arm_id=arm_id)
    elif name == 'open_gripper':
        context.tool('robot.open_gripper', arm_id=arm_id, settle_steps=2)
    else:
        final_pose['position']['z'] += .04
        context.tool('robot.go_to_pose_cartesian', pose=final_pose, arm_id=arm_id)
    return actions
