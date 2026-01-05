from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import curve_fit


def exp_decline(t: np.ndarray, qi: float, di: float) -> np.ndarray:
    """Exponential decline: q(t)=qi*exp(-di*t). t in days."""
    return qi * np.exp(-di * t)


def hyp_decline(t: np.ndarray, qi: float, di: float, b: float) -> np.ndarray:
    """Hyperbolic decline: q(t)=qi / (1 + b*di*t)^(1/b)."""
    return qi / np.power(1.0 + b * di * t, 1.0 / b)


@dataclass(frozen=True)
class DCAFit:
    model: str  # "exp" or "hyp"
    params: tuple[float, ...]
    rmse: float
    aic: float

    def predict(self, t: np.ndarray) -> np.ndarray:
        if self.model == "exp":
            qi, di = self.params
            return exp_decline(t, qi, di)
        if self.model == "hyp":
            qi, di, b = self.params
            return hyp_decline(t, qi, di, b)
        raise ValueError(f"Unknown model: {self.model}")


def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def _aic(n: int, rss: float, k: int) -> float:
    # AIC = n*ln(RSS/n) + 2k
    rss = max(rss, 1e-12)
    return float(n * np.log(rss / n) + 2 * k)


def fit_exp(t: np.ndarray, q: np.ndarray) -> DCAFit:
    # initial guesses: qi ~ first nonzero, di small positive
    qi0 = float(np.nanmax(q[: max(1, min(30, len(q)))]) or np.nanmax(q) or 1.0)
    di0 = 1e-3
    popt, _ = curve_fit(
        exp_decline,
        t,
        q,
        p0=[qi0, di0],
        bounds=([0.0, 0.0], [np.inf, 10.0]),
        maxfev=20000,
    )
    pred = exp_decline(t, *popt)
    resid = q - pred
    rss = float(np.sum(resid**2))
    return DCAFit(model="exp", params=(float(popt[0]), float(popt[1])), rmse=_rmse(q, pred), aic=_aic(len(q), rss, 2))


def fit_hyp(t: np.ndarray, q: np.ndarray) -> DCAFit:
    qi0 = float(np.nanmax(q[: max(1, min(30, len(q)))]) or np.nanmax(q) or 1.0)
    di0 = 1e-3
    b0 = 0.5
    popt, _ = curve_fit(
        hyp_decline,
        t,
        q,
        p0=[qi0, di0, b0],
        bounds=([0.0, 0.0, 0.0], [np.inf, 10.0, 2.0]),
        maxfev=40000,
    )
    pred = hyp_decline(t, *popt)
    resid = q - pred
    rss = float(np.sum(resid**2))
    return DCAFit(
        model="hyp",
        params=(float(popt[0]), float(popt[1]), float(popt[2])),
        rmse=_rmse(q, pred),
        aic=_aic(len(q), rss, 3),
    )


def fit_best(t: np.ndarray, q: np.ndarray) -> DCAFit:
    """Fit both exp and hyperbolic; return lowest AIC."""
    exp_fit = fit_exp(t, q)
    hyp_fit = fit_hyp(t, q)
    return exp_fit if exp_fit.aic <= hyp_fit.aic else hyp_fit


