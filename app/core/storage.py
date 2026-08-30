from __future__ import annotations
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

class CatalogStorage(ABC):
    @abstractmethod
    def restore(self, destination: Path) -> bool: ...
    @abstractmethod
    def persist(self, source: Path) -> None: ...

class LocalFileStorage(CatalogStorage):
    def __init__(self, path: str | Path): self.path = Path(path)
    def restore(self, destination: Path) -> bool:
        if not self.path.exists(): return False
        destination.parent.mkdir(parents=True, exist_ok=True)
        if self.path.resolve() != destination.resolve(): shutil.copy2(self.path, destination)
        return True
    def persist(self, source: Path) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.resolve() != source.resolve(): shutil.copy2(source, self.path)

class GitHubArtifactStorage(LocalFileStorage):
    pass
