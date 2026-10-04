"""Copy the master ui_theme.py into every finance project and regenerate .streamlit/config.toml.

Each project vendors its own copy so it still runs standalone after being cloned on its own.
Usage:  python finance/_shared/sync_theme.py          (from the repo root or anywhere)
        python finance/_shared/sync_theme.py --check  (exit 1 if any copy is out of date)
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINANCE = HERE.parent
PROJECTS = ["dcf-valuation-model", "financial-statement-analyzer", "loan-investment-calculator",
            "monte-carlo-simulator", "three-statement-model"]


def _config_text() -> str:
    spec = importlib.util.spec_from_file_location("ui_theme_master", HERE / "ui_theme.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # needs streamlit + plotly installed
    return mod.config_toml()


def main(check: bool = False) -> int:
    master = (HERE / "ui_theme.py").read_text()
    cfg = _config_text()
    stale = []
    for name in PROJECTS:
        proj = FINANCE / name
        targets = {proj / "ui_theme.py": master, proj / ".streamlit" / "config.toml": cfg}
        for path, text in targets.items():
            if path.exists() and path.read_text() == text:
                continue
            stale.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    for p in stale:
        print(("STALE  " if check else "wrote  ") + str(p.relative_to(FINANCE)))
    if not stale:
        print("all projects in sync")
    return 1 if (check and stale) else 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv))
