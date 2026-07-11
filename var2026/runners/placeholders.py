from pathlib import Path

from var2026.runners.base import MethodRunner


class PlaceholderRunner(MethodRunner):
    def __init__(self, name: str) -> None:
        self.name = name

    def _unsupported(self) -> None:
        raise NotImplementedError(
            f"Method {self.name!r} is registered as a placeholder but is not implemented."
        )

    def train_command(self, scene: Path, output: Path) -> list[str]:
        self._unsupported()

    def infer_command(self, scene: Path, run: Path, output: Path) -> list[str]:
        self._unsupported()
