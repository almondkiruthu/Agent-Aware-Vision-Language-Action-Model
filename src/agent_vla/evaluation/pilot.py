"""Matched RoboTwin pilot plans and honest accounting of incomplete evaluations."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import sqrt
from pathlib import Path


CONDITIONS = ('baseline', 'skills', 'interpolation', 'combined')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                             separators=(',', ':')).encode()).hexdigest()


@dataclass(frozen=True)
class PilotSettings:
    seeds: tuple[int, ...] = tuple(range(100, 110))
    action_horizon: int = 1200
    assessment_interval: int = 120
    max_supervisor_calls: int = 10
    max_interventions: int = 3
    max_skill_actions: int = 160
    max_episode_seconds: int = 1800
    interpolation_alpha: float = 0.25
    max_joint_delta: float = 0.15
    memory: str = 'disabled'
    task: str = 'hanging_mug'

    def __post_init__(self):
        object.__setattr__(self, 'seeds', tuple(self.seeds))
        if (not self.seeds or len(set(self.seeds)) != len(self.seeds)
                or any(type(s) is not int or s < 0 for s in self.seeds)):
            raise ValueError('unique nonnegative integer seeds required')
        for key in ('action_horizon', 'assessment_interval', 'max_supervisor_calls',
                    'max_interventions', 'max_skill_actions', 'max_episode_seconds'):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f'{key} must be a positive integer')
        if self.memory != 'disabled' or self.task != 'hanging_mug':
            raise ValueError('this pilot freezes memory off and uses hanging_mug')
        if (type(self.interpolation_alpha) not in (int, float)
                or not 0 < self.interpolation_alpha <= 1
                or type(self.max_joint_delta) not in (int, float)
                or not 0 < self.max_joint_delta <= 0.15):
            raise ValueError('bounded interpolation settings required')


def make_plan(settings, runtime_identity, supervisor_identity):
    """Rotate condition order; each seed occurs once under every condition.

    Seeds declare intended matching. Observed reset fingerprints establish
    whether matching actually occurred; they must be checked at analysis time.
    """
    if not runtime_identity or not supervisor_identity:
        raise ValueError('explicit runtime and supervisor identity required')
    trials = []
    for index, seed in enumerate(settings.seeds):
        offset = index % len(CONDITIONS)
        order = CONDITIONS[offset:] + CONDITIONS[:offset]
        for condition in order:
            trials.append({'trial_id': f'seed-{seed:05d}-{condition}',
                           'seed': seed, 'condition': condition})
    body = {'schema': 'robotwin-pilot-v1', 'settings': asdict(settings),
            'runtime': runtime_identity, 'supervisor': supervisor_identity,
            'trials': trials, 'scope': 'exploratory_pilot',
            'interpolation_definition': 'bounded_joint_delta_blend_v1',
            'interpolation_client_confirmed': False}
    return dict(body, plan_sha256=fingerprint(body))


def validate_plan(plan):
    supplied = dict(plan)
    digest = supplied.pop('plan_sha256', None)
    if digest != fingerprint(supplied):
        raise ValueError('plan fingerprint mismatch')
    settings = PilotSettings(**plan['settings'])
    expected = make_plan(settings, plan['runtime'], plan['supervisor'])
    if fingerprint(expected) != fingerprint(plan):
        raise ValueError('plan structure or allocation changed')
    return settings


def write_plan(path, plan):
    validate_plan(plan)
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(plan, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def summarize(plan, results):
    """Do not count infrastructure errors or missing runs as robot failures."""
    validate_plan(plan)
    allocation = {row['trial_id']: row for row in plan['trials']}
    seen = {}
    groups = {name: {'planned': 0, 'completed': 0, 'successes': 0,
                     'invalid': 0, 'missing': 0, 'input_tokens': 0,
                     'output_tokens': 0, 'thought_tokens': 0, 'supervisor_calls': 0,
                     'provider_errors': 0, 'usage_incomplete': False,
                     'actions': 0, 'interventions': 0}
              for name in CONDITIONS}
    for trial in allocation.values():
        groups[trial['condition']]['planned'] += 1
    for row in results:
        trial_id = row.get('trial_id')
        if trial_id not in allocation or trial_id in seen:
            raise ValueError('unknown or duplicate trial result')
        trial = allocation[trial_id]
        if row.get('plan_sha256') != plan['plan_sha256'] or any(
                row.get(k) != trial[k] for k in ('seed', 'condition')):
            raise ValueError('result does not belong to the frozen plan')
        if row.get('status') not in ('completed', 'invalid'):
            raise ValueError('unsupported result status')
        seen[trial_id] = row
        group = groups[trial['condition']]
        if row['status'] == 'invalid':
            group['invalid'] += 1
        else:
            if type(row.get('success')) is not bool or not row.get('initial_fingerprint'):
                raise ValueError('completed result requires outcome and reset evidence')
            if type(row.get('actions')) is not int or not 0 <= row['actions'] <= plan['settings']['action_horizon']:
                raise ValueError('invalid action accounting')
            group['completed'] += 1
            group['successes'] += row['success']
        group['usage_incomplete'] |= bool(row.get('usage_incomplete') or row.get('accounting_incomplete'))
        for field in ('input_tokens', 'output_tokens', 'thought_tokens', 'supervisor_calls',
                      'provider_errors', 'actions', 'interventions'):
            value = row.get(field, 0)
            if type(value) is not int or value < 0:
                raise ValueError('invalid resource accounting')
            group[field] += value
    matching = []
    for seed in plan['settings']['seeds']:
        rows = [seen[t['trial_id']] for t in allocation.values()
                if t['seed'] == seed and t['trial_id'] in seen]
        complete = len(rows) == 4 and all(r['status'] == 'completed' for r in rows)
        matched = complete and len({r['initial_fingerprint'] for r in rows}) == 1
        matching.append({'seed': seed, 'complete': complete, 'matched_reset': matched})
    for group in groups.values():
        group['missing'] = group['planned'] - group['completed'] - group['invalid']
        group['observed_success_rate'] = (group['successes'] / group['completed']
                                          if group['completed'] else None)
        n = group['completed']
        if n:
            p, z = group['successes'] / n, 1.959963984540054
            denominator = 1 + z*z/n
            center = (p + z*z/(2*n)) / denominator
            half = z * sqrt(p*(1-p)/n + z*z/(4*n*n)) / denominator
            group['wilson_95_interval'] = [max(0., center-half), min(1., center+half)]
        else:
            group['wilson_95_interval'] = None
    paired = {}
    for condition in CONDITIONS[1:]:
        pairs = []
        for match in matching:
            if match['matched_reset']:
                seed = match['seed']
                baseline = seen[f'seed-{seed:05d}-baseline']['success']
                assisted = seen[f'seed-{seed:05d}-{condition}']['success']
                pairs.append((baseline, assisted))
        paired[condition] = {'matched_seeds': len(pairs),
                             'assisted_only_success': sum(b and not a for a,b in pairs),
                             'baseline_only_success': sum(a and not b for a,b in pairs),
                             'both_success': sum(a and b for a,b in pairs),
                             'neither_success': sum(not a and not b for a,b in pairs)}
    return {'plan_sha256': plan['plan_sha256'], 'conditions': groups,
            'paired_comparisons': paired,
            'paired_resets': matching, 'complete_matched_pilot': all(r['matched_reset'] for r in matching),
            'scope': 'exploratory_pilot', 'population_improvement_established': False}
