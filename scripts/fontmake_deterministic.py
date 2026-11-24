#!/usr/bin/env python3
"""Run fontmake with the pinned Python cu2qu arithmetic on every platform.

fontTools' compiled converter can differ by one ULP across architectures.
Rounding a resulting half-grid control point then changes an integer outline.
Only this process selects the shipped Python implementation; installed package
files and the parent environment are never modified.
"""
from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import importlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shlex
import sys
import tempfile

FONTTOOLS_VERSION = '4.60.1'
CU2QU_SOURCE_SHA256 = 'e8b4ded5923e8f15bccbbf6cfd41636e4785a0595e21e9132e6da3004faea864'


def converter_info():
    distribution = importlib.metadata.distribution('fonttools')
    source = Path(distribution.locate_file('fontTools/cu2qu/cu2qu.py'))
    if distribution.version != FONTTOOLS_VERSION:
        raise RuntimeError(f'Expected fontTools {FONTTOOLS_VERSION}, found {distribution.version}')
    digest = sha256(source.read_bytes()).hexdigest()
    if digest != CU2QU_SOURCE_SHA256:
        raise RuntimeError('Pinned fontTools Python cu2qu source differs; review the compiler pin')
    return dict(fonttools_version=distribution.version, cu2qu_implementation='python',
                source_sha256=digest), source


def load_python_cu2qu():
    """Load the pinned .py source without changing existing converter exports."""
    _, source = converter_info()
    name = 'fontTools.cu2qu._namche_python'
    if name not in sys.modules:
        specification = importlib.util.spec_from_file_location(name, source)
        module = importlib.util.module_from_spec(specification)
        sys.modules[name] = module
        specification.loader.exec_module(module)
    module = sys.modules[name]
    if module.COMPILED:
        raise RuntimeError('Expected the Python cu2qu implementation')
    return module


def activate_python_cu2qu():
    """Select the Python converter for static and interpolatable fontmake pens."""
    converter = load_python_cu2qu()
    for name in ('fontTools.cu2qu', 'fontTools.cu2qu.ufo', 'fontTools.pens.cu2quPen'):
        module = importlib.import_module(name)
        for function in ('curve_to_quadratic', 'curves_to_quadratic'):
            if hasattr(module, function):
                setattr(module, function, getattr(converter, function))
    return converter


@contextmanager
def fontmake_environment(environment):
    """Scope gftools' fontmake subprocesses to this explicit entry point."""
    info, _ = converter_info()
    print(f"Equal-ink compiler: fontTools {info['fonttools_version']}; Python cu2qu "
          f"sha256={info['source_sha256']}", flush=True)
    with tempfile.TemporaryDirectory(prefix='namche-fontmake-') as directory:
        launcher = Path(directory)/'fontmake'
        launcher.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+
                            shlex.quote(str(Path(__file__).resolve()))+' "$@"\n')
        launcher.chmod(0o755)
        child = dict(environment)
        child['PATH'] = directory+os.pathsep+child.get('PATH', '')
        yield child


def main():
    converter = activate_python_cu2qu()
    if sys.argv[1:] == ['--namche-cu2qu-info']:
        info, _ = converter_info()
        info['compiled'] = converter.COMPILED
        info['selected_module'] = importlib.import_module('fontTools.cu2qu').curve_to_quadratic.__module__
        print(json.dumps(info, sort_keys=True))
        return
    from fontmake.__main__ import main as fontmake_main
    fontmake_main()


if __name__ == '__main__':
    main()
