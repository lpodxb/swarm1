import yaml
from pathlib import Path
from typing import Any, Dict


class ConfigLoader:
    def __init__(self, path: str = "configs/config.yaml"):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path}")
        with self.path.open("r") as f:
            data = yaml.safe_load(f)
        return data
