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

    Automatically validates the configuration after loading. Raises
    clear exceptions if validation fails, enabling fail-fast behavior
    for infrastructure errors.

    Parameters
    ----------
    config_path : Path, optional
        Path to the configuration file. If not provided, uses the default
        location (config/parameters.yaml in the project root).

    Returns
    -------
    Dict[str, Any]
        Parsed and validated YAML configuration as a nested dictionary.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    yaml.YAMLError
        If the configuration file is invalid YAML.
    ValueError
        If the configuration fails validation (see validate_config).
    """
    if config_path is None:
        config_path = DEFAULT_CONFIG_PATH

    config_path = Path(config_path)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    validate_config(config)
    return config


def validate_config(config: Dict[str, Any]) -> None:
    """Validate the entire configuration for consistency and required values.

    Validates all conditional and required configuration keys across the
    entire config. Raises clear exceptions if validation fails, allowing
    the pipeline to fail-fast with actionable error messages.

    Parameters
    ----------
    config : Dict[str, Any]
        Configuration dictionary (result of load_config).

    Raises
    ------
    ValueError
        If required configuration is missing or invalid.

    Notes
    -----
    **Validation checks:**

    - **QR Generation:** If qr.enabled=true, requires qr.payload_template (non-empty string)
    - **Typst Compilation:** If typst.bin is set, must be a string
    - **PDF Bundling:** If bundle_size > 0, must be positive integer; group_by must be valid enum
    - **Encryption:** If encryption.enabled=true, requires password.template
    - **Cleanup:** If delete_unencrypted_pdfs is set, must be boolean

    **Validation philosophy:**
    - Infrastructure errors (missing config) raise immediately (fail-fast)
    - All error messages are clear and actionable
    - Config is validated once at load time, not per-step
    """
    # Validate QR config
    qr_config = config.get("qr", {})
    qr_enabled = qr_config.get("enabled", True)

    if qr_enabled:
        payload_template = qr_config.get("payload_template")
        if not payload_template:
            raise ValueError(
                "QR code generation is enabled but qr.payload_template is not specified. "
                "Please define qr.payload_template in config/parameters.yaml "
                "or set qr.enabled to false."
            )

        if not isinstance(payload_template, str):
            raise ValueError(
                f"qr.payload_template must be a string, got {type(payload_template).__name__}"
            )

    # Validate Typst config
    typst_config = config.get("typst", {})
    typst_bin = typst_config.get("bin", "typst")
    if not isinstance(typst_bin, str):
        raise ValueError(f"typst.bin must be a string, got {type(typst_bin).__name__}")

    # Validate Bundling config
    bundling_config = config.get("bundling", {})
    bundle_size = bundling_config.get("bundle_size", 0)

    # First validate type before comparing values
    if bundle_size != 0:  # Only validate if bundle_size is explicitly set
        if not isinstance(bundle_size, int):
            raise ValueError(
                f"bundling.bundle_size must be an integer, got {type(bundle_size).__name__}"
            )
        if bundle_size <= 0:
            raise ValueError(
                f"bundling.bundle_size must be positive, got {bundle_size}"
            )

        # Validate group_by strategy
        group_by = bundling_config.get("group_by")
        from .enums import BundleStrategy

        try:
            if group_by is not None:
                BundleStrategy.from_string(group_by)
        except ValueError as exc:
            raise ValueError(f"Invalid bundling.group_by strategy: {exc}") from exc

    # Validate Encryption config
    encryption_config = config.get("encryption", {})
    encryption_enabled = encryption_config.get("enabled", False)

    if encryption_enabled:
        password_config = encryption_config.get("password", {})
        password_template = password_config.get("template")
        if not password_template:
            raise ValueError(
                "Encryption is enabled but encryption.password.template is not specified. "
                "Please define encryption.password.template in config/parameters.yaml "
                "or set encryption.enabled to false."
            )

        if not isinstance(password_template, str):
            raise ValueError(
                f"encryption.password.template must be a string, "
                f"got {type(password_template).__name__}"
            )

    # Validate Cleanup config
    cleanup_config = config.get("cleanup", {})
    delete_unencrypted = cleanup_config.get("delete_unencrypted_pdfs", False)
    if not isinstance(delete_unencrypted, bool):
        raise ValueError(
            f"cleanup.delete_unencrypted_pdfs must be a boolean, "
            f"got {type(delete_unencrypted).__name__}"
        )
