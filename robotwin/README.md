# Supervising a manipulation policy with an agent

A trained policy, a simulator, and one script that runs them together. The policy
hangs a mug on a rack. It usually fails. Your job is to work out how an agent can
watch it and step in.

## What you are given

A **multi-task diffusion transformer** trained for 50,000 steps on
[RoboTwin 2.0](https://robotwin-platform.github.io), a bimanual benchmark on the
SAPIEN simulator. The robot is an Aloha-AgileX: two 7-DOF arms, 14 joints total,
three cameras (one on the torso, one on each wrist).

On the `hanging_mug` task it succeeds **about 6% of the time** over 50 episodes.

That number is the point. The policy is not broken — watch it move and you will
see competent, purposeful motion. It reaches, it orients, it closes on the mug.
Then something small goes wrong and the whole attempt is lost.

### Three attempts, none successful

| | | |
|---|---|---|
| ![attempt 1](videos/attempt_1.gif) | ![attempt 2](videos/attempt_2.gif) | ![attempt 3](videos/attempt_3.gif) |

Full-length clips are in [`videos/`](videos/) (40 s each, head camera).

Watch for the pattern: early phases look fine, late phases drift. A grasp closes
slightly off-centre and never recovers. The arm approaches the rack at an angle
that was never going to work. Nothing announces the failure — the policy keeps
going confidently until the episode runs out.

This is what makes the problem interesting. A 6% success rate from a policy that
is *mostly* doing the right thing is a different problem from a policy that has
learned nothing.

## The idea

The policy emits an action every control step and never reconsiders. It cannot
tell a good grasp from a bad one, and it has no notion of having gone wrong.

An agent watching the same images might. It sees what you see. It could notice
the mug slipping, or the approach angle being wrong, or the arm stalling in a
corner, and do something about it — retry a phase, nudge a pose, back off and
re-approach, or just stop a doomed attempt early.

How any of that works is yours to design. What counts as "struggling", how the
agent decides, what it is allowed to change, how often it looks — all open.

## How it fits together

One hook, called every control step, after the policy has chosen and before the
robot moves:

```python
def supervise(step, images, state, action):
    """
    images   {"head_camera": HxWx3 uint8, "left_camera": ..., "right_camera": ...}
    state    14 joint positions, left arm then right arm
    action   14 joint targets the policy chose

    Return the action to execute.
    """
    return action
```

Return `action` unchanged and the policy drives. Return something else and you
have taken over. That is the whole interface — everything else in
`run_inference.py` is plumbing you can rewrite or throw away.

Some directions worth considering, none of them required:

- Call an agent every N steps rather than every step; a vision-language model is
  far slower than a 30 Hz control loop, so something has to give
- Give the agent episode memory, so it can compare now against ten steps ago
- Let it act at a higher level than joint targets — "open the gripper", "lift
  10 cm", "go back to the pre-grasp pose"
- Detect failure early and end the episode rather than running the clock out

## Setup

The simulator and the policy need **incompatible versions of numpy** — RoboTwin's
motion planner (`mplib`) requires numpy 1.x and segfaults on 2.x, while the
policy stack requires numpy 2.x. They cannot share a process. So there are two
environments, and the script runs in one role or the other.

### 1. Simulator environment (python 3.10)

```bash
conda create -n robotwin python=3.10 -y && conda activate robotwin
pip install -r requirements-sim.txt
```

Then RoboTwin itself:

```bash
git clone --recurse-submodules https://github.com/RoboTwin-Platform/RoboTwin.git
cd RoboTwin
bash scripts/_download_assets.sh      # ~16 GB, takes a while
python scripts/update_embodiment_config_path.py
```

And CuRobo, which RoboTwin imports unconditionally. This step compiles CUDA
kernels, so before you start:

- A **CUDA toolkit with headers**, not just `nvcc`. The build fails on
  `fatal error: cuda_runtime_api.h: No such file or directory` if you only have
  the compiler. Its major version must match your torch build — torch 2.8 ships
  cu128, so CUDA 12.x. Set `CUDA_HOME` such that
  `$CUDA_HOME/include/cuda_runtime_api.h` exists.
- **gcc 13 or newer.** gcc 12 miscompiles torch's headers and fails with a
  confusing `need 'typename' before ...` on a line that already has it.

The CuRobo version matters too: newer releases moved the package layout and will
not import.

```bash
git clone --branch v0.7.8 --depth 1 https://github.com/NVlabs/curobo.git envs/curobo
pip install -e envs/curobo --no-build-isolation
pip install warp-lang==1.12.0
```

Two patches you will probably need. Both are one-liners, both bit us:

```bash
# mplib: a collision check that rejects valid plans
sed -i 's/ or collide//g' $(python -c "import mplib,pathlib;print(pathlib.Path(mplib.__file__).parent/'planner.py')")

# SAPIEN: the OIDN denoiser fails on many drivers and the renderer then stops responding
sed -i 's/set_ray_tracing_denoiser("oidn")/set_ray_tracing_denoiser("none")/' envs/_base_task.py
```

If rendering hangs after a few hundred steps, your driver cannot sustain SAPIEN's
ray tracing. Switch to the rasteriser in `envs/_base_task.py`:

```python
sapien.render.set_camera_shader_dir("default")   # instead of "rt"
```

It is stable and about twice as fast. Images look flatter than the training data,
which costs some success rate, so prefer ray tracing if your GPU tolerates it.

A GPU with working **NVIDIA Vulkan** is required. Check with
`vulkaninfo --summary` — you want a line naming your GPU, not `llvmpipe`. Most
datacenter GPUs in containers do not have it; desktop NVIDIA cards do.

### 2. Policy environment (python 3.12)

```bash
conda create -n policy python=3.12 -y && conda activate policy
pip install -r requirements-policy.txt
```

### 3. Weights

Put the checkpoint directory (the one containing `model.safetensors` and
`config.json`) somewhere and point `--weights` at it.

## Running

Two terminals.

```bash
conda activate robotwin
python run_inference.py sim --robotwin-root ./RoboTwin
```

```bash
conda activate policy
python run_inference.py policy --weights ./weights --episodes 10
```

You get a video per episode in `videos/` and a success rate at the end.

```
success at step 743
episode 3/10 (seed 2): 1 successes so far
...
success rate: 10% (1/10)
```

Useful flags: `--seed` (the scene; same seed means same starting layout),
`--steps` (default 1200, about 40 s), `--episodes`, `--task` (any of RoboTwin's
50 tasks, though the weights were trained with `hanging_mug` among them).

## Measuring whether you helped

The baseline is **6% on `hanging_mug` over 50 episodes**. Compare against that,
over enough episodes to mean something — at a 6% base rate, ten episodes tells
you almost nothing, and a jump from 1/10 to 2/10 is noise.

Worth reporting alongside success rate:

- How often the agent intervened, and whether interventions helped or hurt
- Where in the episode failures happen, and whether that distribution moves
- What it costs — an agent in a 30 Hz loop has a real time budget

A result showing the agent *didn't* help, with evidence for why, is a genuine
finding. So is one that works only on a specific failure mode.

## Notes

The policy samples stochastically, so the same seed gives the same scene but not
the same actions. Rerunning a failure will not reproduce it exactly.

Episodes end on success or after `--steps`. There is no partial credit: the mug
is on the rack or it is not.

The policy was trained on all 50 RoboTwin tasks at once, not just this one.
`hanging_mug` is among the harder ones — it needs a precise grasp followed by a
precise placement, and an error in the first half is usually unrecoverable in the
second.
