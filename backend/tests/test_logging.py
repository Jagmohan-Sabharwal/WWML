"""Application logging is machine-readable and not duplicated."""

import json
import logging

import pytest

from app.core.logging import configure_logging


def test_configuration_is_idempotent_and_applies_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("WARNING")
    configure_logging("WARNING")
    logger = logging.getLogger("wwml.test")
    logger.info("filtered")
    logger.warning("probe unavailable")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["message"] == "probe unavailable"
    assert record["level"] == "WARNING"
    assert record["logger"] == "wwml.test"
    assert record["timestamp"].endswith("+00:00")
