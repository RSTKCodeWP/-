# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2025 VueOSD — https://github.com/wkumik/Digital-FPV-OSD-Tool
"""Shared subprocess helpers — suppress console windows on Windows."""

import sys
import subprocess


def _hidden_popen(*args, **kwargs):
    """subprocess.Popen wrapper that never shows a console window on Windows."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault("startupinfo", si)
        kwargs.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
    return subprocess.Popen(*args, **kwargs)


def _hidden_run(*args, **kwargs):
    """subprocess.run wrapper that never shows a console window on Windows."""
    if sys.platform == "win32":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs.setdefault("startupinfo", si)
        kwargs.setdefault("creationflags", 0x08000000)  # CREATE_NO_WINDOW
    return subprocess.run(*args, **kwargs)
