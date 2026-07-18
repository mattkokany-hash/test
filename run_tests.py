#!/usr/bin/env python3
"""Minimal stdlib test runner so the suite runs without pytest installed.

Discovers ``test_*`` functions in ``tests/*.py`` and executes them. The tests
are plain-assert pytest-style functions, so `pytest` also runs them unchanged.

    python3 run_tests.py
"""

from __future__ import annotations

import importlib.util
import inspect
import pathlib
import sys
import traceback


class _MonkeyPatch:
    """Just enough of pytest's monkeypatch for these tests: setattr + undo."""

    def __init__(self):
        self._undo: list = []

    def setattr(self, target, name, value):
        self._undo.append((target, name, getattr(target, name)))
        setattr(target, name, value)

    def undo(self):
        for target, name, old in reversed(self._undo):
            setattr(target, name, old)
        self._undo.clear()


def load_module(path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    root = pathlib.Path(__file__).parent
    sys.path.insert(0, str(root))
    test_files = sorted((root / "tests").glob("test_*.py"))

    passed = failed = 0
    failures: list[str] = []
    for tf in test_files:
        mod = load_module(tf)
        for name in dir(mod):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            mp = None
            try:
                if "monkeypatch" in inspect.signature(fn).parameters:
                    mp = _MonkeyPatch()
                    fn(monkeypatch=mp)
                else:
                    fn()
                passed += 1
                print(f"  PASS  {tf.name}::{name}")
            except Exception:  # noqa: BLE001 -- test harness reports everything
                failed += 1
                failures.append(f"{tf.name}::{name}\n{traceback.format_exc()}")
                print(f"  FAIL  {tf.name}::{name}")
            finally:
                if mp is not None:
                    mp.undo()

    print("\n" + "=" * 60)
    print(f"{passed} passed, {failed} failed")
    if failures:
        print("=" * 60)
        for f in failures:
            print(f)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
