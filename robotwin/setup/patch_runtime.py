"""Apply the client's two documented patches, failing on unexpected source."""
from pathlib import Path
import mplib

planner = Path(mplib.__file__).parent / "planner.py"
old = "if np.linalg.norm(delta_twist) < 1e-4 or collide or not within_joint_limit:"
new = "if np.linalg.norm(delta_twist) < 1e-4 or not within_joint_limit:"
text = planner.read_text()
if old in text:
    planner.write_text(text.replace(old, new))
elif new not in text:
    raise SystemExit("mplib source differs; inspect before patching")

base = Path(__file__).resolve().parents[1] / "RoboTwin/envs/_base_task.py"
old = 'set_ray_tracing_denoiser("oidn")'
new = 'set_ray_tracing_denoiser("none")'
text = base.read_text()
if old in text:
    base.write_text(text.replace(old, new))
elif new not in text:
    raise SystemExit("SAPIEN denoiser call differs; inspect before patching")
print("Client patches applied; camera shader remains unchanged.")
