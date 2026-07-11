import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

from var2026.io.scene_layout import SceneLayout

PREPARE_VERSION = 3


def _source_fingerprint(scene: SceneLayout, colmap_version: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"prepare_version={PREPARE_VERSION}\n".encode())
    digest.update(f"colmap_version={colmap_version}\n".encode())
    for path in (
        scene.sparse_model / "cameras.bin",
        scene.sparse_model / "images.bin",
        scene.sparse_model / "points3D.bin",
        scene.test_poses,
    ):
        digest.update(path.relative_to(scene.root).as_posix().encode())
        digest.update(path.read_bytes())
    for path in sorted(scene.train_images.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            stat = path.stat()
            digest.update(path.name.encode())
            digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode())
    return digest.hexdigest()


def _colmap_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "-h"],
        check=False,
        capture_output=True,
        text=True,
    )
    text = result.stdout or result.stderr
    return text.splitlines()[0].strip() if text else "unknown"


def _colmap_image_names(path: Path) -> set[str]:
    names: set[str] = set()
    with path.open("rb") as handle:
        count_data = handle.read(8)
        if len(count_data) != 8:
            raise RuntimeError(f"Invalid COLMAP images file: {path}")
        count = struct.unpack("<Q", count_data)[0]
        for _ in range(count):
            if len(handle.read(64)) != 64:
                raise RuntimeError(f"Invalid COLMAP image record: {path}")
            name_bytes = bytearray()
            while True:
                byte = handle.read(1)
                if not byte:
                    raise RuntimeError(f"Invalid COLMAP image name: {path}")
                if byte == b"\x00":
                    break
                name_bytes.extend(byte)
            names.add(name_bytes.decode("utf-8"))
            points_data = handle.read(8)
            if len(points_data) != 8:
                raise RuntimeError(f"Invalid COLMAP image points: {path}")
            points = struct.unpack("<Q", points_data)[0]
            handle.seek(24 * points, 1)
    return names


def _validate_prepared_scene(root: Path) -> None:
    layout = SceneLayout(root.resolve())
    layout.validate()
    disk_names = {
        path.name
        for path in layout.train_images.iterdir()
        if path.is_file() and not path.name.startswith(".")
    }
    model_names = _colmap_image_names(layout.sparse_model / "images.bin")
    if model_names != disk_names:
        raise RuntimeError(
            "Prepared COLMAP model does not match the images on disk"
        )


def prepare_graphdeco_scene(
    scene_root: Path,
    output: Path,
    colmap_executable: str = "colmap",
) -> bool:
    """Create a cached, undistorted COLMAP scene. Return True when rebuilt."""
    scene = SceneLayout(scene_root.resolve())
    scene.validate()
    executable = shutil.which(colmap_executable)
    if executable is None:
        raise RuntimeError(
            f"COLMAP executable not found: {colmap_executable!r}. "
            "Install COLMAP, then run the command again."
        )

    version = _colmap_version(executable)
    fingerprint = _source_fingerprint(scene, version)
    metadata_path = output / "prepare.json"
    if metadata_path.is_file():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("fingerprint") == fingerprint:
            try:
                _validate_prepared_scene(output)
            except (OSError, RuntimeError, ValueError):
                pass
            else:
                return False

    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        input_images = temporary / "input"
        input_images.symlink_to(scene.train_images, target_is_directory=True)
        distorted_sparse = temporary / "distorted" / "sparse" / "0"
        distorted_sparse.mkdir(parents=True)
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            shutil.copy2(scene.sparse_model / name, distorted_sparse / name)

        image_names = sorted(
            path.name
            for path in scene.train_images.iterdir()
            if path.is_file() and not path.name.startswith(".")
        )
        image_list = temporary / "train_images.txt"
        image_list.write_text("\n".join(image_names) + "\n", encoding="utf-8")

        train = temporary / "train"
        train.mkdir()
        commands: list[list[str]] = []
        undistort_command = [
            executable,
            "image_undistorter",
            "--image_path", str(input_images),
            "--input_path", str(distorted_sparse),
            "--output_path", str(train),
            "--output_type", "COLMAP",
            "--image_list_path", str(image_list),
        ]
        commands.append(undistort_command)
        subprocess.run(undistort_command, check=True)

        prepared_names = {
            path.name
            for path in (train / "images").iterdir()
            if path.is_file() and not path.name.startswith(".")
        }
        if prepared_names != set(image_names):
            missing = sorted(set(image_names) - prepared_names)
            extra = sorted(prepared_names - set(image_names))
            raise RuntimeError(
                f"COLMAP output image mismatch; missing={missing}, extra={extra}"
            )

        sparse = train / "sparse"
        model_names = _colmap_image_names(sparse / "images.bin")
        extra_model_names = sorted(model_names - set(image_names))
        if extra_model_names:
            delete_list = temporary / "delete_images.txt"
            delete_list.write_text(
                "\n".join(extra_model_names) + "\n",
                encoding="utf-8",
            )
            filtered_sparse = temporary / "filtered_sparse"
            filtered_sparse.mkdir()
            delete_command = [
                executable,
                "image_deleter",
                "--input_path", str(sparse),
                "--output_path", str(filtered_sparse),
                "--image_names_path", str(delete_list),
            ]
            commands.append(delete_command)
            subprocess.run(delete_command, check=True)
            shutil.rmtree(sparse)
            filtered_sparse.rename(sparse)
            delete_list.unlink()

        final_model_names = _colmap_image_names(sparse / "images.bin")
        if final_model_names != set(image_names):
            raise RuntimeError(
                "Filtered COLMAP model does not match the training image list"
            )

        sparse_zero = sparse / "0"
        sparse_zero.mkdir()
        for name in ("cameras.bin", "images.bin", "points3D.bin"):
            shutil.move(str(sparse / name), sparse_zero / name)

        test = temporary / "test"
        test.mkdir()
        shutil.copy2(scene.test_poses, test / "test_poses.csv")
        shutil.rmtree(temporary / "distorted")
        input_images.unlink()
        image_list.unlink()
        shutil.rmtree(train / "stereo", ignore_errors=True)

        metadata = {
            "source": str(scene.root),
            "fingerprint": fingerprint,
            "prepare_version": PREPARE_VERSION,
            "colmap_version": version,
            "commands": commands,
        }
        (temporary / "prepare.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )
        _validate_prepared_scene(temporary)
        if output.exists():
            shutil.rmtree(output)
        temporary.rename(output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return True
