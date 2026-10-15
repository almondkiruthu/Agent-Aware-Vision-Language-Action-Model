"""Download the exact public checkpoint supplied by the client, without a token."""
import json
import os
from pathlib import Path
# Standard HTTPS avoids stalled Xet transfers on restricted networks.
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")
from huggingface_hub import snapshot_download

root = Path(__file__).resolve().parents[1]
pins = json.loads((root / "setup/pins.json").read_text())
snapshot_download(
    repo_id=pins["checkpoint_repo"], revision=pins["checkpoint_revision"],
    local_dir=root / "weights", token=False, max_workers=2,
)
required = ["config.json", "model.safetensors", "policy_preprocessor.json",
            "policy_postprocessor.json", "tokenizer/tokenizer.json"]
for name in required:
    if not (root / "weights" / name).is_file():
        raise SystemExit(f"Missing checkpoint component: {name}")
print(f"Checkpoint downloaded and required files present: {root / 'weights'}")
