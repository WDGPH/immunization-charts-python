"""Shared pytest fixtures for unit, integration, and e2e tests.

This module provides:
- Temporary directory fixtures for file I/O testing
- Mock data generators (DataFrames, JSON artifacts)
- Configuration fixtures for parameter testing
- Cleanup utilities for test isolation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest
import yaml


@pytest.fixture
def tmp_test_dir() -> Generator[Path, None, None]:
    """Provide a temporary directory that's cleaned up after each test.

    Real-world significance:
    - Isolates file I/O tests from each other
    - Prevents test artifacts from polluting the file system
    - Required for testing file cleanup and artifact management

    Yields
    ------
    Path
        Absolute path to temporary directory (automatically deleted after test)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tmp_output_structure(tmp_test_dir: Path) -> Dict[str, Path]:
    """Create standard output directory structure expected by pipeline.

    Real-world significance:
    - Tests can assume artifacts/, pdf_individual/, metadata/ directories exist
    - Matches production output structure for realistic testing
    - Enables testing of file organization and cleanup steps

    Parameters
    ----------
    tmp_test_dir : Path
        Root temporary directory from fixture

    Returns
    -------
    Dict[str, Path]
        Keys: 'root', 'artifacts', 'pdf_individual', 'metadata', 'logs'
        Values: Paths to created directories
    """
    (tmp_test_dir / "artifacts").mkdir(exist_ok=True)
    (tmp_test_dir / "pdf_individual").mkdir(exist_ok=True)
    (tmp_test_dir / "metadata").mkdir(exist_ok=True)
    (tmp_test_dir / "logs").mkdir(exist_ok=True)

    return {
        "root": tmp_test_dir,
        "artifacts": tmp_test_dir / "artifacts",
        "pdf_individual": tmp_test_dir / "pdf_individual",
        "metadata": tmp_test_dir / "metadata",
        "logs": tmp_test_dir / "logs",
    }


@pytest.fixture
def default_vaccine_reference() -> Dict[str, list]:
    """Provide a minimal vaccine reference for testing.

    Real-world significance:
    - Maps vaccine codes to component diseases
    - Used by preprocess to expand vaccine records into diseases
    - Affects disease coverage text in notices

    Returns
    -------
    Dict[str, list]
        Maps vaccine codes to disease components, e.g. {"DTaP": ["Diphtheria", "Tetanus", "Pertussis"]}
    """
    return {
        "DTaP": ["Diphtheria", "Tetanus", "Pertussis"],
        "IPV": ["Polio"],
        "MMR": ["Measles", "Mumps", "Rubella"],
        "Varicella": ["Chickenpox"],
        "MenC": ["Meningococcal"],
        "PCV": ["Pneumococcal"],
        "Hib": ["Haemophilus influenzae"],
        "HBV": ["Hepatitis B"],
        "HPV": ["Human Papillomavirus"],
    }


@pytest.fixture
def default_config(tmp_output_structure: Dict[str, Path]) -> Dict[str, Any]:
    """Provide a minimal pipeline configuration for testing.

    Real-world significance:
    - Tests can assume this config structure is valid
    - Enables testing of feature flags (qr.enabled, encryption.enabled, etc.)
    - Matches production config schema

    Parameters
    ----------
    tmp_output_structure : Dict[str, Path]
        Output directories from fixture (used for config paths)

    Returns
    -------
    Dict[str, Any]
        Configuration dict with all standard sections
    """
    return {
        "pipeline": {
            "auto_remove_output": False,
            "keep_intermediate_files": False,
        },
        "qr": {
            "enabled": True,
            "payload_template": "https://example.com/vac/{client_id}",
        },
        "encryption": {
            "enabled": False,
            "password": {
                "template": "Password123",
            },
        },
        "bundling": {
            "bundle_size": 100,
            "enabled": False,
        },
        "chart_diseases_header": [
            "Diphtheria",
            "Tetanus",
            "Pertussis",
            "Polio",
            "Measles",
            "Mumps",
            "Rubella",
        ],
        "replace_unspecified": [],
    }


@pytest.fixture
def config_file(tmp_test_dir: Path, default_config: Dict[str, Any]) -> Path:
    """Create a temporary config file with default configuration.

    Real-world significance:
    - Tests that need to load config from disk can use this fixture
    - Enables testing of config loading and validation
    - Provides realistic config for integration tests

    Parameters
    ----------
    tmp_test_dir : Path
        Root temporary directory
    default_config : Dict[str, Any]
        Default configuration dict

    Returns
    -------
    Path
        Path to created YAML config file
    """
    config_path = tmp_test_dir / "parameters.yaml"
    with open(config_path, "w") as f:
        yaml.dump(default_config, f)
    return config_path


@pytest.fixture
def vaccine_reference_file(
    tmp_test_dir: Path, default_vaccine_reference: Dict[str, list]
) -> Path:
    """Create a temporary vaccine reference file.

    Real-world significance:
    - Tests that need vaccine mapping can load from disk
    - Enables testing of vaccine expansion into component diseases
    - Matches production vaccine_reference.json location/format

    Parameters
    ----------
    tmp_test_dir : Path
        Root temporary directory
    default_vaccine_reference : Dict[str, list]
        Vaccine reference dict

    Returns
    -------
    Path
        Path to created JSON vaccine reference file
    """
    vaccine_ref_path = tmp_test_dir / "vaccine_reference.json"
    with open(vaccine_ref_path, "w") as f:
        json.dump(default_vaccine_reference, f)
    return vaccine_ref_path


@pytest.fixture
def run_id() -> str:
    """Provide a consistent run ID for testing artifact generation.

    Real-world significance:
    - Artifacts are stored with run_id to enable comparing multiple pipeline runs
    - Enables tracking of which batch processed which clients
    - Required for reproducibility testing

    Returns
    -------
    str
        Example run ID in format used by production code
    """
    return "test_run_20250101_120000"


# Markers fixture for organizing test execution
@pytest.fixture(params=["unit", "integration", "e2e"])
def test_layer(request: pytest.FixtureRequest) -> str:
    """Fixture to identify which test layer is running (informational only).

    Real-world significance:
    - Documents which test layer is executing (for reporting/analysis)
    - Can be used by conftest hooks to apply layer-specific setup

    Yields
    ------
    str
        Layer name: "unit", "integration", or "e2e"
    """
    return request.param
