# RoboTwin transition: start here

Prepared 2026-10-15. Working root: `C:\Users\almon\Desktop\RoboTwin-Agent`.

## Current result

The client starter, pinned RoboTwin source snapshot, setup scripts, Colab notebook,
and small Colab upload bundle are prepared. **The first real 30-step policy smoke
episode and two full 1,200-step attempts completed and produced new videos.**
The full attempts reported 0/2 task successes. Colab L4 allocation,
NVIDIA Vulkan, SAPIEN rendering, both Python environments, CuRobo compilation,
asset extraction, and checkpoint download are verified. This establishes a working
baseline execution pipeline; it does not reproduce the client's reported success rate.

| Run | Seed | Steps / video frames | Task success | Local video |
| --- | --- | --- | --- | --- |
| Pipeline smoke | 0 | 30 | No | `robotwin/outputs/20261015T142012Z/episode_0.mp4` |
| Full attempt | 0 | 1200 | No | `robotwin/outputs/20261015T142335Z/episode_0.mp4` |
| Full attempt | 1 | 1200 | No | `robotwin/outputs/20261015T142836Z/episode_1.mp4` |

Both full videos are 320x240, 40 seconds at 30 fps. Video frame counts were
checked with ffprobe, simulator step counters agree, and downloaded video hashes
match the Colab records. `robotwin/evidence/episodes.json` records these checks.
Logs and videos are local under `robotwin/outputs/` and ignored by Git. The original
download is `C:\Users\almon\Downloads\robotwin-results.zip` (5,180,804 bytes).
`sim-packages.txt` and `policy-packages.txt` under `robotwin/evidence/` record the
installed environments; they are observations, not portable lockfiles.

The original checkout is retained as a reference at
`C:\Users\almon\Desktop\Agent-Aware-Vision-Language-Action-Model`.
Both checkouts now use `https://github.com/almondkiruthu/Agent-Aware-Vision-Language-Action-Model.git`.
The new checkout has independent Git metadata and preserves the fork's history.
It is on `codex/robotwin-setup`, based on `f5fc34f2b9f224136db31d93b3f78d54817063ec`.
Setup changes are local and have not been pushed.

Open the new directory as the project for further work. This existing chat remains
associated with the original directory; shell commands must explicitly use the new
directory until the project is switched in the app.

## Why Colab is the next target

- This machine has an RTX 2050 with 4096 MiB VRAM.
- The actual WSL Vulkan probe exposes only `llvmpipe`, a CPU renderer, although
  `nvidia-smi` can see the NVIDIA GPU. See `robotwin/evidence/wsl-preflight.json`.
- RoboTwin's official system-support table lists WSL rendering as unsupported.
- The supplied Slack thread reports that teammates exhausted 4 GB VRAM on native
  Ubuntu and subsequently ran inference on Modal. Those are teammate reports,
  not runs verified on this machine.
- The owner prefers existing Colab Pro access. No Modal account, paid GPU rental,
  or deployment was created. Colab must pass the same Vulkan and SAPIEN checks.
- Chrome upload succeeded after enabling extension file access. The live execution record is
  https://colab.research.google.com/drive/11btnJ6fhRl1z3D0Z2Cb_Uekhqdd9Sq8p?authuser=2
  It retains diagnostic history. Use the clean generated `robotwin/RoboTwin_Colab.ipynb`
  for a new runtime; the execution record is evidence of this run.
- The assigned L4 has 23034 MiB VRAM and driver 580.82.07. Colab initially lacked
  Vulkan ICD registration. Matching official NVIDIA userspace files were extracted
  without installing a kernel driver, then Vulkan ICD and EGL vendor JSON paths
  were set in the notebook environment. Both registrations are necessary.
- `vulkaninfo --summary` then identified `DRIVER_ID_NVIDIA_PROPRIETARY` and the L4;
  SAPIEN 3.0.3 produced a nonblank 320x240 image. This is a renderer test only.
- The runtime ships CUDA toolkit 13.0, so CUDA 12.8 compiler and development
  headers are installed alongside it for the client's CuRobo build.

Docker Desktop over WSL does not, by itself, supply the missing NVIDIA Vulkan
driver. Do not download the full simulator assets locally just to discover the
same rendering limitation again.

## Files and next run

1. Open `robotwin/RoboTwin_Colab.ipynb` in Colab and select a GPU runtime.
2. Upload `robotwin/robotwin-colab-input.zip` when its first cell requests it.
3. Run the host preflight. Stop if it does not find NVIDIA Vulkan.
4. Check CUDA 12.x development headers and GCC/G++ >=13 as required by the client.
5. Install separate Python 3.10 simulator and Python 3.12 policy environments.
   The notebook tests a real SAPIEN image before installing the larger stack.
6. Fetch source, build CuRobo v0.7.8, and download assets and model weights.
7. Run a 30-step pipeline smoke test, then a 1200-step episode. Inspect the newly
   generated video and logs. Download the evidence ZIP before ending the runtime.

The notebook fails on missing prerequisites instead of silently substituting a
software renderer or treating CUDA availability as proof of rendering support.
It may require runtime-specific toolchain work; it is not certified turnkey.

For a compatible Linux host, run these from `robotwin/` in order:

```bash
bash setup/install_linux.sh check
bash setup/install_linux.sh environments
bash setup/install_linux.sh source
export CUDA_HOME=/usr/local/cuda  # verify this contains CUDA 12.x headers and nvcc
bash setup/install_linux.sh curobo
bash setup/install_linux.sh assets
bash setup/install_linux.sh weights
bash setup/run_smoke.sh 0 30
bash setup/run_smoke.sh 0 1200
```

Install `uv` and the OS tools listed in the notebook first. The scripts do not
modify host NVIDIA drivers. They record output under `robotwin/outputs/` and stop
the simulator they launch, including on failure. One episode is a smoke test,
not a success-rate estimate or evidence of supervisor improvement.

## Provenance and boundaries

The original client README, runner, requirements, and supplied videos are kept
unchanged under `robotwin/`. `robotwin/evidence/starter-manifest.json` records their
hashes against the ZIP. Supplied videos are examples, not outputs of this setup.

`robotwin/setup/pins.json` records exact RoboTwin, LeRobot, and checkpoint revisions.
The client did not specify a RoboTwin commit; the selected source revision is the
upstream HEAD retrieved during setup, not a known client-tested revision.
The local RoboTwin directory is an archive snapshot because Git's network
transport failed. It has a `.source-revision` marker and retains upstream LICENSE.
The XPolicyLab submodule is not included in the snapshot; the client runner uses
the separate pinned LeRobot stack. A fresh Linux/Colab checkout uses submodules.

The checkpoint is public at `Neotix-Robotics/robotwin-hanging-mug-dit`, revision
`d49ccf6705835dabca5f47c77ae9bd9807e02625`. No Hugging Face token is required.
Local download is incomplete: small configuration/normalization files arrived,
but the 1,773,362,776-byte model transfer stalled without receiving payload data.
Both Hugging Face and direct HTTPS attempts were stopped; no downloader remains
running. `weights/model.safetensors.partial` is an empty placeholder, not a model.
The notebook downloads the complete checkpoint directly into the Colab runtime.
The client reports roughly 6% success over 50 episodes; that claim has not been
reproduced here. The full Slack transcript and its credentials are not included.

No legacy code has been removed. First establish the RoboTwin baseline, then
review the reusable trace, supervision, memory, and evaluation interfaces against
this client's 14-dimensional joint-target/action-chunk contract. Review the team's
existing RoboTwin work before implementing a second version of it.

Do not run the old AFK issue queue against this new scope. Forking Git history
does not guarantee that GitHub issues and dependencies were migrated. Repository
names have been updated, but issue IDs, acceptance criteria, and the work queue
still require reconciliation before another AFK run.

## Verification and remaining blockers

Verified: remote/fork main SHA equality; original starter file hashes; Python and
notebook code-cell syntax; Bash syntax; local preflight correctly rejects WSL;
public checkpoint metadata; source archive extraction and revision recording.

Also verified: Colab GPU allocation; NVIDIA Vulkan on Colab; SAPIEN render.
Also verified: full simulator/policy installation; CUDA compilation; RoboTwin assets;
public checkpoint download; live 30-step policy episode; two full-length episodes;
all three downloaded videos, hashes, frame counts, and simulator step counts.
Not verified: statistical reproduction of the client's baseline; supervisor integration.

Ubuntu also had a pre-existing interrupted dpkg/systemd configuration. It was
reported rather than repaired as part of this task. The Vulkan diagnostic package
was extracted temporarily without configuring those packages.
Automatic approval review blocked cleanup of `robotwin/.cache/vulkan/` with only
the reason `blocked by policy`, even after its exact path and contents were
verified. The small diagnostic folder therefore remains, ignored by Git. There
are no extra extracted starter directories; the original ZIP was preserved.

Sources:
- https://robotwin-platform.github.io/doc/usage/robotwin-install.html
- https://github.com/RoboTwin-Platform/RoboTwin
- https://huggingface.co/Neotix-Robotics/robotwin-hanging-mug-dit
- https://research.google.com/colaboratory/faq.html
- Client ZIP and user-supplied Slack thread (private; not copied here).
