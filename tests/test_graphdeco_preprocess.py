import struct
from pathlib import Path
from subprocess import CompletedProcess

from var2026.preprocess import graphdeco


def _make_scene(root: Path) -> None:
    images = root / "train" / "images"
    sparse = root / "train" / "sparse" / "0"
    test = root / "test"
    images.mkdir(parents=True)
    sparse.mkdir(parents=True)
    test.mkdir()
    (images / "image.jpg").write_bytes(b"image")
    for name in ("cameras.bin", "images.bin", "points3D.bin"):
        (sparse / name).write_bytes(name.encode())
    (test / "test_poses.csv").write_text("poses", encoding="utf-8")


def test_prepare_builds_and_reuses_cache(tmp_path: Path, monkeypatch) -> None:
    scene = tmp_path / "scene"
    output = tmp_path / "prepared"
    executable = tmp_path / "colmap"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    _make_scene(scene)
    undistort_calls = 0

    def fake_run(command, **kwargs):
        nonlocal undistort_calls
        if command[1] == "-h":
            return CompletedProcess(command, 0, "COLMAP 1.0\n", "")
        if command[1] == "image_deleter":
            source = Path(command[command.index("--input_path") + 1])
            target = Path(command[command.index("--output_path") + 1])
            target.mkdir(exist_ok=True)
            for name in ("cameras.bin", "images.bin", "points3D.bin"):
                (target / name).write_bytes((source / name).read_bytes())
            return CompletedProcess(command, 0)

        undistort_calls += 1
        train = Path(command[command.index("--output_path") + 1])
        images = train / "images"
        images.mkdir()
        image_list = Path(command[command.index("--image_list_path") + 1])
        for name in image_list.read_text(encoding="utf-8").splitlines():
            (images / name).write_bytes(b"prepared")
        sparse = train / "sparse"
        sparse.mkdir()
        (sparse / "cameras.bin").write_bytes(b"cameras")
        (sparse / "points3D.bin").write_bytes(b"points")
        names = image_list.read_text(encoding="utf-8").splitlines()
        with (sparse / "images.bin").open("wb") as handle:
            handle.write(struct.pack("<Q", len(names)))
            for index, name in enumerate(names, start=1):
                handle.write(
                    struct.pack(
                        "<i4d3di",
                        index, 1.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, 1,
                    )
                )
                handle.write(name.encode() + b"\x00")
                handle.write(struct.pack("<Q", 0))
        return CompletedProcess(command, 0)

    monkeypatch.setattr(graphdeco.subprocess, "run", fake_run)
    assert graphdeco.prepare_graphdeco_scene(scene, output, str(executable))
    assert not graphdeco.prepare_graphdeco_scene(scene, output, str(executable))
    assert undistort_calls == 1

    (output / "train" / "images" / "image.jpg").unlink()
    assert graphdeco.prepare_graphdeco_scene(scene, output, str(executable))
    assert undistort_calls == 2

    (scene / "train" / "sparse" / "0" / "cameras.bin").write_bytes(b"changed")
    assert graphdeco.prepare_graphdeco_scene(scene, output, str(executable))
    assert undistort_calls == 3
