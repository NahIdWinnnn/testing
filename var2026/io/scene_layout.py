from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneLayout:
    root: Path

    @property
    def name(self) -> str:
        return self.root.name

    @property
    def train_images(self) -> Path:
        return self.root / "train" / "images"

    @property
    def sparse_model(self) -> Path:
        return self.root / "train" / "sparse" / "0"

    @property
    def test_poses(self) -> Path:
        return self.root / "test" / "test_poses.csv"

    def validate(self) -> None:
        required = [
            self.train_images,
            self.sparse_model / "cameras.bin",
            self.sparse_model / "images.bin",
            self.sparse_model / "points3D.bin",
            self.test_poses,
        ]
        missing = [str(path) for path in required if not path.exists()]
        if missing:
            raise ValueError("Invalid scene layout; missing: " + ", ".join(missing))


def discover_scenes(data_root: Path) -> list[SceneLayout]:
    if not data_root.is_dir():
        raise ValueError(f"Data root does not exist: {data_root}")
    scenes = [
        SceneLayout(path)
        for path in sorted(data_root.iterdir())
        if path.is_dir() and (path / "test" / "test_poses.csv").is_file()
    ]
    if not scenes:
        raise ValueError(f"No scenes with test/test_poses.csv found in {data_root}")
    return scenes
