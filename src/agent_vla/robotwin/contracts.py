"""Three-camera evidence and joint-target decisions, without evaluator leakage."""

from dataclasses import dataclass
from math import isfinite
from agent_vla.evaluation.pilot import CONDITIONS


CAMERAS = ('head_camera', 'left_camera', 'right_camera')
SKILLS = ('open_gripper', 'retreat_up', 'release_and_retract')


def vector(value, size):
    if not isinstance(value, (list, tuple)) or len(value) != size or any(
            type(v) not in (int, float) or not isfinite(v) for v in value):
        raise ValueError(f'{size} finite numeric values required')
    return tuple(float(v) for v in value)


@dataclass(frozen=True)
class Observation:
    sequence: int
    images: dict[str, bytes | None]
    joint_targets: tuple[float, ...]
    measured_joints: tuple[float, ...]
    ee_poses: dict[str, tuple[float, ...]]
    initial_fingerprint: str

    def __post_init__(self):
        if type(self.sequence) is not int or self.sequence < 0 or set(self.images) != set(CAMERAS):
            raise ValueError('sequence and all camera availability slots required')
        if any(v is not None and (type(v) is not bytes or not v.startswith(b'\x89PNG\r\n\x1a\n'))
               for v in self.images.values()):
            raise ValueError('PNG images or explicit missing cameras required')
        vector(self.joint_targets, 14)
        vector(self.measured_joints, 12)
        if set(self.ee_poses) != {'left', 'right'}:
            raise ValueError('both proprioceptive end-effector poses required')
        for pose in self.ee_poses.values():
            vector(pose, 7)

    def metadata(self):
        # This is the complete supervisor allowlist. Reset fingerprints and
        # evaluator outcomes never cross this seam.
        return {'sequence': self.sequence, 'joint_targets': list(self.joint_targets),
                'measured_arm_joints': list(self.measured_joints),
                'end_effector_poses_xyz_wxyz': self.ee_poses,
                'cameras': {k: 'available' if v is not None else 'missing'
                            for k, v in self.images.items()},
                'gripper_state_basis': 'command_target_not_measured_contact'}


def validate_decision(response, condition, sequence, settings):
    if condition not in CONDITIONS or condition == 'baseline':
        raise ValueError('baseline cannot request supervisor decisions')
    if (type(response) is not dict or type(response.get('sequence')) is not int
            or response.get('sequence') != sequence):
        raise ValueError('decision observation identity mismatch')
    kind = response.get('kind')
    common = {'sequence', 'kind', 'reason', 'evidence'}
    extra = {'pass': set(), 'skill': {'arm', 'skill'},
             'interpolate': {'arm', 'joint_delta'}}
    if kind not in extra or set(response) != common | extra[kind]:
        raise ValueError('decision shape is not an allowed structured request')
    if type(response['reason']) is not str or not 0 < len(response['reason']) <= 1000:
        raise ValueError('bounded reason text required')
    evidence = response['evidence']
    if type(evidence) is not list or len(evidence) > 6:
        raise ValueError('bounded evidence list required')
    for item in evidence:
        if (type(item) is not dict or set(item) != {'camera', 'detail'}
                or item['camera'] not in CAMERAS
                or type(item['detail']) is not str or not 0 < len(item['detail']) <= 500):
            raise ValueError('camera-grounded evidence required')
    if kind == 'pass':
        return dict(response)
    if not evidence or response['arm'] not in ('left', 'right'):
        raise ValueError('corrections require evidence and an explicit arm')
    if kind == 'skill':
        if condition not in ('skills', 'combined') or response['skill'] not in SKILLS:
            raise ValueError('skill is not enabled')
    else:
        if condition not in ('interpolation', 'combined'):
            raise ValueError('interpolation is not enabled')
        delta = vector(response['joint_delta'], 6)
        if any(abs(v) > settings.max_joint_delta for v in delta):
            raise ValueError('joint delta exceeds the configured envelope')
    return dict(response)


def interpolate(proposal, decision, settings, limits):
    """Blend toward a bounded delta target; preserve both gripper commands."""
    if decision.get('arm') not in ('left', 'right'):
        raise ValueError('explicit arm required')
    action = list(vector(proposal, 14))
    lower, upper = (vector(x, 14) for x in limits)
    if any(lo >= hi for lo, hi in zip(lower, upper)):
        raise ValueError('invalid joint limits')
    start = 0 if decision['arm'] == 'left' else 7
    for i, delta in enumerate(vector(decision['joint_delta'], 6)):
        if abs(delta) > settings.max_joint_delta:
            raise ValueError('joint delta outside envelope')
        action[start + i] += settings.interpolation_alpha * delta
    if any(not lo <= value <= hi for lo, value, hi in zip(lower, action, upper)):
        raise ValueError('interpolated target outside native joint limits')
    return action
