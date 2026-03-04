"""Test fixtures — fresh SQLite database per test."""


import pytest

import aiperture.config
from aiperture import plugins
from aiperture.db.engine import init_db, reset_engine


@pytest.fixture(autouse=True)
def _reset_plugins():
    """Reset plugin registry before each test."""
    plugins.reset()
    yield
    plugins.reset()


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Create a fresh SQLite database for each test."""
    db_path = tmp_path / "test.db"
    aiperture.config.settings = aiperture.config.Settings(
        db_path=str(db_path),
        artifact_storage_dir=str(tmp_path / "artifacts"),
    )
    reset_engine()
    init_db()
    yield
    reset_engine()
