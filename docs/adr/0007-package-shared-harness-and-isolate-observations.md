---
status: accepted
---

# Package the shared harness and isolate observation handling

Use an installable `src/agent_vla` package with explicit domain imports, and move
observation validation, filtering, freshness, and ingestion out of episode
execution so sensor consumers do not depend on the execution loop. Remove old
root import paths and document their migration rather than retain a second
public import surface; preserve trace schemas and behavioral regression tests.
Keep the client RoboTwin runner and historical LIBERO integration outside the
distribution because their simulator dependencies and action semantics are
distinct; this decision does not imply RoboTwin supervisor integration.
