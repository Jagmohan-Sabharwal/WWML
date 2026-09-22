"""Progress means asset planning and never treats an empty plan as complete."""

import pytest

from app.api.editor.dashboard import planning_progress


@pytest.mark.parametrize(
    "ready,required,unplanned,expected",
    [
        (0, 0, 0, None),
        (0, 0, 2, 0),
        (1, 3, 1, 25),
        (3, 3, 0, 100),
        (1, 3, 0, 33.3),
        (9999, 10000, 0, 99.9),
    ],
)
def test_planning_progress(ready, required, unplanned, expected):
    assert planning_progress(ready, required, unplanned) == expected
