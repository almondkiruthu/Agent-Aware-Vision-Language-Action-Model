---
status: accepted
---

# Use the client RoboTwin starter as the active baseline

On 2026-10-15 the client-directed transition replaced the LIBERO-first sequence
in ADR 0003 with the supplied RoboTwin `hanging_mug` runner and public checkpoint,
verified on Colab L4. Keep the original starter unchanged and isolate the old
LIBERO integration under `legacy/libero`, preserving shared harness, supervision,
recording, memory, evaluation code, and regression evidence while their adapters
are reviewed. RoboTwin's bimanual joint targets require explicit new capability
and observation mappings; LIBERO corrections and evaluation task allocations
do not transfer automatically.
