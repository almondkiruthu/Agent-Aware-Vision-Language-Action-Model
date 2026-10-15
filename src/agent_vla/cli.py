"""Discoverable offline evidence commands; no simulator or model loading."""

import argparse
import json
from pathlib import Path


def main(argv=None):
    """Run an evidence command; return a process exit status."""
    parser = argparse.ArgumentParser(description=__doc__, prog="agent-vla")
    commands = parser.add_subparsers(dest="command", required=True)
    replay = commands.add_parser("replay", help="Validate and replay a sealed trace")
    replay.add_argument("directory", type=Path)
    verify = commands.add_parser("verify-bundle", help="Verify the full artifact inventory")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--replay", action="store_true", help="Also execute deterministic replay")
    timeline = commands.add_parser("timeline", help="Render a trace as a local HTML timeline")
    timeline.add_argument("directory", type=Path)
    timeline.add_argument("output", type=Path, help="New HTML file; existing files are refused")
    args = parser.parse_args(argv)

    from agent_vla.evidence.replay import TraceError, load_recorded_replay

    try:
        if args.command == "replay":
            result = load_recorded_replay(args.directory).report()
        elif args.command == "verify-bundle":
            from agent_vla.evidence.artifact_bundle import verify_artifact_bundle

            verified = verify_artifact_bundle(args.directory)
            result = {"verified": True, "episode_id": verified.source_episode_id,
                      "replayed": verified.run().steps if args.replay else None}
        else:
            from agent_vla.evidence.timeline import render_episode_timeline

            report = render_episode_timeline(args.directory)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(report)
            result = {"output": str(args.output.resolve())}
    except (TraceError, OSError) as exc:
        parser.exit(1, f"Evidence unavailable: {exc}\n")
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0
