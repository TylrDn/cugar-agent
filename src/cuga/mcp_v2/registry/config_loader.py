"""Hydra/OmegaConf adapter for loading registry configuration fragments."""

from __future__ import annotations

from pathlib import Path

from hydra import compose
from hydra.core.global_hydra import GlobalHydra
from hydra.initialize import initialize_config_dir
from omegaconf import DictConfig

from .errors import RegistryLoadError


def load_registry_config(entry_path: Path) -> list[tuple[Path, DictConfig]]:
    """Load registry documents using Hydra composition."""

    if not entry_path.exists():
        raise RegistryLoadError(f"Registry file not found: {entry_path}")

    # Ensure Hydra is clean for repeated calls (e.g., tests)
    GlobalHydra.instance().clear()
    config_dir = str(entry_path.parent.resolve())
    config_name = entry_path.stem

    with initialize_config_dir(config_dir=config_dir, version_base=None):
        cfg = compose(config_name=config_name)
        return [(entry_path.resolve(), cfg)]


__all__ = ["load_registry_config"]
