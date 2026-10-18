# Architecture refactor verification — 2026-10-16

Verified locally on Windows with Python 3.13.12 in `.venv`.

| Check | Result |
| --- | --- |
| Offline regression suite | 591 tests passed, including the 587 existing tests and 4 installed-command/import tests |
| Artifact command coverage after final command update | 6 artifact-bundle tests passed through `agent-vla verify-bundle` |
| Distribution | Built `agent_vla-0.1.0-py3-none-any.whl`; installed it without dependencies in a temporary environment outside the checkout |
| Installed imports | All 73 discovered modules imported; no NumPy, Torch, SAPIEN, or LeRobot loaded |
| Installed command | Replayed the sealed two-step fixture from outside the checkout; preserved unsuccessful outcome and diagnostic-only scope |
| Observation extraction | Observation definitions and function bodies preserved; observation imports do not load the episode loop |
| Implementation preservation | AST comparison of all 64 prior modules found no implementation changes beyond imports and observation extraction |
| Runnable example | Recorded, sealed, replayed, and rendered the two-step synthetic CPU episode |
| Legacy command | Relocated LIBERO runner help succeeds after shared-package installation |
| Client provenance | All ten original starter file hashes match the manifest |
| Static checks | Python compilation, Python 3.10 syntax parsing, Bash syntax, and maintained local documentation links passed |

The initial full run found stale subprocess commands in tests after root modules
moved; those commands now use installed module entry points. The subsequent full
suite passed. Source schemas, replay fixture bytes, and the client runner were
preserved.

CI is configured for Windows and Linux with Python 3.10 and 3.13, including the
built-wheel check. Hosted CI and Python 3.10 runtime execution have not been
verified in this local refactor. No new GPU episode or live supervisor request
was run. The synthetic example is not evidence of RoboTwin task performance.
