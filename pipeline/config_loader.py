"""Configuration loading utilities for the immunization pipeline.

Provides a centralized way to load and validate the parameters.yaml
configuration file across all pipeline scripts.
"""

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = SCRIPT_DIR.parent / "config" / "parameters.yaml"


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse the parameters.yaml configuration file.

    Parameters
    ----------
    config_path : Path, optional
        Path to the configuration file. If not provided, uses the default
        location (config/parameters.yaml in the project root).

    Returns
    -------
    Dict[str, Any]
        Parsed YAML configuration as a nested dictionary.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    yaml.YAMLError
        If the configuration file is invalid YAML.
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    return config


def get_config_value(
    config: Dict[str, Any],
    key_path: str,
    default: Any = None,
) -> Any:
    """Get a nested value from the configuration using dot notation.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary (result of load_config).
    key_path : str
        Dot-separated path to the value (e.g., "batching.batch_size").
    default : Any, optional
        Default value if the key path is not found.

    Returns
    -------
    Any
        The configuration value, or the default if not found.

    Examples
    --------
    >>> config = load_config()
    >>> batch_size = get_config_value(config, "batching.batch_size", 100)
    >>> font_path = get_config_value(config, "typst.font_path")
    """
    keys = key_path.split(".")
    value = config

    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default

    return value if value is not None else default
