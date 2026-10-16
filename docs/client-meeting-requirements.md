# RoboTwin: next client meeting

Client requirements relayed by the project owner on 2026-10-16:

1. Agentic supervisor evaluated on recovery skills library implementation.
2. Agentic supervisor evaluated on an interpolation implementation.
3. Agentic supervisor evaluated on a skills library + interpolation implementation.

These are the current delivery priorities. The inherited LIBERO issue queue is
historical and must not be used as the implementation backlog for this milestone.
GitHub Issues on the owner's fork were disabled when checked on 2026-10-16;
no remote issues have been deleted or closed.

## Proposed evaluation structure

Compare the three requested conditions with the unchanged RoboTwin policy as a
baseline. Keep the task, policy checkpoint, trial selection, action horizon, and
resource accounting comparable. Distinguish task success from successful setup,
recovery execution, and offline replay. Do not treat the existing two unsuccessful
baseline attempts as a statistically established success rate.

The comparison design is an engineering recommendation, not additional wording
from the client. Episode counts, deadlines, task coverage, success criteria,
supervisor model, and intervention limits still need to be established.

## Definition still required

The client has not yet defined **interpolation** in the supplied requirements.
It could describe blending policy actions with corrective targets, generating
intermediate movements, or another method. Do not silently equate it with the
existing bounded action-adjustment implementation.

The owner subsequently described the intended intuition as the supervisor
"filling in the gaps" of the VLA, possibly by predicting the next step. This is
an interpretation, not a client-provided definition. A candidate implementation
is supervisor-selected corrective targets plus bounded blending from the VLA's
proposed action; independently predicting a replacement action would instead be
correction generation. The targets, blending rule, limits, and treatment of
action chunks must be specified before choosing either interpretation.

Likewise, confirm which recovery skills are required and how the combined
condition chooses between or combines skills and interpolation. Existing
LIBERO end-effector corrections do not establish valid RoboTwin joint-space
skills. The shared supervisor remains unconnected to the current client runner.

Start with the explicit RoboTwin observation/action adapter and baseline parity
work in [the codebase map](codebase-map.md), then implement and evaluate the
confirmed conditions. Existing decisions about frozen models, evaluator
isolation, bounded interventions, and separating memory conditions remain useful
unless the new client contract explicitly changes them.
