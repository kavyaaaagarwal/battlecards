import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_committed_openapi_is_up_to_date():
    r = subprocess.run([sys.executable, "scripts/export_openapi.py", "--check"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
