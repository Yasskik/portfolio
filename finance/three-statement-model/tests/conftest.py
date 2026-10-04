import copy

import pytest

import data_loader as dl
import model as M

TICKERS = ["AAPL", "MSFT", "KO", "T", "F"]


@pytest.fixture(scope="session")
def hist():
    return {t: dl.load_snapshot(t) for t in TICKERS}


def build(h, drivers=None):
    return M.ThreeStatementModel(copy.deepcopy(h.years), drivers, h.company, h.ticker)


@pytest.fixture(scope="session")
def base_models(hist):
    return {t: build(h) for t, h in hist.items()}
