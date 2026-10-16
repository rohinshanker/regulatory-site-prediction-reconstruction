"""Shared real backend release fixture."""

import os

import pytest

from regsite.backend import RnaStructure


@pytest.fixture(scope="session")
def real_backend():
    root = os.environ.get("REGSITE_RNASTRUCTURE")
    if not root:
        pytest.skip("set REGSITE_RNASTRUCTURE for required release integration tests")
    return RnaStructure.open(root)
