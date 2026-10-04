"""Recalculate .xlsx files with LibreOffice (headless) and read back the cached values."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")


def recalc(xlsx: Path, outdir: Path | None = None) -> Path:
    """Open `xlsx` in LibreOffice, recalculate every formula, save a copy and return its path."""
    if SOFFICE is None:
        raise RuntimeError("LibreOffice (soffice) not found")
    outdir = Path(outdir or tempfile.mkdtemp(prefix="lo_recalc_"))
    outdir.mkdir(parents=True, exist_ok=True)
    profile = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    subprocess.run([SOFFICE, f"-env:UserInstallation=file://{profile}", "--headless", "--calc",
                    "--convert-to", "xlsx", "--outdir", str(outdir), str(xlsx)],
                   check=True, capture_output=True, timeout=300)
    shutil.rmtree(profile, ignore_errors=True)
    return outdir / Path(xlsx).name


def recalc_values(xlsx: Path):
    """Return an openpyxl workbook (data_only) with LibreOffice-computed values."""
    with tempfile.TemporaryDirectory() as d:
        out = recalc(Path(xlsx), Path(d))
        return openpyxl.load_workbook(out, data_only=True)
