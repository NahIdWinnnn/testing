from abc import ABC, abstractmethod
from pathlib import Path


class MethodRunner(ABC):
    name: str

    @abstractmethod
    def train_command(self, scene: Path, output: Path) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def infer_command(self, scene: Path, run: Path, output: Path) -> list[str]:
        raise NotImplementedError
