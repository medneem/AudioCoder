"""Windows Explorer handoff for successfully rendered output files."""
from pathlib import Path
import subprocess
import sys


def reveal_output_file(path: Path) -> None:
    """Open Explorer at the output folder and select the converted file."""
    if sys.platform != "win32":
        raise OSError("Открытие папки результата поддерживается в Windows.")
    destination = Path(path).resolve()
    subprocess.Popen(
        ["explorer.exe", "/select,", str(destination)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
