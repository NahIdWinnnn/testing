# GraphDeCo patch log

GraphDeCo is now normal code inside this repo:

```text
methods/graphdeco
```

Current method patch:

- add `<cstdint>` to the rasterizer so CUDA 12.8 can build it.
- keep optional sample assets out of this repo.
- restore SIBR viewer source as `methods/sibr_viewers`, pinned to the upstream
  GraphDeCo `SIBR_viewers` commit.
- add optional SIBR viewer patch
  `docs/patches/sibr_var_test_pose_navigation.patch`; it adds the VAR Test
  Poses panel, hides default subview control panels, and adds Left/Right
  test-pose navigation to the native Gaussian viewer.
- add SIBR Linux build compatibility patch
  `docs/patches/sibr_modern_linux_deps.patch`; it keeps native SIBR buildable
  on the current workstation stack by handling Boost 1.90 without
  `boost_system`, Boost filesystem API changes, Embree 4 headers/libraries,
  CUDA 12.8 rasterizer compile quirks, newer FFmpeg headers, optional EGL, and
  WSLg GLEW/Wayland window-position warnings.

Do not commit `build/` or `*.egg-info/`.
