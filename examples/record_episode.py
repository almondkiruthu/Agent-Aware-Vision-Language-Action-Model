"""Record and replay a synthetic CPU episode; this is not a robot benchmark."""

import argparse
import json

from agent_vla.evidence.adapters import successful_replay
from agent_vla.evidence.replay import TraceRecorder, load_recorded_replay
from agent_vla.runtime.harness import run_episode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New trace directory, never overwritten")
    args = parser.parse_args()
    fixture = successful_replay()
    trace = TraceRecorder(args.output, fixture.config, fixture.recorder)
    outcome = run_episode(fixture.config, fixture.policy, fixture.environment, trace)
    trace.seal(outcome)
    print(json.dumps(load_recorded_replay(args.output).report(), sort_keys=True))


if __name__ == "__main__":
    main()
