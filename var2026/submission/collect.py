import shutil
from pathlib import Path

from var2026.io.scene_layout import discover_scenes


def collect_renders(data_root: Path, runs_root: Path, submission_dir: Path) -> None:
    submission_dir.mkdir(parents=True, exist_ok=True)
    for scene in discover_scenes(data_root):
        source = runs_root / scene.name / "renders_test"
        if not source.is_dir():
            raise RuntimeError(f"Missing renders for {scene.name}: {source}")
        destination = submission_dir / scene.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)
