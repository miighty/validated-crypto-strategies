from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegressionResult:
    coefficients: pd.Series
    r_squared: float
    observations: int


def expanding_wild_events(
    returns: pd.Series,
    quantile: float = 0.95,
    minimum_prior_observations: int = 60,
) -> pd.DataFrame:
    """Flag large absolute returns using only observations available before each event."""
    if not 0 < quantile < 1:
        raise ValueError("quantile must be strictly between zero and one")
    clean = returns.astype(float).sort_index()
    absolute = clean.abs()
    threshold = absolute.expanding(min_periods=minimum_prior_observations).quantile(quantile).shift(1)
    return pd.DataFrame(
        {
            "return": clean,
            "absolute_return": absolute,
            "threshold": threshold,
            "is_wild": absolute.ge(threshold) & threshold.notna(),
        }
    )


def rolling_beta(
    asset_returns: pd.DataFrame,
    btc_returns: pd.Series,
    lookback: int = 60,
    minimum_observations: int = 40,
) -> pd.DataFrame:
    """Estimate trailing BTC betas without using the current observation."""
    aligned_btc = btc_returns.astype(float).reindex(asset_returns.index)
    variance = aligned_btc.rolling(lookback, min_periods=minimum_observations).var().shift(1)
    output = {}
    for symbol in asset_returns:
        covariance = (
            asset_returns[symbol]
            .astype(float)
            .rolling(lookback, min_periods=minimum_observations)
            .cov(aligned_btc)
            .shift(1)
        )
        output[symbol] = covariance / variance
    return pd.DataFrame(output, index=asset_returns.index)


def residual_opening_gap(
    equity_gaps: pd.DataFrame,
    btc_event_returns: pd.Series,
    betas: pd.DataFrame,
    factor_gaps: pd.DataFrame | None = None,
    factor_loadings: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return the equity gap unexplained by BTC and optional pre-estimated factors."""
    expected = betas.mul(btc_event_returns.reindex(equity_gaps.index), axis=0)
    if factor_gaps is not None or factor_loadings is not None:
        if factor_gaps is None or factor_loadings is None:
            raise ValueError("factor_gaps and factor_loadings must be provided together")
        common = factor_gaps.columns.intersection(factor_loadings.index)
        expected = expected.add(
            factor_gaps[common].to_numpy() @ factor_loadings.loc[common].to_numpy(),
            fill_value=0.0,
        )
    return equity_gaps - expected


def classify_liquidation_events(
    long_liquidations: pd.Series,
    short_liquidations: pd.Series,
    absolute_event_usd: float = 800_000_000,
    normalized_quantile: float = 0.99,
    rolling_hours: int = 24,
) -> pd.DataFrame:
    """Classify liquidation cascades using absolute and expanding normalized thresholds."""
    frame = pd.concat(
        {
            "long": long_liquidations.astype(float),
            "short": short_liquidations.astype(float),
        },
        axis=1,
    ).fillna(0.0)
    rolled = frame.rolling(rolling_hours, min_periods=rolling_hours).sum()
    total = rolled.sum(axis=1)
    normalized_threshold = (
        total.expanding(min_periods=max(rolling_hours * 3, 60))
        .quantile(normalized_quantile)
        .shift(1)
    )
    is_event = total.ge(absolute_event_usd) | total.ge(normalized_threshold)
    imbalance = (rolled["short"] - rolled["long"]) / total.replace(0, np.nan)
    event_type = pd.Series("none", index=frame.index, dtype="object")
    event_type.loc[is_event & imbalance.lt(-1 / 3)] = "long_cascade"
    event_type.loc[is_event & imbalance.gt(1 / 3)] = "short_squeeze"
    event_type.loc[is_event & imbalance.between(-1 / 3, 1 / 3, inclusive="both")] = "two_sided"
    return pd.DataFrame(
        {
            "long_liquidations_24h": rolled["long"],
            "short_liquidations_24h": rolled["short"],
            "total_liquidations_24h": total,
            "normalized_threshold": normalized_threshold,
            "imbalance": imbalance,
            "is_event": is_event.fillna(False),
            "event_type": event_type,
        }
    )


def ols(y: pd.Series, features: pd.DataFrame) -> RegressionResult:
    """Small deterministic OLS helper with an intercept and complete-case filtering."""
    joined = pd.concat([y.rename("target"), features], axis=1).dropna()
    if len(joined) <= len(features.columns) + 1:
        raise ValueError("not enough complete observations for regression")
    x = np.column_stack([np.ones(len(joined)), joined[features.columns].to_numpy(float)])
    target = joined["target"].to_numpy(float)
    coefficients, *_ = np.linalg.lstsq(x, target, rcond=None)
    fitted = x @ coefficients
    residual_ss = float(np.square(target - fitted).sum())
    total_ss = float(np.square(target - target.mean()).sum())
    r_squared = 1.0 - residual_ss / total_ss if total_ss > 0 else 0.0
    names = ["intercept", *features.columns]
    return RegressionResult(pd.Series(coefficients, index=names), r_squared, len(joined))


def incremental_liquidation_value(
    equity_returns: pd.Series,
    btc_returns: pd.Series,
    btc_volatility: pd.Series,
    factor_returns: pd.DataFrame,
    liquidation_size: pd.Series,
    liquidation_imbalance: pd.Series,
) -> dict[str, RegressionResult | float]:
    """Compare explanatory fit with and without liquidation information."""
    base = pd.concat(
        [btc_returns.rename("btc_return"), btc_volatility.rename("btc_volatility"), factor_returns],
        axis=1,
    )
    augmented = base.assign(
        liquidation_size=liquidation_size,
        liquidation_imbalance=liquidation_imbalance,
    )
    base_result = ols(equity_returns, base)
    augmented_result = ols(equity_returns, augmented)
    return {
        "base": base_result,
        "augmented": augmented_result,
        "incremental_r_squared": augmented_result.r_squared - base_result.r_squared,
    }

