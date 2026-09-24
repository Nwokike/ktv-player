"""Every source file must parse under the oldest interpreter we support.

The dev venv (and ``requires-python``) sit on 3.14, whose PEG parser accepts
grammar newer runtimes reject — unparenthesized ``except A, B:`` (PEP 758) is
the one that has bitten this repo, landing silently in the player, the HLS
proxy and the local scanner. Anything a 3.12 interpreter cannot parse is a
guaranteed ``SyntaxError`` the moment the app is packaged, so the quality gate
fails the build instead of the phone.
"""

import ast
from pathlib import Path

MIN_PYTHON = (3, 12)
SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def _python_files() -> list[Path]:
    return sorted(p for p in SRC_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def test_src_tree_is_not_empty() -> None:
    assert len(_python_files()) > 20, (
        "src tree looks wrong — guard would pass vacuously"
    )


def test_every_source_file_parses_on_minimum_python() -> None:
    failures: list[str] = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), feature_version=MIN_PYTHON)
        except SyntaxError as ex:
            rel = path.relative_to(SRC_ROOT.parent)
            failures.append(f"{rel}:{ex.lineno}: {ex.msg}")
    assert not failures, "parses only on Python 3.14+:\n" + "\n".join(failures)


def test_no_unparenthesized_multi_exception_handlers() -> None:
    """Direct guard for the PEP 758 form, named for readable CI failures."""
    import re

    pattern = re.compile(r"^\s*except\s+[A-Za-z_][\w.]*\s*,\s*[A-Za-z_]", re.MULTILINE)
    offenders = [
        str(p.relative_to(SRC_ROOT.parent))
        for p in _python_files()
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"unparenthesized except handlers in: {offenders}"
