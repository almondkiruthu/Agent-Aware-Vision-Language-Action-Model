# Historical LIBERO integration

This package retains the previous SmolVLA/LIBERO implementation and its frozen
asset lock for regression tests and reference. Active development uses
[RoboTwin](../../ROBOTWIN_SETUP.md).

Run commands from the repository root so shared harness modules are importable:

```bash
python -m legacy.libero.run_smolvla_episode --help
python -m legacy.libero.inspect_simulator_controller --help
```

Live LIBERO runs still require the separate historical environment described in
[the legacy guide](../../docs/legacy-libero.md). These modules are not imported
by the RoboTwin client runner. No compatibility shims remain at the old root
paths; update Python imports to `legacy.libero.<module>`.
