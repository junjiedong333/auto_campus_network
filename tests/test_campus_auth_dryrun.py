import subprocess
import sys


def test_dryrun_exits_zero_without_login():
    r = subprocess.run(
        [sys.executable, "src/campus_auth.py", "--dry-run"],
        capture_output=True, text=True, timeout=90,
    )
    assert r.returncode == 0
    out = r.stdout.lower()
    assert "eth_up" in out or "eth" in out
