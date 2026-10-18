"""Render real SAPIEN pixels before downloading RoboTwin assets. No task claim."""
import argparse
from pathlib import Path
import numpy as np
import sapien.core as sapien

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", type=Path, default=Path("evidence/sapien-smoke.png"))
args = parser.parse_args()
engine = sapien.Engine()
renderer = sapien.SapienRenderer()
engine.set_renderer(renderer)
scene = engine.create_scene()
scene.set_ambient_light([0.5, 0.5, 0.5])
scene.add_directional_light([0, 1, -1], [1, 1, 1])
scene.add_ground(0)
builder = scene.create_actor_builder()
material = renderer.create_material()
material.set_base_color([1, 0, 0, 1])
builder.add_box_visual(half_size=[0.2, 0.2, 0.2], material=material)
actor = builder.build_kinematic()
actor.set_pose(sapien.Pose([0, 0, 0.2]))
camera = scene.add_camera("probe", 320, 240, 1.0, 0.1, 10)
camera.set_pose(sapien.Pose([-2, 0, 0.5]))
scene.step()
scene.update_render()
camera.take_picture()
rgb = np.asarray(camera.get_picture("Color"))[..., :3]
assert rgb.shape == (240, 320, 3) and np.isfinite(rgb).all()
assert float(rgb.max() - rgb.min()) > 0.05, "Renderer produced a blank image"
import imageio.v3 as iio
args.output.parent.mkdir(parents=True, exist_ok=True)
iio.imwrite(args.output, (np.clip(rgb, 0, 1) * 255).astype(np.uint8))
print(f"SAPIEN rendered pixels: {args.output}. This is not a RoboTwin episode.")
