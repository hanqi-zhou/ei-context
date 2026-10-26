"""Package imports must not require credentials or network access."""

import subprocess
import sys


def test_import_offline() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import socket; socket.socket = None; import ei_context"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
