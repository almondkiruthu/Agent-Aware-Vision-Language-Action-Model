"""Probe the actual host before installing the large simulator stack."""
import argparse
import json
import platform
import shutil
import subprocess
from pathlib import Path


def probe(command):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=45)
        return {"returncode": result.returncode, "output": (result.stdout + result.stderr).strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"returncode": -1, "output": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("evidence/preflight.json"))
    parser.add_argument("--vulkaninfo", default="vulkaninfo")
    args = parser.parse_args()
    gpu = probe(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"])
    vulkan = probe([args.vulkaninfo, "--summary"])
    # CUDA visibility alone is insufficient. Require an NVIDIA Vulkan driver.
    nvidia_vulkan = vulkan["returncode"] == 0 and "DRIVER_ID_NVIDIA_PROPRIETARY" in vulkan["output"]
    linux = platform.system() == "Linux"
    wsl = "microsoft" in platform.release().lower()
    report = {
        "platform": platform.platform(), "wsl": wsl,
        "free_disk_gib": round(shutil.disk_usage(Path.cwd()).free / 2**30, 1),
        "gpu": gpu, "vulkan": vulkan,
        "nvidia_vulkan": nvidia_vulkan,
        "host_gate_passed": linux and not wsl and gpu["returncode"] == 0 and nvidia_vulkan,
        "note": "Host gate only; SAPIEN render smoke and full episode must still pass."
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["host_gate_passed"] else 2)


if __name__ == "__main__":
    main()
