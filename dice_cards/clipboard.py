"""Clipboard support and output capturing."""

import io
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager


ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    return ANSI_ESCAPE.sub("", text)


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard."""
    if cmd := shutil.which("wl-copy"):
        subprocess.run([cmd], input=text, text=True, check=True)
    elif cmd := shutil.which("xclip"):
        subprocess.run([cmd, "-selection", "clipboard"], input=text, text=True, check=True)
    elif cmd := shutil.which("xsel"):
        subprocess.run([cmd, "--clipboard", "--input"], input=text, text=True, check=True)
    elif cmd := shutil.which("pbcopy"):
        subprocess.run([cmd], input=text, text=True, check=True)
    else:
        print("warning: no clipboard tool found", file=sys.stderr)


@contextmanager
def capture(clip: bool, lonelog: bool = False):
    """Context manager that captures stdout. Prints output and optionally copies to clipboard."""
    if not clip and not lonelog:
        yield
        return

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        yield
    finally:
        sys.stdout = old_stdout
        output = buf.getvalue()
        if lonelog and output:
            output = "-> " + output
        print(output, end="")
        if clip:
            copy_to_clipboard(strip_ansi(output).rstrip("\n"))
