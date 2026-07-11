# VAR 2026 Repository Instructions

## Goal and priorities

This is the contest orchestration repository for VAR 2026 Novel View Synthesis /
BTS Digital Twin. Prioritize a valid, reproducible pipeline over model quality:
repo structure, camera correctness, strict submission validation, GraphDeCo
baseline, and shared QA.

## Data and camera contract

Each scene contains `train/images`, `train/sparse/0/{cameras,images,points3D}.bin`,
and `test/test_poses.csv`. Test CSV columns are:
`image_name,qw,qx,qy,qz,tx,ty,tz,fx,fy,cx,cy,width,height`.

Poses are COLMAP world-to-camera. Quaternion order is `qw,qx,qy,qz`; translation
order is `tx,ty,tz`; camera center is `C = -R.T @ t`; local axes are x right,
y down, z forward. Never assume camera-to-world or invert a pose unless a
specific backend adapter explicitly requires and documents it.

## Architecture and environments

Competition code belongs in `var2026/`; external implementations belong in
`methods/`. The root `var2026` Conda environment is lightweight orchestration
and QA. Every method may use its own Python, PyTorch, CUDA runtime, and compiled
extensions. Do not force every method to use Python 3.10 or 3.11. Runners invoke
method environments with `conda run -n <env>`.

GraphDeCo is an upstream recursive Git submodule at `methods/graphdeco`. Do not
modify its core files unless absolutely necessary. Record every unavoidable
patch in `docs/graphdeco_patch_log.md`. Future method runners must fail with a
clear `NotImplementedError`; never pretend unsupported methods work.

## Workstation workflow

The repository is self-contained. Local data, runs, and submissions use
`VAI_NVS_DATA/`, `runs/`, and `submissions/` inside the checkout. Git ignores
all three. Do not assume a fixed checkout path. Heavy training and inference
run on the shared WSL GPU workstation. Use tmux for long jobs and `just` for
daily commands.

## Commands, outputs, and QA

Keep explicit canonical commands under `python -m var2026`; use `just` as the
short operator interface. Do not hard-code private paths in Python. Every run
must record command, config, timestamps, status, logs, and errors. Never silently
skip a failed scene.

Use Streamlit as the shared QA dashboard. SIBR is an optional live/model viewer,
not the dashboard, and must never block the pipeline. Do not rebuild a realtime
3D viewer in Streamlit.

Submission validation must remain strict: exact expected scenes and images,
decodable files, correct dimensions, and no missing or extra output. Never weaken
validation to make a submission pass. ZIP scene directories at archive root;
never zip an outer version directory.

## Reproducibility and judge reproduction

Do not assume `git clone` alone is sufficient. Preserve exact commands, configs,
logs, root commits, recursive submodule commits, environment files, validation
reports, and model paths for every final run.

Do not silently patch external method code. Keep each required patch under
`docs/patches/` and record it in the method patch log.

Never weaken submission validation. `.env` is local only. Commit
`.env.example`, not `.env`. Local data, runs, and submissions use ignored
directories inside the repository.

Every final result must be traceable to a root repository commit, submodule
commits, config, environment, and command log.

## Do not

- Do not implement renderers in the orchestration repository.
- Do not assume test poses are camera-to-world.
- Do not mix method dependencies into the root environment.
- Do not modify upstream method code casually.
- Do not hard-code private paths in Python.
- Do not silently skip failed scenes.
- Do not block work on SIBR.
- Do not prioritize tuning before pipeline validity.
