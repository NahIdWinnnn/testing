import json
import struct
from pathlib import Path

import pytest
from PIL import Image

from var2026.viewer.sibr import (
    PATCHED_SIBR_MARKER,
    bundle_viewer,
    list_sibr_scenes,
    prepare_sibr_launch,
    prepare_test_only_sibr_model,
    pose_to_camera_json,
    resolve_sibr_scene,
    sibr_command,
    sibr_viewer_mode,
    viewer_from_env,
    write_test_colmap_source,
)
from var2026.io.test_poses import TestPose


HEADER = "image_name,qw,qx,qy,qz,tx,ty,tz,fx,fy,cx,cy,width,height\n"
ROW = "view.png,1,0,0,0,1,2,3,500,600,320,240,640,480\n"


def make_run(root: Path) -> None:
    root.mkdir(parents=True)
    for name in ("cfg_args", "cameras.json", "input.ply"):
        (root / name).write_text(name, encoding="utf-8")
    point_cloud = root / "point_cloud" / "iteration_30000"
    point_cloud.mkdir(parents=True)
    (point_cloud / "point_cloud.ply").write_text("ply", encoding="utf-8")
    renders = root / "renders_test"
    renders.mkdir()
    Image.new("RGB", (4, 2)).save(renders / "view.png")


def make_prepared(root: Path) -> None:
    (root / "train").mkdir(parents=True)
    test = root / "test"
    test.mkdir()
    (test / "test_poses.csv").write_text(HEADER + ROW, encoding="utf-8")


def make_prepared_without_test_poses(root: Path) -> None:
    (root / "train").mkdir(parents=True)


def test_resolve_sibr_scene_accepts_direct_run_layout(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    run = runs / "example"
    make_run(run)
    test = run / "test"
    test.mkdir()
    (test / "test_poses.csv").write_text(HEADER + ROW, encoding="utf-8")

    paths = resolve_sibr_scene("example", "graphdeco", runs, tmp_path / "prepared")

    assert paths.run == run.resolve()
    assert paths.prepared_train == run.resolve()
    assert paths.test_poses == (test / "test_poses.csv").resolve()


def test_list_sibr_scenes_finds_method_and_direct_layouts(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")
    make_run(runs / "example")

    scenes = list_sibr_scenes("graphdeco", runs, prepared)

    by_name = {scene.scene: scene for scene in scenes}
    assert by_name["scene_001"].layout == "runs/graphdeco"
    assert by_name["scene_001"].test_camera_count == 1
    assert by_name["example"].layout == "runs"
    assert by_name["example"].test_poses is None


def test_resolve_sibr_scene_paths(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")

    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    assert paths.run == (runs / "graphdeco" / "scene_001").resolve()
    assert paths.prepared_train == (prepared / "scene_001" / "train").resolve()
    assert paths.test_poses == (prepared / "scene_001" / "test" / "test_poses.csv").resolve()


def test_resolve_sibr_scene_allows_model_only_when_test_poses_missing(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared_without_test_poses(prepared / "scene_001")

    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    assert paths.test_poses is None


def test_sibr_viewer_falls_back_or_reports_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VAR2026_SIBR_GAUSSIAN_VIEWER", raising=False)
    try:
        viewer = viewer_from_env()
    except ValueError as exc:
        assert "scripts/setup_sibr.sh" in str(exc)
    else:
        assert viewer.name.startswith("SIBR_gaussianViewer_app")


def test_sibr_command_accepts_extra_args(tmp_path: Path) -> None:
    viewer = tmp_path / "SIBR_gaussianViewer_app"
    viewer.write_text("binary", encoding="utf-8")

    command = sibr_command(
        viewer,
        tmp_path / "model",
        tmp_path / "train",
        "--no_interop --rendering-size 800 600",
    )

    assert command == [
        str(viewer),
        "-m", str(tmp_path / "model"),
        "-s", str(tmp_path / "train"),
        "--no_interop",
        "--rendering-size", "800", "600",
    ]


def test_pose_to_camera_json_uses_world_to_camera_contract() -> None:
    pose = TestPose(
        image_name="view.png",
        qw=1,
        qx=0,
        qy=0,
        qz=0,
        tx=1,
        ty=2,
        tz=3,
        fx=500,
        fy=600,
        cx=320,
        cy=240,
        width=640,
        height=480,
    )

    camera = pose_to_camera_json(7, pose)

    assert camera["id"] == 7
    assert camera["img_name"] == "view.png"
    assert camera["position"] == [-1, -2, -3]
    assert camera["rotation"] == [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
    assert camera["fx"] == 500
    assert camera["fy"] == 600


def test_prepare_test_only_model_writes_test_cameras(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")
    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    model = prepare_test_only_sibr_model(paths)

    cameras = json.loads((model / "cameras.json").read_text(encoding="utf-8"))
    assert cameras[0]["img_name"] == "view.png"
    assert cameras[0]["position"] == [-1, -2, -3]
    assert (model / "point_cloud" / "iteration_30000" / "point_cloud.ply").is_file()
    assert (model / "test_poses.csv").is_file()


def test_write_test_colmap_source_creates_test_only_source(tmp_path: Path) -> None:
    poses = tmp_path / "test_poses.csv"
    poses.write_text(HEADER + ROW, encoding="utf-8")

    source = tmp_path / "source"
    written = write_test_colmap_source(poses, source)

    assert len(written) == 1
    assert (source / "images" / "view.png").is_file()
    assert (source / "sparse" / "0" / "cameras.bin").is_file()
    assert (source / "sparse" / "0" / "images.bin").is_file()
    assert (source / "sparse" / "0" / "points3D.bin").read_bytes() == b"\x00" * 8
    cameras_bin = (source / "sparse" / "0" / "cameras.bin").read_bytes()
    images_bin = (source / "sparse" / "0" / "images.bin").read_bytes()
    assert struct.unpack_from("<Q", cameras_bin, 0)[0] == 1
    assert struct.unpack_from("<i", cameras_bin, 8)[0] == 0
    assert struct.unpack_from("<Q", images_bin, 0)[0] == 1
    assert struct.unpack_from("<i", images_bin, 8)[0] == 0
    assert struct.unpack_from("<i", images_bin, 8 + struct.calcsize("<iddddddd"))[0] == 0


def test_prepare_sibr_launch_requires_patched_viewer_for_test_poses(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")
    viewer = tmp_path / "SIBR_gaussianViewer_app"
    viewer.write_text("binary", encoding="utf-8")
    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    with pytest.raises(ValueError, match="test-pose navigation requires"):
        prepare_sibr_launch(paths, viewer)


def test_prepare_sibr_launch_allows_raw_model_only_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")
    viewer = tmp_path / "SIBR_gaussianViewer_app"
    viewer.write_text("binary", encoding="utf-8")
    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)
    monkeypatch.setenv("VAR2026_SIBR_ALLOW_RAW", "1")

    launch = prepare_sibr_launch(paths, viewer)

    assert launch.scene == "scene_001"
    assert launch.method == "graphdeco"
    assert launch.mode == "raw-sibr-fallback"
    assert launch.test_camera_count == 1
    assert launch.model == paths.run / "viewer" / "sibr_test_only_model"
    assert launch.source == paths.run / "viewer" / "test_source"
    assert launch.command[:5] == [str(viewer), "-m", str(launch.model), "-s", str(launch.source)]


def test_prepare_sibr_launch_supports_scene_without_test_poses(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared_without_test_poses(prepared / "scene_001")
    viewer = tmp_path / "SIBR_gaussianViewer_app"
    viewer.write_text("binary", encoding="utf-8")
    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    launch = prepare_sibr_launch(paths, viewer)

    assert launch.test_camera_count == 0
    assert launch.model == paths.run
    assert launch.source == paths.prepared_train


def test_sibr_viewer_mode_detects_patch_marker(tmp_path: Path) -> None:
    viewer = tmp_path / "SIBR_gaussianViewer_app"
    viewer.write_text("binary", encoding="utf-8")

    assert sibr_viewer_mode(viewer) == "raw-sibr-fallback"

    (tmp_path / PATCHED_SIBR_MARKER).write_text("patched\n", encoding="utf-8")

    assert sibr_viewer_mode(viewer) == "patched-sibr"


def test_bundle_viewer_contains_model_poses_manifest_and_renders(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    prepared = tmp_path / "prepared"
    make_run(runs / "graphdeco" / "scene_001")
    make_prepared(prepared / "scene_001")
    paths = resolve_sibr_scene("scene_001", "graphdeco", runs, prepared)

    bundle = bundle_viewer(paths, tmp_path / "bundle")

    assert (bundle / "model" / "point_cloud" / "iteration_30000" / "point_cloud.ply").is_file()
    assert (bundle / "renders_test" / "view.png").is_file()
    assert (bundle / "test" / "test_poses.csv").read_text(encoding="utf-8") == HEADER + ROW
    cameras = json.loads((bundle / "test_cameras.json").read_text(encoding="utf-8"))
    assert cameras[0]["img_name"] == "view.png"
    manifest = json.loads((bundle / "viewer_manifest.json").read_text(encoding="utf-8"))
    assert manifest["scene"] == "scene_001"
    assert manifest["method"] == "graphdeco"
    assert manifest["test_camera_count"] == 1
