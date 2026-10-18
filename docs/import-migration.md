# Import migration

The shared implementation now installs as `agent-vla` and imports as `agent_vla`.
Install with `python -m pip install -e ".[dev]"` before using scripts or tests.
Root-module imports are intentionally removed; update downstream notebooks with this table.
The original RoboTwin starter and its environments remain separate.

| Previous module | New module |
| --- | --- |
| `action_capabilities` | `agent_vla.interventions.action_capabilities` |
| `adaptation_memory` | `agent_vla.memory.adaptation_memory` |
| `artifact_bundle` | `agent_vla.evidence.artifact_bundle` |
| `artifact_finalization` | `agent_vla.evidence.artifact_finalization` |
| `attempt_identity` | `agent_vla.evidence.attempt_identity` |
| `baseline_fallback` | `agent_vla.runtime.baseline_fallback` |
| `camera_evidence` | `agent_vla.observations.camera_evidence` |
| `correction_expiry` | `agent_vla.interventions.correction_expiry` |
| `correction_validation` | `agent_vla.interventions.correction_validation` |
| `decision_memory` | `agent_vla.memory.decision_memory` |
| `detector_metrics` | `agent_vla.evaluation.detector_metrics` |
| `development_annotations` | `agent_vla.memory.development_annotations` |
| `development_memory` | `agent_vla.memory.development_memory` |
| `end_effector_progress` | `agent_vla.observations.end_effector_progress` |
| `environment_interruption` | `agent_vla.runtime.interruption` |
| `episode_deadline` | `agent_vla.runtime.deadline` |
| `episode_harness` | `agent_vla.runtime.harness` |
| `episode_timeline` | `agent_vla.evidence.timeline` |
| `evaluation_acceptance` | `agent_vla.evaluation.acceptance` |
| `evaluation_allocation` | `agent_vla.evaluation.allocation` |
| `evaluation_clusters` | `agent_vla.evaluation.clusters` |
| `evaluation_operations` | `agent_vla.evaluation.operations` |
| `evaluation_outcomes` | `agent_vla.evaluation.outcomes` |
| `evaluation_preflight` | `agent_vla.evaluation.preflight` |
| `evaluation_protocol` | `agent_vla.evaluation.protocol` |
| `evaluation_replacement` | `agent_vla.evaluation.replacement` |
| `evaluation_resume` | `agent_vla.evaluation.resume` |
| `evaluation_schedule` | `agent_vla.evaluation.schedule` |
| `execution_failure` | `agent_vla.runtime.execution_failure` |
| `execution_progress` | `agent_vla.evidence.journal` |
| `fixed_memory` | `agent_vla.memory.fixed_memory` |
| `frozen_runtime` | `agent_vla.runtime.frozen_runtime` |
| `gripper_transitions` | `agent_vla.observations.gripper_transitions` |
| `intervention_budget` | `agent_vla.interventions.intervention_budget` |
| `intervention_memory` | `agent_vla.memory.intervention_memory` |
| `memory_correction` | `agent_vla.memory.memory_correction` |
| `memory_snapshot` | `agent_vla.memory.memory_snapshot` |
| `model_usage` | `agent_vla.runtime.model_usage` |
| `observation_contract` | `agent_vla.observations.contracts` |
| `observation_only` | `agent_vla.runtime.observation_only` |
| `observation_window` | `agent_vla.observations.window` |
| `policy_adapter` | `agent_vla.runtime.policy_adapter` |
| `recorded_replay` | `agent_vla.evidence.replay` |
| `recovery_eligibility` | `agent_vla.supervision.recovery_eligibility` |
| `recovery_monitor` | `agent_vla.interventions.recovery_monitor` |
| `recovery_registry` | `agent_vla.interventions.recovery_registry` |
| `reopen_retreat` | `agent_vla.interventions.reopen_retreat` |
| `repeated_proposals` | `agent_vla.observations.repeated_proposals` |
| `replay_adapters` | `agent_vla.evidence.adapters` |
| `robot_state_evidence` | `agent_vla.observations.robot_state_evidence` |
| `shareable_report` | `agent_vla.evidence.shareable_report` |
| `single_action_adjustment` | `agent_vla.interventions.single_action_adjustment` |
| `supervisor_adjustment` | `agent_vla.supervision.adjustment` |
| `supervisor_eligibility` | `agent_vla.supervision.eligibility` |
| `supervisor_identity` | `agent_vla.supervision.identity` |
| `supervisor_provider` | `agent_vla.supervision.provider` |
| `supervisor_recovery` | `agent_vla.supervision.recovery` |
| `supervisor_replay` | `agent_vla.supervision.replay` |
| `supervisor_response` | `agent_vla.supervision.response` |
| `supervisor_retry` | `agent_vla.supervision.retry` |
| `supervisor_vlm` | `agent_vla.supervision.vlm` |
| `temporal_diagnosis` | `agent_vla.supervision.temporal_diagnosis` |
| `temporal_persistence` | `agent_vla.supervision.temporal_persistence` |
| `translation_conversion` | `agent_vla.interventions.translation_conversion` |
| `visual_change` | `agent_vla.observations.visual_change` |

Observation types, filtering, freshness, and ingestion formerly imported from `episode_harness` now belong to `agent_vla.observations.contracts`.
