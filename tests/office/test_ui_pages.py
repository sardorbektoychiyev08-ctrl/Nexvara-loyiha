"""Click through UI pages in a real NEXVARA window (throwaway data folder).

The scripts open a window on screen, so they run with the Office tests
(NEXVARA_RUN_OFFICE=1). Each script prints its findings and exits 0 on PASS.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.office,
    pytest.mark.skipif(
        os.environ.get("NEXVARA_RUN_OFFICE") != "1",
        reason="set NEXVARA_RUN_OFFICE=1 to open real windows",
    ),
]

SCRIPTS = Path(__file__).parents[1] / "ui_scripts"
ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("script", sorted(p.name for p in SCRIPTS.glob("*.py")))
def test_ui_script(script):
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / script)], capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env, timeout=600, cwd=ROOT,
    )  # fmt: skip
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
