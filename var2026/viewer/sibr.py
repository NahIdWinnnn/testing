import json
import os
import shutil
import shlex
import struct
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from var2026.camera.colmap_pose import quaternion_to_rotation
from var2026.io.test_poses import TestPose, load_test_poses


@dataclass(frozen=True)
class SibrScenePaths:
    scene: str
    method: str
    run: Path
    prepared_train: Path
    test_poses: Path | None


@dataclass(frozen=True)
class SibrLaunchInfo:
    scene: str
    method: str
    mode: str
    viewer: Path
    model: Path
    source: Path
    test_camera_count: int
    command: list[str]


@dataclass(frozen=True)
class SibrSceneSummary:
    scene: str
    method: str
    run: Path
    test_poses: Path | None
    test_camera_count: int
    layout: str


PATCHED_SIBR_MARKER = ".var2026_test_pose_navigation"
RAW_VIEWER_TRUE_VALUES = {"1", "true", "yes", "on"}


def resolve_sibr_scene(
    scene: str,
    method: str,
    runs_root: Path,
    prepared_root: Path,
) -> SibrScenePaths:
    if method != "graphdeco":
        raise NotImplementedError("SIBR viewer is currently supported only for graphdeco runs")
    run = _resolve_run_path(scene, method, runs_root)
    prepared_scene = (prepared_root / scene).resolve()
    prepared_train = prepared_scene / "train"
    if not prepared_train.is_dir():
        run_train = run / "train"
        prepared_train = run_train if run_train.is_dir() else run
    paths = SibrScenePaths(
        scene=scene,
        method=method,
        run=run,
        prepared_train=prepared_train,
        test_poses=_resolve_test_poses(scene, run, prepared_root),
    )
    _validate_model(paths.run)
    return paths


def _resolve_run_path(scene: str, method: str, runs_root: Path) -> Path:
    candidates = [
        runs_root / method / scene,
        runs_root / scene,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


def _resolve_test_poses(scene: str, run: Path, prepared_root: Path) -> Path | None:
    candidates = [
        prepared_root / scene / "test" / "test_poses.csv",
        run / "test" / "test_poses.csv",
        run / "test_poses.csv",
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    return None


def list_sibr_scenes(
    method: str,
    runs_root: Path,
    prepared_root: Path,
) -> list[SibrSceneSummary]:
    if method != "graphdeco":
        raise NotImplementedError("SIBR viewer is currently supported only for graphdeco runs")
    runs_root = runs_root.resolve()
    candidate_runs: list[tuple[str, Path, str]] = []
    method_root = runs_root / method
    if method_root.is_dir():
        candidate_runs.extend((child.name, child, f"runs/{method}") for child in sorted(method_root.iterdir()) if child.is_dir())
    if runs_root.is_dir():
        candidate_runs.extend((child.name, child, "runs") for child in sorted(runs_root.iterdir()) if child.is_dir())

    seen: set[str] = set()
    scenes: list[SibrSceneSummary] = []
    for scene, run, layout in candidate_runs:
        if scene in seen:
            continue
        try:
            _validate_model(run)
        except FileNotFoundError:
            continue
        test_poses = _resolve_test_poses(scene, run.resolve(), prepared_root.resolve())
        scenes.append(
            SibrSceneSummary(
                scene=scene,
                method=method,
                run=run.resolve(),
                test_poses=test_poses,
                test_camera_count=_count_test_poses(test_poses) if test_poses is not None else 0,
                layout=layout,
            )
        )
        seen.add(scene)
    return scenes


def _count_test_poses(test_poses: Path) -> int:
    return len(load_test_poses(test_poses))


def _validate_model(run: Path) -> None:
    required = [
        run / "cfg_args",
        run / "cameras.json",
        run / "input.ply",
        run / "point_cloud",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Invalid SIBR model; missing: " + ", ".join(missing))
    point_clouds = sorted((run / "point_cloud").glob("iteration_*/point_cloud.ply"))
    if not point_clouds:
        raise FileNotFoundError(f"No trained point cloud found under {run / 'point_cloud'}")


def pose_to_camera_json(index: int, pose: TestPose) -> dict[str, object]:
    rotation = quaternion_to_rotation(pose.qw, pose.qx, pose.qy, pose.qz)
    position = [
        -sum(rotation[row][column] * value for row, value in enumerate((pose.tx, pose.ty, pose.tz)))
        for column in range(3)
    ]
    camera_to_world_rotation = [
        [rotation[row][column] for row in range(3)]
        for column in range(3)
    ]
    return {
        "id": index,
        "img_name": pose.image_name,
        "width": pose.width,
        "height": pose.height,
        "position": position,
        "rotation": camera_to_world_rotation,
        "fy": pose.fy,
        "fx": pose.fx,
    }


def write_test_cameras(test_poses: Path, output: Path) -> list[dict[str, object]]:
    cameras = [
        pose_to_camera_json(index, pose)
        for index, pose in enumerate(load_test_poses(test_poses))
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(cameras, indent=2) + "\n", encoding="utf-8")
    return cameras


def write_test_colmap_source(test_poses: Path, output: Path) -> list[TestPose]:
    poses = load_test_poses(test_poses)
    if not poses:
        raise ValueError(f"No test poses found in {test_poses}")
    images = output / "images"
    sparse = output / "sparse" / "0"
    images.mkdir(parents=True, exist_ok=True)
    sparse.mkdir(parents=True, exist_ok=True)

    _write_colmap_cameras(poses, sparse / "cameras.bin")
    _write_colmap_images(poses, sparse / "images.bin")
    (sparse / "points3D.bin").write_bytes(struct.pack("<Q", 0))

    from PIL import Image

    expected = {pose.image_name for pose in poses}
    for child in images.iterdir():
        if child.name not in expected:
            child.unlink()
    for pose in poses:
        image = images / pose.image_name
        if image.is_file():
            continue
        Image.new("RGB", (pose.width, pose.height), "black").save(image)
    return poses


def _write_colmap_cameras(poses: list[TestPose], output: Path) -> None:
    with output.open("wb") as handle:
        handle.write(struct.pack("<Q", len(poses)))
        for index, pose in enumerate(poses):
            handle.write(struct.pack("<iiQQ", index, 1, pose.width, pose.height))
            handle.write(struct.pack("<dddd", pose.fx, pose.fy, pose.cx, pose.cy))


def _write_colmap_images(poses: list[TestPose], output: Path) -> None:
    with output.open("wb") as handle:
        handle.write(struct.pack("<Q", len(poses)))
        for index, pose in enumerate(poses):
            handle.write(
                struct.pack(
                    "<idddddddi",
                    index,
                    pose.qw,
                    pose.qx,
                    pose.qy,
                    pose.qz,
                    pose.tx,
                    pose.ty,
                    pose.tz,
                    index,
                )
            )
            handle.write(pose.image_name.encode("utf-8") + b"\x00")
            handle.write(struct.pack("<Q", 0))


def prepare_test_only_sibr_model(
    paths: SibrScenePaths,
    viewer_root: Path | None = None,
    link_assets: bool = True,
) -> Path:
    if paths.test_poses is None:
        raise ValueError(f"No test poses found for scene {paths.scene}")
    viewer_root = viewer_root or paths.run / "viewer"
    model = viewer_root / "sibr_test_only_model"
    model.mkdir(parents=True, exist_ok=True)
    for name in ("cfg_args", "input.ply", "point_cloud", "exposure.json"):
        source = paths.run / name
        if source.exists():
            _sync_link_or_copy(source, model / name, link_assets=link_assets)
    write_test_cameras(paths.test_poses, model / "cameras.json")
    shutil.copy2(paths.test_poses, model / "test_poses.csv")
    return model


def _remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _sync_link_or_copy(source: Path, destination: Path, link_assets: bool) -> None:
    if source.is_dir():
        destination.mkdir(exist_ok=True)
        expected = {child.name for child in source.iterdir()}
        if destination.exists():
            for child in destination.iterdir():
                if child.name not in expected:
                    _remove_path(child)
        for child in source.iterdir():
            _sync_link_or_copy(child, destination / child.name, link_assets=link_assets)
        return
    if _same_file_payload(source, destination):
        return
    if destination.exists() or destination.is_symlink():
        _remove_path(destination)
    if link_assets:
        try:
            os.link(source, destination)
            return
        except OSError:
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _same_file_payload(source: Path, destination: Path) -> bool:
    if not destination.is_file():
        return False
    source_stat = source.stat()
    destination_stat = destination.stat()
    return (
        source_stat.st_size == destination_stat.st_size
        and source_stat.st_mtime_ns == destination_stat.st_mtime_ns
    )


def sibr_command(
    viewer: Path,
    model: Path,
    prepared_train: Path,
    extra_args: str = "",
) -> list[str]:
    if not viewer:
        raise ValueError("VAR2026_SIBR_GAUSSIAN_VIEWER is not set")
    if not viewer.is_file():
        raise FileNotFoundError(f"SIBR viewer binary does not exist: {viewer}")
    model_arg = _viewer_path_argument(viewer, model)
    command = [
        str(viewer),
        "-m", model_arg,
    ]
    train_arg = _viewer_path_argument(viewer, prepared_train)
    command.extend(["-s", train_arg])
    command.extend(shlex.split(extra_args))
    return command


def _viewer_path_argument(viewer: Path, path: Path) -> str:
    if viewer.suffix.lower() != ".exe":
        return str(path)
    wslpath = shutil.which("wslpath")
    if not wslpath:
        return str(path)
    result = subprocess.run(
        [wslpath, "-w", str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def launch_sibr_viewer(
    paths: SibrScenePaths,
    viewer: Path,
    extra_args: str = "",
) -> int:
    launch = prepare_sibr_launch(paths, viewer, extra_args)
    print_sibr_launch(launch)
    return subprocess.run(launch.command, cwd=viewer.parent, check=False).returncode


def prepare_sibr_launch(
    paths: SibrScenePaths,
    viewer: Path,
    extra_args: str = "",
) -> SibrLaunchInfo:
    mode = sibr_viewer_mode(viewer)
    if paths.test_poses is None:
        model = paths.run
        prepared_train = paths.prepared_train
        poses = []
    else:
        _validate_test_pose_viewer_mode(mode, paths)
        if viewer.suffix.lower() == ".exe":
            cache_root = _windows_cache_root(paths)
            model = prepare_test_only_sibr_model(
                paths,
                viewer_root=cache_root,
                link_assets=False,
            )
            prepared_train = cache_root / "test_source"
            poses = write_test_colmap_source(paths.test_poses, prepared_train)
        else:
            model = prepare_test_only_sibr_model(paths)
            prepared_train = paths.run / "viewer" / "test_source"
            poses = write_test_colmap_source(paths.test_poses, prepared_train)
    if poses:
        _validate_test_source(prepared_train, len(poses))
    command = sibr_command(viewer, model, prepared_train, extra_args)
    return SibrLaunchInfo(
        scene=paths.scene,
        method=paths.method,
        mode=mode,
        viewer=viewer,
        model=model,
        source=prepared_train,
        test_camera_count=len(poses),
        command=command,
    )


def _validate_test_pose_viewer_mode(mode: str, paths: SibrScenePaths) -> None:
    allow_raw = os.environ.get("VAR2026_SIBR_ALLOW_RAW", "").strip().lower()
    if mode == "raw-sibr-fallback" and allow_raw not in RAW_VIEWER_TRUE_VALUES:
        raise ValueError(
            f"Scene {paths.scene} has test poses at {paths.test_poses}, but the configured "
            "viewer is the raw official SIBR binary. Left/Right test-pose navigation "
            "requires the patched native SIBR viewer. Run scripts/setup_sibr.sh --native. "
            "For model-only raw viewing, set VAR2026_SIBR_ALLOW_RAW=1."
        )


def _validate_test_source(source: Path, expected_count: int) -> None:
    sparse = source / "sparse" / "0"
    missing = [
        path
        for path in (
            source / "images",
            sparse / "cameras.bin",
            sparse / "images.bin",
            sparse / "points3D.bin",
        )
        if not path.exists()
    ]
    if missing:
        joined = ", ".join(str(path) for path in missing)
        raise FileNotFoundError(f"Invalid SIBR test source; missing: {joined}")
    actual_count = sum(1 for path in (source / "images").iterdir() if path.is_file())
    if actual_count != expected_count:
        raise ValueError(
            f"Invalid SIBR test source: expected {expected_count} test images, "
            f"found {actual_count} in {source / 'images'}"
        )


def sibr_viewer_mode(viewer: Path) -> str:
    marker = viewer.parent / PATCHED_SIBR_MARKER
    if marker.is_file():
        return "patched-sibr"
    value = os.environ.get("VAR2026_SIBR_PATCHED", "").strip().lower()
    if value in {"1", "true", "yes", "on", "patched"}:
        return "patched-sibr"
    return "raw-sibr-fallback"


def print_sibr_launch(launch: SibrLaunchInfo) -> None:
    print("SIBR viz launch:", flush=True)
    print(f"  scene: {launch.scene}", flush=True)
    print(f"  method: {launch.method}", flush=True)
    print(f"  mode: {launch.mode}", flush=True)
    print(f"  viewer: {launch.viewer}", flush=True)
    print(f"  model: {launch.model}", flush=True)
    print(f"  source: {launch.source}", flush=True)
    print(f"  test cameras: {launch.test_camera_count}", flush=True)
    if launch.mode == "raw-sibr-fallback":
        print(
            "  note: raw official SIBR opens the model, but does not include the "
            "VAR Test Poses panel. Test-pose arrows require scripts/setup_sibr.sh --native.",
            flush=True,
        )


def _windows_cache_root(paths: SibrScenePaths) -> Path:
    configured = os.environ.get("VAR2026_SIBR_WINDOWS_CACHE", "")
    if configured:
        return Path(configured).expanduser().resolve() / paths.method / paths.scene
    wslpath = shutil.which("wslpath")
    if not wslpath:
        return paths.run / "viewer" / "windows_cache"
    result = subprocess.run(
        ["cmd.exe", "/c", "echo %USERPROFILE%"],
        check=True,
        capture_output=True,
        text=True,
    )
    windows_profile = result.stdout.strip().splitlines()[-1]
    converted = subprocess.run(
        [wslpath, "-u", windows_profile],
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        Path(converted.stdout.strip())
        / "VAR2026"
        / "NVSViewerCache"
        / paths.method
        / paths.scene
    )


def bundle_viewer(paths: SibrScenePaths, output: Path) -> Path:
    output = output.resolve()
    if output.exists() or output.is_symlink():
        _remove_path(output)
    output.mkdir(parents=True)

    model_out = output / "model"
    _copy_model(paths.run, model_out)
    renders = paths.run / "renders_test"
    if not renders.is_dir():
        raise FileNotFoundError(f"Missing rendered test images: {renders}")
    shutil.copytree(renders, output / "renders_test")

    test_dir = output / "test"
    test_dir.mkdir()
    shutil.copy2(paths.test_poses, test_dir / "test_poses.csv")
    cameras = write_test_cameras(paths.test_poses, output / "test_cameras.json")
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": paths.method,
        "scene": paths.scene,
        "model": "model",
        "renders_test": "renders_test",
        "test_poses": "test/test_poses.csv",
        "test_cameras": "test_cameras.json",
        "test_camera_count": len(cameras),
        "source_run": str(paths.run),
        "source_prepared_train": str(paths.prepared_train),
    }
    (output / "viewer_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def _copy_model(run: Path, output: Path) -> None:
    output.mkdir()
    for name in ("cfg_args", "cameras.json", "input.ply", "exposure.json"):
        source = run / name
        if source.is_file():
            shutil.copy2(source, output / name)
    shutil.copytree(run / "point_cloud", output / "point_cloud")


def viewer_from_env() -> Path:
    value = os.environ.get("VAR2026_SIBR_GAUSSIAN_VIEWER", "")
    if value and not value.startswith("/path/to/"):
        return Path(value).expanduser().resolve()
    root = Path(__file__).resolve().parents[2]
    candidates = []
    candidates.extend(
        [
            root / "methods" / "sibr_viewers" / "install" / "bin" / "SIBR_gaussianViewer_app",
            root / ".local" / "sibr_windows" / "bin" / "SIBR_gaussianViewer_app.exe",
        ]
    )
    windows_viewer = _default_windows_viewer()
    if windows_viewer is not None:
        candidates.append(windows_viewer)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    if not value:
        raise ValueError(
            "SIBR viewer is not configured. Set VAR2026_SIBR_GAUSSIAN_VIEWER "
            "to the SIBR_gaussianViewer_app binary, or run scripts/setup_sibr.sh."
        )
    raise FileNotFoundError(
        f"SIBR viewer binary does not exist: {Path(value).expanduser().resolve()}. "
        "Set VAR2026_SIBR_GAUSSIAN_VIEWER or run scripts/setup_sibr.sh."
    )


def _default_windows_viewer() -> Path | None:
    if not shutil.which("wslpath") or not shutil.which("cmd.exe"):
        return None
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", "echo %USERPROFILE%"],
            check=True,
            capture_output=True,
            text=True,
        )
        windows_profile = result.stdout.strip().splitlines()[-1]
        converted = subprocess.run(
            ["wslpath", "-u", windows_profile],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, IndexError):
        return None
    return (
        Path(converted.stdout.strip())
        / "VAR2026"
        / "SIBR_viewers"
        / "bin"
        / "SIBR_gaussianViewer_app.exe"
    )
