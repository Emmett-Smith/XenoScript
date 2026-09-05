"""pytest bootstrap: make the sibling-import style used throughout
plinth/*.py (import lexer, import parser, ...) work no matter how pytest
discovers this test package."""
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_PLINTH_PKG_DIR = _TESTS_DIR.parent / "plinth"
_LANGUAGE_DIR = _TESTS_DIR.parent

for _p in (str(_PLINTH_PKG_DIR), str(_LANGUAGE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
