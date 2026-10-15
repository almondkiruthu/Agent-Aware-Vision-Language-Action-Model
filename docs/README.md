# Documentation index

## Current RoboTwin work

- [Setup, fresh Colab walkthrough, and verified episode results](../ROBOTWIN_SETUP.md)
- [Codebase map and remaining integration work](codebase-map.md)
- [Research installation, commands, and verification](research-workflow.md)
- [Shared package architecture](architecture.md)
- [Old-to-new import migration](import-migration.md)
- [Architecture refactor verification](architecture-validation.md)
- [RoboTwin transition decision](adr/0006-use-robotwin-client-starter.md)
- [Domain vocabulary](../CONTEXT.md)

## Shared implementation reference

The following guides describe existing tested implementation. Examples and
capability assumptions may still use LIBERO; they do not establish a live
RoboTwin supervisor integration:

- [Observation-only supervision](observation-only.md)
- [Supervisor VLM interface](supervisor-vlm.md)
- [Artifact bundles](artifact-bundle.md)
- [Intervention memory](intervention-memory.md)
- [Evaluation protocol](evaluation-protocol.md)
- [Shareable reports](shareable-report.md)

## Historical evidence

- [Previous LIBERO implementation and full module reference](legacy-libero.md)
- [LIBERO startup preflight](baseline-startup.md)
- [LIBERO controller inspection](simulator-controller.md)
- [Earlier client interface questions](client-interface-handoff.md)
- [Historical AFK queue](../ralph/QUEUE.md)

Historical results, client planning documents, and ADRs are retained for
provenance. In particular, the earlier LIBERO-first sequence is superseded by
the client's RoboTwin starter; earlier deployment dates and issue numbers are
not current commitments.
