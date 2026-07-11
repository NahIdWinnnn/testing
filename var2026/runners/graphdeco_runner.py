import os
import shlex
from pathlib import Path

from var2026.runners.base import MethodRunner


class GraphDeCoRunner(MethodRunner):
    name = "graphdeco"

    def __init__(self, environment: str = "graphdeco") -> None:
        self.environment = environment
        self.root = Path(__file__).resolve().parents[2]

    def train_command(self, scene: Path, output: Path) -> list[str]:
        iterations = os.environ.get("VAR2026_GRAPHDECO_ITERATIONS", "30000")
        extra_args = shlex.split(os.environ.get("VAR2026_GRAPHDECO_EXTRA_ARGS", ""))
        return [
            "conda", "run", "-n", self.environment, "python",
            str(self.root / "methods" / "graphdeco" / "train.py"),
            "-s", str(scene / "train"),
            "-m", str(output),
            "--iterations", iterations,
        ] + extra_args

    def infer_command(self, scene: Path, run: Path, output: Path) -> list[str]:
        return [
            "conda", "run", "-n", self.environment, "python",
            str(self.root / "var2026" / "runners" / "graphdeco_render.py"),
            "--poses", str(scene / "test" / "test_poses.csv"),
            "--run", str(run),
            "--out", str(output),
        ]
