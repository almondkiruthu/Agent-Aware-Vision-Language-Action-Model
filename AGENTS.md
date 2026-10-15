## Agent skills

### Runtime and migration

Start RoboTwin work with `ROBOTWIN_SETUP.md` and `docs/codebase-map.md`.
The previous simulator implementation is in `legacy/libero/`; shared root
modules are not yet integrated with the RoboTwin runner. Run offline regression
checks with `python -m unittest discover -s tests`.

### Issue tracker

For issue tracking and current fork availability, see `docs/agents/issue-tracker.md`.

### Triage labels

Use the five default triage labels. See `docs/agents/triage-labels.md`.

### Domain docs

Use a single-context layout: root `CONTEXT.md` and `docs/adr/`. See `docs/agents/domain.md`.

### Unattended issue work

For an AFK coding run, use `bash ralph/afk.sh <issue-target>` and follow
`ralph/README.md` and `ralph/prompt.md`.
