"""RoboTwin execution seam sharing the established deadline and intervention budget.

The caller owns process termination. After any invalid outcome it must destroy
the simulator, not reuse it while a timed-out callback might still be running.
"""

import time
import traceback
from agent_vla.interventions.intervention_budget import InterventionBudget
from agent_vla.runtime.deadline import EpisodeDeadline
from .contracts import SKILLS, interpolate, vector
from .supervisor import ProviderError


def run_trial(settings, condition, policy, environment, supervisor, record, clock=time.monotonic):
    budget = InterventionBudget(settings.max_interventions,
                                {s: settings.max_interventions for s in SKILLS})
    deadline = EpisodeDeadline(settings.max_episode_seconds, clock,
                               (policy, environment, supervisor))
    result = {'status': 'invalid', 'success': None, 'actions': 0, 'interventions': 0,
              'supervisor_calls': 0, 'provider_errors': 0, 'usage_incomplete': False,
              'input_tokens': 0, 'output_tokens': 0, 'thought_tokens': 0}
    previous = None
    next_assessment = settings.assessment_interval
    try:
        observation, evaluator = deadline.call('reset', environment.reset)
        result['initial_fingerprint'] = observation.initial_fingerprint
        policy.reset()
        record('observation', environment.evidence(observation, evaluator))
        while result['actions'] < settings.action_horizon and not evaluator['success']:
            proposal = list(vector(deadline.call('policy', policy.propose, observation), 14))
            record('proposal', {'sequence': observation.sequence, 'action': proposal})
            actions, source = [proposal], 'policy'
            if (condition != 'baseline' and result['actions'] >= next_assessment
                    and result['supervisor_calls'] < settings.max_supervisor_calls
                    and budget.interventions < settings.max_interventions):
                next_assessment = result['actions'] + settings.assessment_interval
                for attempt in range(3):
                    result['supervisor_calls'] += 1
                    record('supervisor_request', {'sequence': observation.sequence,
                        'call': result['supervisor_calls'], 'attempt_for_assessment': attempt + 1})
                    try:
                        decision, usage = deadline.call('supervisor', supervisor.decide, observation,
                                                        proposal, condition, settings, previous)
                        break
                    except ProviderError as error:
                        result['provider_errors'] += 1
                        result['usage_incomplete'] = True
                        record('provider_error', {'code': error.code, 'usage_unknown': True})
                        if (error.code not in ('gemini_http_503', 'gemini_transport_error')
                                or attempt == 2 or result['supervisor_calls'] >= settings.max_supervisor_calls):
                            raise
                        deadline.call('provider_backoff', time.sleep, 5 * (attempt + 1))
                previous = observation
                for field in ('input_tokens', 'output_tokens', 'thought_tokens'):
                    result[field] += usage.get(field, 0)
                record('supervisor_response', {'sequence': observation.sequence,
                                               'decision': decision, 'usage': usage})
                if decision is not None and decision['kind'] != 'pass':
                    kind = decision['kind']
                    admission = budget.admit('recovery' if kind == 'skill' else 'adjustment',
                                             decision.get('skill'))
                    result['interventions'] = budget.interventions
                    record('intervention_admission', admission)
                    if admission['admitted']:
                        try:
                            if kind == 'skill':
                                remaining = min(settings.max_skill_actions,
                                                settings.action_horizon - result['actions'])
                                actions = deadline.call('skill_plan', environment.plan_skill,
                                                        decision, observation, remaining)
                                if not actions or len(actions) > remaining:
                                    raise ValueError('invalid skill action count')
                                actions = [list(vector(a, 14)) for a in actions]
                            else:
                                actions = [interpolate(proposal, decision, settings,
                                                       evaluator['limits'])]
                        except ValueError as error:
                            actions = [proposal]
                            record('intervention_rejected', {'reason': str(error)})
                        else:
                            # A failed reset invalidates the episode; it cannot safely
                            # fall back to an action chunk with uncertain ownership.
                            policy.reset()
                            source = kind
            for action in actions:
                deadline.check('dispatch')
                record('action_intent', {'sequence': observation.sequence,
                                         'source': source, 'action': action})
                observation, evaluator = deadline.call('step', environment.step,
                                                       observation.sequence, action)
                result['actions'] += 1
                if observation.sequence != result['actions']:
                    raise ValueError('noncontiguous simulator sequence')
                record('observation', environment.evidence(observation, evaluator))
                if evaluator['success']:
                    break
        result.update(status='completed', success=bool(evaluator['success']))
    except Exception as error:
        result['error'] = getattr(error, 'code', type(error).__name__)
        record('trial_error', {'code': result['error'], 'locations': [
            {'file': frame.filename, 'line': frame.lineno, 'function': frame.name}
            for frame in traceback.extract_tb(error.__traceback__)]})
    result['elapsed_seconds'] = clock() - deadline.started_at
    record('trial_result', result)
    return result
