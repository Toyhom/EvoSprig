from pathlib import Path

import pytest

from evosprig.core.spec import load_spec

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def example_root():
    return ROOT / "examples" / "hello"


@pytest.fixture
def spec(example_root):
    return load_spec(example_root / "agent.yaml")
