import json
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from var2026.io.scene_layout import discover_scenes
from var2026.io.test_poses import load_test_poses


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
    scenes: int
    images: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_submission(data_root: Path, submission_dir: Path) -> ValidationResult:
    errors: list[str] = []
    image_count = 0
    scenes = discover_scenes(data_root)
    expected_scene_names = {scene.name for scene in scenes}
    if not submission_dir.is_dir():
        return ValidationResult(False, [f"Submission directory does not exist: {submission_dir}"], len(scenes), 0)

    actual_scene_names = {path.name for path in submission_dir.iterdir() if path.is_dir()}
    for name in sorted(expected_scene_names - actual_scene_names):
        errors.append(f"Missing scene directory: {name}")
    for name in sorted(actual_scene_names - expected_scene_names):
        errors.append(f"Extra scene directory: {name}")
    extra_root_files = [path.name for path in submission_dir.iterdir() if path.is_file()]
    for name in sorted(extra_root_files):
        errors.append(f"Unexpected file at submission root: {name}")

    for scene in scenes:
        expected = {pose.image_name: pose for pose in load_test_poses(scene.test_poses)}
        scene_output = submission_dir / scene.name
        if not scene_output.is_dir():
            continue
        actual_files = {path.name: path for path in scene_output.iterdir() if path.is_file()}
        for name in sorted(expected.keys() - actual_files.keys()):
            errors.append(f"{scene.name}: missing image {name}")
        for name in sorted(actual_files.keys() - expected.keys()):
            errors.append(f"{scene.name}: extra image {name}")
        for name in sorted(expected.keys() & actual_files.keys()):
            image_count += 1
            try:
                with Image.open(actual_files[name]) as image:
                    image.load()
                    size = image.size
            except (OSError, UnidentifiedImageError) as exc:
                errors.append(f"{scene.name}/{name}: cannot decode image: {exc}")
                continue
            pose = expected[name]
            if size != (pose.width, pose.height):
                errors.append(
                    f"{scene.name}/{name}: size {size[0]}x{size[1]}, "
                    f"expected {pose.width}x{pose.height}"
                )
        nested = [path for path in scene_output.iterdir() if path.is_dir()]
        for path in nested:
            errors.append(f"{scene.name}: unexpected nested directory {path.name}")
    return ValidationResult(not errors, errors, len(scenes), image_count)


def write_validation_result(result: ValidationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8")
