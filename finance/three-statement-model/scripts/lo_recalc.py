"""Recalculate .xlsx files with LibreOffice (headless) and read back the computed values.

LibreOffice's plain `--convert-to` recalculates on load but does not iterate a circular
reference to convergence. So `recalc()` runs a small LibreOffice Basic macro (written into a
throw-away user profile) that opens the workbook, keeps iterative calculation on
(IterationCount / IterationEpsilon), runs a full hard recalculation `passes` times (each pass restarts the iteration from the
latest values, like pressing F9 repeatedly) and saves a copy.
This is the same as pressing Ctrl+Shift+F9 in Calc, or F9 in Excel with iteration enabled.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import openpyxl

SOFFICE = shutil.which("soffice") or shutil.which("libreoffice")

_MODULE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE script:module PUBLIC "-//OpenOffice.org//DTD OfficeDocument 1.0//EN" "module.dtd">
<script:module xmlns:script="http://openoffice.org/2000/script" script:name="Module1" script:language="StarBasic">
Sub Recalc(inp As String, outp As String, iters As Integer)
  Dim a(0) As New com.sun.star.beans.PropertyValue
  a(0).Name = "Hidden" : a(0).Value = True
  doc = StarDesktop.loadComponentFromURL(ConvertToURL(inp), "_blank", 0, a())
  f = FreeFile
  Open outp &amp; ".log" For Output As #f
  Print #f, "file_iterate=" &amp; doc.IsIterationEnabled &amp; ";file_count=" &amp; doc.IterationCount
  doc.IsIterationEnabled = True
  doc.IterationCount = iters
  doc.IterationEpsilon = 0.000000001
__PASSES__  Close #f
  Dim b(0) As New com.sun.star.beans.PropertyValue
  b(0).Name = "FilterName" : b(0).Value = "Calc MS Excel 2007 XML"
  doc.storeToURL(ConvertToURL(outp), b())
  doc.close(True)
End Sub
</script:module>
"""


def _profile(passes: int) -> Path:
    prof = Path(tempfile.mkdtemp(prefix="lo_profile_"))
    subprocess.run([SOFFICE, f"-env:UserInstallation=file://{prof}", "--headless", "--terminate_after_init"],
                   capture_output=True, timeout=120)
    # Threaded formula-group calculation can deadlock on circular references: switch it off.
    reg = prof / "user" / "registrymodifications.xcu"
    items = "".join(
        f'<item oor:path="/org.openoffice.Office.Calc/Formula/Calculation"><prop oor:name="{k}" oor:op="fuse">'
        f'<value>false</value></prop></item>' for k in ("UseThreadedCalculationForFormulaGroups", "UseOpenCL"))
    if reg.exists():
        txt = reg.read_text(encoding="utf-8")
        reg.write_text(txt.replace("</oor:items>", items + "</oor:items>"), encoding="utf-8")
    std = prof / "user" / "basic" / "Standard"
    std.mkdir(parents=True, exist_ok=True)
    (std / "Module1.xba").write_text(_MODULE.replace("__PASSES__", "  doc.calculateAll()\n" * passes), encoding="utf-8")
    return prof


def recalc(xlsx: Path, outdir: Path | None = None, iterations: int = 1000, passes: int = 20) -> Path:
    """Open `xlsx` in LibreOffice, hard-recalculate with iteration, save a copy and return its path."""
    if SOFFICE is None:
        raise RuntimeError("LibreOffice (soffice) not found")
    xlsx = Path(xlsx).resolve()
    outdir = Path(outdir or tempfile.mkdtemp(prefix="lo_recalc_")).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / xlsx.name
    if out == xlsx:
        raise ValueError("output would overwrite the input")
    out.unlink(missing_ok=True)
    prof = _profile(passes)
    work = Path(tempfile.mkdtemp(prefix="lo_work_"))   # fresh folder: no stale lock files, no dialogs
    try:
        src, dst = work / "in.xlsx", work / "out.xlsx"
        shutil.copy(xlsx, src)
        macro = f'macro:///Standard.Module1.Recalc("{src}","{dst}",{int(iterations)})'
        subprocess.run([SOFFICE, f"-env:UserInstallation=file://{prof}", "--headless", "--norestore", macro],
                       check=True, capture_output=True, timeout=300)
        if dst.exists():
            shutil.move(str(dst), out)
    finally:
        shutil.rmtree(prof, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)
    if not out.exists():
        raise RuntimeError(f"LibreOffice did not produce {out}")
    return out


def recalc_values(xlsx: Path):
    """Return an openpyxl workbook (data_only) with LibreOffice-computed values."""
    with tempfile.TemporaryDirectory() as d:
        out = recalc(Path(xlsx), Path(d))
        return openpyxl.load_workbook(out, data_only=True)
