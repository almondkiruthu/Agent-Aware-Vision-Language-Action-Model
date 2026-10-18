"""Observation evidence, sanitization, freshness, and ordered ingestion.

This module owns the deployable observation interface independently of episode
execution. Its current camera mapping remains the explicit main/wrist contract;
new simulator adapters must map their sensors deliberately.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Any, Literal, Mapping


@dataclass(frozen=True)
class ObservationPacket:
    """One captured observation, identified within a single episode.

    ``captured_at`` is a timezone-aware source capture time for provenance.
    ``captured_monotonic`` is sampled at capture from the same monotonic clock
    as ``run_episode``; it alone is used for durations. Sequences start at zero.
    """

    episode_id: str
    sequence: int
    captured_at: datetime
    observation: Any
    captured_monotonic: float | None = None
    frame_references: tuple[FrameReference, ...] = ()
    robot_state_capture: RobotStateCapture | None = None
    state_fields: tuple[StateField, ...] = ()


@dataclass(frozen=True)
class StateField:
    """Deployable state for one arm, timed at observation return unless verified.

    A missing measurement has no value or timestamp. ``observation_return`` is
    not a claim of sensor capture time or synchronized robot and camera clocks.
    """

    arm: str
    name: str
    frame: str
    units: str
    availability: Literal['available', 'missing']
    value: tuple[float, ...] | None
    captured_at: datetime | None
    captured_monotonic: float | None
    time_basis: Literal['observation_return'] | None


@dataclass(frozen=True)
class ViewCapture:
    """A camera capture on the packet's monotonic clock, when known."""

    observation_sequence: int
    captured_at: datetime
    captured_monotonic: float


@dataclass(frozen=True)
class RobotStateCapture:
    """Measured robot-state capture on the packet's monotonic clock."""

    observation_sequence: int
    captured_at: datetime
    captured_monotonic: float


@dataclass(frozen=True)
class FrameReference:
    """Reference to one view in an observation's ``pixels`` mapping.

    A missing view has no capture time. ``observation_return`` timestamps mark
    when the paired simulator observation returned, not camera exposure time.
    ``co_observed`` therefore does not claim measured camera synchronization.
    """

    camera: Literal['main', 'wrist']
    observation_sequence: int
    image_key: str
    captured_at: datetime | None
    captured_monotonic: float | None
    availability: Literal['available', 'missing']
    synchronization: Literal['co_observed', 'verified', 'unsynchronized',
                             'unpaired', 'unavailable']
    time_basis: Literal['observation_return', 'camera_capture'] | None


def supervisor_observation(packet: ObservationPacket) -> ObservationPacket:
    """Copy only declared deployable fields across the supervision boundary.

    Raw environment mappings belong to the policy/recorder. Unknown fields,
    including nested metadata, are omitted rather than filtered by secret names.
    Adapters must map additional sensors to this contract before exposing them.
    Numeric payloads are rebuilt as plain values, removing array/object metadata.
    """
    def measurement(value):
        if type(value) in (int, float, bool):
            return value if isfinite(value) else None
        if isinstance(value, (list, tuple)):
            items = [measurement(item) for item in value]
            return items if items and all(item is not None for item in items) else None
        if hasattr(value, 'tolist'):
            try:
                return measurement(value.tolist())
            except (TypeError, ValueError, RuntimeError):
                return None
        return None

    raw = packet.observation if isinstance(packet.observation, Mapping) else {}
    allowed = {}
    if type(raw.get('task')) is str:
        allowed['task'] = raw['task']
    pixels = raw.get('pixels')
    if isinstance(pixels, Mapping):
        allowed['pixels'] = {key: measurement(pixels[key])
                             for key in ('image', 'image2') if key in pixels}
    state = raw.get('robot_state')
    if isinstance(state, Mapping):
        clean_state = {}
        for key in ('position', 'orientation', 'joint_positions', 'joint_velocities'):
            if key in state:
                clean_state[key] = measurement(state[key])
        for group, fields in (('eef', ('pos', 'quat')),
                              ('gripper', ('qpos', 'qvel', 'closed'))):
            if isinstance(state.get(group), Mapping):
                clean_state[group] = {key: measurement(state[group][key])
                                      for key in fields if key in state[group]}
                if group == 'eef':
                    for key in ('frame', 'position_units'):
                        if type(state[group].get(key)) is str:
                            clean_state[group][key] = state[group][key]
        allowed['robot_state'] = clean_state
    def valid_capture(sequence, wall, mono):
        return (type(sequence) is int and type(wall) is datetime and
                type(mono) in (int, float) and isfinite(mono))

    # Reject malformed metadata rather than forwarding nested payloads in typed slots.
    for ref in packet.frame_references:
        if (type(ref) is not FrameReference or
            ref.camera not in ('main', 'wrist') or
            ref.image_key != ('pixels.image' if ref.camera == 'main' else 'pixels.image2') or
            type(ref.observation_sequence) is not int or
            (ref.captured_at is not None and type(ref.captured_at) is not datetime) or
            (ref.captured_monotonic is not None and
             (type(ref.captured_monotonic) not in (int, float) or
              not isfinite(ref.captured_monotonic))) or
            ref.availability not in ('available', 'missing') or
            ref.synchronization not in ('co_observed', 'verified', 'unsynchronized',
                                        'unpaired', 'unavailable') or
            ref.time_basis not in (None, 'observation_return', 'camera_capture')):
            raise ValueError('invalid supervisor camera metadata')
    # Reconstruct typed metadata rather than copying arbitrary attached attributes.
    references = tuple(FrameReference(
        ref.camera, ref.observation_sequence, ref.image_key, ref.captured_at,
        ref.captured_monotonic, ref.availability, ref.synchronization, ref.time_basis)
        for ref in packet.frame_references)
    capture = packet.robot_state_capture
    if capture is not None and (
        type(capture) is not RobotStateCapture or not valid_capture(
            capture.observation_sequence, capture.captured_at, capture.captured_monotonic)
    ):
        raise ValueError('invalid supervisor robot-state metadata')
    state_capture = (RobotStateCapture(capture.observation_sequence,
                                      capture.captured_at, capture.captured_monotonic)
                     if type(capture) is RobotStateCapture else None)
    state_fields = []
    seen = set()
    for item in packet.state_fields:
        if (type(item) is not StateField or
                any(type(text) is not str or not text for text in
                    (item.arm, item.name, item.frame, item.units)) or
                (item.arm, item.name) in seen):
            raise ValueError('invalid supervisor state field')
        seen.add((item.arm, item.name))
        if item.availability == 'missing':
            valid = all(value is None for value in (
                item.value, item.captured_at, item.captured_monotonic, item.time_basis))
        else:
            valid = (item.availability == 'available' and
                     type(item.value) is tuple and bool(item.value) and
                     all(type(value) in (int, float) and isfinite(value)
                         for value in item.value) and
                     type(item.captured_at) is datetime and
                     item.captured_at.utcoffset() is not None and
                     type(item.captured_monotonic) in (int, float) and
                     isfinite(item.captured_monotonic) and
                     item.time_basis == 'observation_return')
        if not valid:
            raise ValueError('invalid supervisor state field')
        state_fields.append(StateField(
            item.arm, item.name, item.frame, item.units, item.availability,
            item.value, item.captured_at, item.captured_monotonic, item.time_basis))
    return ObservationPacket(packet.episode_id, packet.sequence, packet.captured_at,
                             allowed, packet.captured_monotonic, references,
                             state_capture, tuple(state_fields))


def frame_references_for_observation(
    observation: Mapping[str, Any], sequence: int,
    captured_at: datetime, captured_monotonic: float,
    camera_captures: Mapping[str, ViewCapture] | None = None,
    max_skew_seconds: float | None = None,
) -> tuple[FrameReference, FrameReference]:
    """Describe LIBERO's main/wrist views without filling a missing view.

    Explicit camera capture metadata verifies association and skew. When the
    environment only supplies a paired observation, both times are the shared
    observation-return timestamp and synchronization remains unverified.
    """
    if (type(sequence) is not int or sequence < 0 or
        not isinstance(captured_at, datetime) or captured_at.utcoffset() is None or
        isinstance(captured_monotonic, bool) or
        not isinstance(captured_monotonic, (int, float)) or
        not isfinite(captured_monotonic)):
        raise ValueError('valid observation identity and timestamps required')
    if camera_captures is not None and (
        isinstance(max_skew_seconds, bool) or
        not isinstance(max_skew_seconds, (int, float)) or
        not isfinite(max_skew_seconds) or max_skew_seconds < 0
    ):
        raise ValueError('explicit camera captures require a finite skew limit')
    if not isinstance(observation, Mapping):
        raise ValueError('observation must be a mapping')
    if camera_captures is not None and set(camera_captures) - {'main', 'wrist'}:
        raise ValueError('unknown camera capture')
    pixels = observation.get('pixels')
    if not isinstance(pixels, Mapping):
        pixels = {}
    available = {camera: pixels.get(key) is not None
                 for camera, key in (('main', 'image'), ('wrist', 'image2'))}
    if camera_captures is not None:
        for camera, capture in camera_captures.items():
            if not isinstance(capture, ViewCapture) or not available[camera]:
                raise ValueError('camera capture requires a present view')
            if (type(capture.observation_sequence) is not int or
                not isinstance(capture.captured_at, datetime) or
                capture.captured_at.utcoffset() is None or
                not isinstance(capture.captured_monotonic, (int, float)) or
                isinstance(capture.captured_monotonic, bool) or
                not isfinite(capture.captured_monotonic) or
                capture.captured_monotonic > captured_monotonic or
                capture.captured_at > captured_at):
                raise ValueError('invalid camera capture metadata')
    captures = camera_captures or {}
    pair_verified = (all(available.values()) and len(captures) == 2 and
                     all(captures[camera].observation_sequence == sequence
                         for camera in ('main', 'wrist')) and
                     abs(captures['main'].captured_monotonic -
                         captures['wrist'].captured_monotonic) <= max_skew_seconds and
                     abs((captures['main'].captured_at -
                          captures['wrist'].captured_at).total_seconds()) <=
                     max_skew_seconds)
    references = []
    for camera, key in (('main', 'image'), ('wrist', 'image2')):
        if not available[camera]:
            references.append(FrameReference(camera, sequence, f'pixels.{key}',
                                             None, None, 'missing', 'unavailable', None))
            continue
        capture = captures.get(camera)
        status = ('verified' if pair_verified else
                  'unsynchronized' if camera_captures is not None else
                  'co_observed' if all(available.values()) else 'unpaired')
        references.append(FrameReference(
            camera, capture.observation_sequence if capture else sequence,
            f'pixels.{key}', capture.captured_at if capture else captured_at,
            capture.captured_monotonic if capture else captured_monotonic,
            'available', status,
            'camera_capture' if capture else 'observation_return'))
    return tuple(references)


@dataclass(frozen=True)
class InputFreshness:
    """One required input's availability and age at a decision time.

    An ``observation_return`` age is only a lower bound on sensor age, so an
    input with that time basis cannot be called fresh. ``sensor_capture``
    measures age since capture. Status does not establish valid geometry.
    """

    name: Literal['main', 'wrist', 'robot_state']
    available: bool
    age_seconds: float | None
    max_age_seconds: float
    status: Literal['fresh', 'unverified', 'missing', 'stale', 'invalid_metadata']
    diagnostic: str
    captured_monotonic: float | None
    observation_sequence: int | None
    time_basis: Literal['sensor_capture', 'observation_return'] | None


def _camera_payload_present(value: Any) -> bool:
    """Check for data without testing pixel truthiness or importing array libraries."""
    if value is None or isinstance(value, Mapping):
        return False
    if isinstance(value, (list, tuple)):
        return bool(value) and all(_camera_payload_present(v) for v in value)
    if isinstance(value, (int, float)):
        return isfinite(value)  # Zero-valued pixels are still measurements.
    try:
        shape = getattr(value, 'shape', None)
        if shape is not None:
            # len(array) alone misses zero elements on a later axis.
            return len(shape) > 0 and all(dimension > 0 for dimension in shape)
        return len(value) > 0
    except (TypeError, ValueError, RuntimeError):
        return False


def check_observation_freshness(
    packet: ObservationPacket, now_monotonic: float,
    max_age_seconds: Mapping[str, float],
) -> tuple[InputFreshness, ...]:
    """Assess configured required inputs without accepting absent data as fresh.

    Limits must name one or more of ``main``, ``wrist``, and ``robot_state``.
    A missing input has no age. An explicit capture from an older observation
    retains that older sequence and timestamp. Invalid or future metadata is
    reported as invalid, rather than being clamped to age zero.
    """
    names = ('main', 'wrist', 'robot_state')
    if not isinstance(packet, ObservationPacket) or (
        not isinstance(now_monotonic, (int, float)) or
        isinstance(now_monotonic, bool) or not isfinite(now_monotonic)
    ):
        raise ValueError('packet and finite decision time required')
    if (not isinstance(packet.captured_at, datetime) or
        packet.captured_at.utcoffset() is None or
        packet.captured_monotonic is None or
        not isinstance(packet.captured_monotonic, (int, float)) or
        isinstance(packet.captured_monotonic, bool) or
        not isfinite(packet.captured_monotonic) or
        packet.captured_monotonic > now_monotonic):
        raise ValueError('packet capture must precede the decision')
    if not isinstance(max_age_seconds, Mapping) or not max_age_seconds or (
        set(max_age_seconds) - set(names)
    ):
        raise ValueError('freshness limits require known input names')
    for limit in max_age_seconds.values():
        if (not isinstance(limit, (int, float)) or isinstance(limit, bool) or
            not isfinite(limit) or limit < 0):
            raise ValueError('freshness limits must be finite and nonnegative')

    observation = packet.observation if isinstance(packet.observation, Mapping) else {}
    pixels = observation.get('pixels')
    pixels = pixels if isinstance(pixels, Mapping) else {}
    refs = {ref.camera: ref for ref in packet.frame_references
            if isinstance(ref, FrameReference)}
    results = []
    for name in names:
        if name not in max_age_seconds:
            continue
        limit = max_age_seconds[name]
        if name == 'robot_state':
            state = observation.get('robot_state')
            def present(value: Any) -> bool:
                if value is None:
                    return False
                if isinstance(value, Mapping):
                    return bool(value) and all(present(v) for v in value.values())
                if isinstance(value, (list, tuple)):
                    return bool(value) and all(present(v) for v in value)
                if isinstance(value, bool):
                    return True
                if isinstance(value, (int, float)):
                    return isfinite(value)
                if hasattr(value, 'tolist'):
                    try:
                        return present(value.tolist())
                    except (TypeError, ValueError, RuntimeError):
                        return False
                return False
            available = isinstance(state, Mapping) and present(state)
            capture = packet.robot_state_capture
            captured = (capture.captured_monotonic if isinstance(capture, RobotStateCapture)
                        else packet.captured_monotonic if capture is None else None)
            sequence = (capture.observation_sequence if isinstance(capture, RobotStateCapture)
                        else packet.sequence if capture is None else None)
            basis = 'sensor_capture' if capture is not None else 'observation_return'
            metadata_valid = (capture is None or (
                isinstance(capture, RobotStateCapture) and
                type(capture.observation_sequence) is int and
                0 <= capture.observation_sequence <= packet.sequence and
                isinstance(capture.captured_at, datetime) and
                capture.captured_at.utcoffset() is not None and
                capture.captured_at <= packet.captured_at))
        else:
            key = 'image' if name == 'main' else 'image2'
            ref = refs.get(name)
            available = _camera_payload_present(pixels.get(key))
            captured = ref.captured_monotonic if ref is not None else None
            sequence = ref.observation_sequence if ref is not None else None
            basis = (('sensor_capture' if ref.time_basis == 'camera_capture'
                      else 'observation_return') if ref is not None and
                     ref.time_basis is not None else None)
            metadata_valid = (ref is not None and
                ref.image_key == f'pixels.{key}' and
                ref.availability == ('available' if available else 'missing') and
                type(ref.observation_sequence) is int and
                0 <= ref.observation_sequence <= packet.sequence and
                (not available or (
                    isinstance(ref.captured_at, datetime) and
                    ref.captured_at.utcoffset() is not None and
                    ref.captured_at <= packet.captured_at and
                    ref.time_basis in ('camera_capture', 'observation_return'))))
        if not available:
            status, diagnostic = 'missing', f'{name}: obtain a new observation with this input'
            age = None
            captured = None
            sequence = None
            basis = None
        elif (not metadata_valid or not isinstance(captured, (int, float)) or
              isinstance(captured, bool) or not isfinite(captured) or
              captured > packet.captured_monotonic):
            status, diagnostic = 'invalid_metadata', f'{name}: repair capture metadata before use'
            age = None
        else:
            age = now_monotonic - captured
            if age > limit:
                status = 'stale'
                diagnostic = (f'{name}: age {age:.3f}s exceeds {limit:.3f}s; '
                              'obtain a new capture')
            elif basis == 'observation_return':
                status = 'unverified'
                diagnostic = (f'{name}: sensor capture time unavailable; '
                              'obtain timestamped input before claiming freshness')
            else:
                status, diagnostic = 'fresh', f'{name}: within configured age limit'
        results.append(InputFreshness(name, available, age, limit, status,
                                      diagnostic, captured, sequence, basis))
    return tuple(results)


@dataclass(frozen=True)
class IngestionOutcome:
    accepted: bool
    code: str
    episode_id: str
    received_episode_id: str | None
    expected_sequence: int
    received_sequence: int | None


class ObservationRejected(ValueError):
    """An environment packet was rejected before it could drive a decision."""

    def __init__(self, outcome: IngestionOutcome):
        self.outcome = outcome
        super().__init__(f'observation rejected: {outcome.code}; '
                         f'expected episode {outcome.episode_id}, '
                         f'received {outcome.received_episode_id}; '
                         f'expected sequence {outcome.expected_sequence}, '
                         f'received {outcome.received_sequence}')


class ObservationIngestor:
    """Accept a contiguous, time-ordered packet stream for one episode."""

    def __init__(self, episode_id: str):
        if not isinstance(episode_id, str) or not episode_id:
            raise ValueError('episode_id must be a nonempty string')
        self.episode_id = episode_id
        self._next_sequence = 0
        self._last_capture: datetime | None = None
        self._last_monotonic_capture: float | None = None

    def ingest(self, packet: ObservationPacket,
               received_at: float | None = None) -> IngestionOutcome:
        expected = self._next_sequence
        received = packet.sequence if isinstance(packet, ObservationPacket) else None
        received_episode = packet.episode_id if isinstance(packet, ObservationPacket) else None
        code = 'accepted'
        if not isinstance(packet, ObservationPacket):
            code = 'invalid_packet'
        elif packet.episode_id != self.episode_id:
            code = 'wrong_episode'
        elif type(packet.sequence) is not int or packet.sequence < 0:
            code = 'invalid_sequence'
        elif not isinstance(packet.captured_at, datetime) or (
            packet.captured_at.utcoffset() is None
        ):
            code = 'invalid_capture_time'
        elif (packet.captured_monotonic is None or
              isinstance(packet.captured_monotonic, bool) or
              not isinstance(packet.captured_monotonic, (int, float)) or
              not isfinite(packet.captured_monotonic)):
            code = 'invalid_monotonic_capture_time'
        elif received_at is not None and packet.captured_monotonic > received_at:
            code = 'future_monotonic_capture_time'
        elif packet.sequence < self._next_sequence:
            code = 'duplicate'
        elif packet.sequence > self._next_sequence:
            code = 'out_of_order'
        elif self._last_capture is not None and packet.captured_at < self._last_capture:
            code = 'out_of_order_capture_time'
        elif (self._last_monotonic_capture is not None and
              packet.captured_monotonic < self._last_monotonic_capture):
            code = 'out_of_order_monotonic_capture_time'
        if code == 'accepted':
            self._next_sequence += 1
            self._last_capture = packet.captured_at
            self._last_monotonic_capture = packet.captured_monotonic
        return IngestionOutcome(code == 'accepted', code, self.episode_id,
                                received_episode, expected, received)
