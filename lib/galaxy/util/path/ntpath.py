"""Galaxy "safe" path functions forced to work with Windows-style paths regardless of current platform
"""
from __future__ import absolute_import

import ntpath  # noqa: I100 See https://github.com/PyCQA/flake8-import-order/pull/115
import sys

from . import _build_self


_build_self(sys.modules[__name__], ntpath)
