"""
Shared diagnostic and scoring module for Spatia composite indicators.

Implements the OECD Handbook / UNDP HDI methodology:
  1. Correlation matrix -> flag |r| > threshold
  2. KMO + Bartlett's test -> validate construct coherence
  3. PCA with varimax rotation -> report loadings and variance
  4. Variable selection -> drop redundant pairs
  5. Geometric mean -> partially compensatory aggregation

Usage:
  from scoring import (
      correlation_diagnostics, kmo_bartlett, pca_diagnostics,
      select_variables, geometric_mean_score, run_full_diagnostics,
      generate_report,
  )
"""

import json
import os
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

try:
    from factor_analyzer.factor_analyzer import (
        calculate_bartlett_sphericity,
        calculate_kmo,
    )
    HAS_FACTOR_ANALYZER = True
except ImportError:
    HAS_FACTOR_ANALYZER = False


# ── Correlation diagnostics ──────────────────────────────────────────────────

def correlation_diagnostics(
    df: pd.DataFrame,
    columns: list[str],
    threshold: float = 0.70,
) -> dict:
    """Compute Pearson correlation matrix and flag pairs above threshold.

    Returns dict with:
      - matrix: correlation matrix as nested dict
      - flagged_pairs: list of (col_a, col_b, r) where |r| > threshold
    """
    corr = df[columns].corr(method="pearson")
    flagged = []
    for i, a in enumerate(columns):
        for j, b in enumerate(columns):
            if j > i and abs(corr.loc[a, b]) > threshold:
                flagged.append((a, b, round(float(corr.loc[a, b]), 4)))

    return {
        "matrix": {c: {c2: round(float(corr.loc[c, c2]), 4) for c2 in columns}
                   for c in columns},
        "flagged_pairs": flagged,
        "threshold": threshold,
    }


# ── KMO and Bartlett's test ──────────────────────────────────────────────────

def kmo_bartlett(df: pd.DataFrame, columns: list[str]) -> dict:
    """Compute KMO measure and Bartlett's test of sphericity.

    KMO > 0.60 indicates adequate sampling for factor analysis.
    Bartlett's p < 0.05 rejects the null hypothesis of identity matrix.

    Requires factor_analyzer package. Returns fallback if not installed.
    """
    X = df[columns].dropna()

    if not HAS_FACTOR_ANALYZER:
        return {
            "kmo_overall": None,
            "kmo_per_variable": {},
            "bartlett_chi2": None,
            "bartlett_p": None,
            "warning": "factor_analyzer not installed; install with: pip install factor_analyzer",
        }

    if len(X) < len(columns) * 5:
        return {
            "kmo_overall": None,
            "kmo_per_variable": {},
            "bartlett_chi2": None,
            "bartlett_p": None,
            "warning": f"Insufficient observations ({len(X)}) for {len(columns)} variables",
        }

    try:
        chi2, p = calculate_bartlett_sphericity(X)
        kmo_per_var, kmo_overall = calculate_kmo(X)
        return {
            "kmo_overall": round(float(kmo_overall), 4),
            "kmo_per_variable": {c: round(float(v), 4)
                                 for c, v in zip(columns, kmo_per_var)},
            "bartlett_chi2": round(float(chi2), 2),
            "bartlett_p": float(p),
        }
    except Exception as e:
        return {
            "kmo_overall": None,
            "kmo_per_variable": {},
            "bartlett_chi2": None,
            "bartlett_p": None,
            "warning": f"KMO/Bartlett computation failed: {e}",
        }


# ── PCA diagnostics ─────────────────────────────────────────────────────────

def pca_diagnostics(df: pd.DataFrame, columns: list[str]) -> dict:
    """Run exploratory PCA and return variance, loadings, and rotated loadings.

    Returns dict with:
      - n_components_80pct: components needed for 80% cumulative variance
      - explained_variance: list of per-component variance ratios
      - cumulative_variance: list of cumulative variance ratios
      - loadings: dict of {PC1: {var: loading, ...}, ...} (first 5 PCs)
      - rotated_loadings: varimax-rotated loadings (if factor_analyzer available)
    """
    X = df[columns].dropna().values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    n_max = min(len(columns), X_scaled.shape[0])
    pca = PCA(n_components=n_max)
    pca.fit(X_scaled)

    cumvar = np.cumsum(pca.explained_variance_ratio_)
    n80 = max(2, int(np.argmax(cumvar >= 0.80)) + 1)
    n80 = min(n80, len(columns))

    # Raw loadings (correlation between variables and PCs)
    loadings = pca.components_.T * np.sqrt(pca.explained_variance_)
    n_report = min(5, n_max)
    loadings_dict = {}
    for pc_idx in range(n_report):
        pc_name = f"PC{pc_idx + 1}"
        loadings_dict[pc_name] = {
            col: round(float(loadings[i, pc_idx]), 4)
            for i, col in enumerate(columns)
        }

    # Varimax rotation
    rotated_dict = {}
    if HAS_FACTOR_ANALYZER:
        try:
            from factor_analyzer import Rotator
            raw_loadings = pca.components_[:n80].T * np.sqrt(
                pca.explained_variance_[:n80]
            )
            rotator = Rotator(method="varimax")
            rotated = rotator.fit_transform(raw_loadings)
            for pc_idx in range(n80):
                pc_name = f"RC{pc_idx + 1}"
                rotated_dict[pc_name] = {
                    col: round(float(rotated[i, pc_idx]), 4)
                    for i, col in enumerate(columns)
                }
        except Exception:
            pass

    return {
        "n_components_80pct": int(n80),
        "explained_variance": [round(float(v), 4)
                               for v in pca.explained_variance_ratio_[:n_report]],
        "cumulative_variance": [round(float(v), 4) for v in cumvar[:n_report]],
        "loadings": loadings_dict,
        "rotated_loadings": rotated_dict,
    }


# ── Variable selection ───────────────────────────────────────────────────────

def select_variables(
    df: pd.DataFrame,
    columns: list[str],
    threshold: float = 0.70,
) -> list[str]:
    """Select variables by removing redundant pairs (|r| > threshold).

    For each pair exceeding the threshold, drop the variable with lower
    mean absolute correlation with all other variables (standard VIF-like
    elimination).

    Returns list of retained column names.
    """
    if len(columns) <= 2:
        return list(columns)

    corr = df[columns].corr(method="pearson").abs()
    retained = set(columns)

    while True:
        # Find worst pair among retained variables
        worst_r = 0.0
        worst_pair = None
        ret_list = sorted(retained)
        for i, a in enumerate(ret_list):
            for j, b in enumerate(ret_list):
                if j > i and corr.loc[a, b] > worst_r:
                    worst_r = corr.loc[a, b]
                    worst_pair = (a, b)

        if worst_r <= threshold or worst_pair is None:
            break

        a, b = worst_pair
        # Drop the one with lower mean |r| with other retained variables
        others = [c for c in retained if c not in (a, b)]
        if not others:
            # Only two variables left and correlated — keep both
            break
        mean_a = corr.loc[a, others].mean()
        mean_b = corr.loc[b, others].mean()
        drop = b if mean_a >= mean_b else a
        retained.discard(drop)

    # Preserve original ordering
    return [c for c in columns if c in retained]


# ── Geometric mean score ─────────────────────────────────────────────────────

def geometric_mean_score(
    df: pd.DataFrame,
    columns: list[str],
    floor: float = 1.0,
) -> pd.Series:
    """Compute geometric mean of percentile-ranked columns (0-100).

    Applies a floor (default 1.0, HDI-style) to prevent a single zero
    from annihilating the composite. The geometric mean is partially
    compensatory: low values on one dimension drag down the overall score
    more than they would in an arithmetic mean.

    Formula: (prod max(x_i, floor))^(1/n)
    """
    n = len(columns)
    if n == 0:
        return pd.Series(np.nan, index=df.index)
    if n == 1:
        return df[columns[0]].clip(lower=floor)

    log_sum = pd.Series(0.0, index=df.index)
    valid = pd.Series(True, index=df.index, dtype=bool)

    for col in columns:
        vals = df[col].clip(lower=floor)
        is_valid = vals.notna()
        valid &= is_valid
        log_sum[is_valid] += np.log(vals[is_valid])

    result = pd.Series(np.nan, index=df.index)
    result[valid] = np.exp(log_sum[valid] / n)
    return result


# ── Full diagnostic pipeline ─────────────────────────────────────────────────

def run_full_diagnostics(
    df: pd.DataFrame,
    columns: list[str],
    corr_threshold: float = 0.70,
) -> dict:
    """Run all diagnostics: correlation, KMO/Bartlett, PCA, variable selection.

    Returns dict with all diagnostic results plus retained/dropped variable lists.
    """
    diag = {}
    diag["n_variables"] = len(columns)
    diag["n_observations"] = int(df[columns].dropna().shape[0])
    diag["correlation"] = correlation_diagnostics(df, columns, corr_threshold)
    diag["kmo_bartlett"] = kmo_bartlett(df, columns)
    diag["pca"] = pca_diagnostics(df, columns)

    retained = select_variables(df, columns, corr_threshold)
    diag["variable_selection"] = {
        "retained": retained,
        "dropped": [c for c in columns if c not in retained],
        "threshold": corr_threshold,
    }

    return diag


# ── Report generation ────────────────────────────────────────────────────────

def generate_report(
    analysis_id: str,
    diagnostics: dict,
    output_dir: Optional[str] = None,
) -> dict:
    """Generate and optionally save a diagnostic report as JSON.

    Returns the report dict. If output_dir is provided, writes to
    {output_dir}/{analysis_id}_diagnostics.json.
    """
    report = {
        "analysis_id": analysis_id,
        "methodology": "PCA-validated geometric mean (OECD/HDI)",
        "geometric_mean_floor": 1.0,
        **diagnostics,
    }

    if output_dir:
        path = os.path.join(output_dir, f"{analysis_id}_diagnostics.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"  Diagnostics: {path}")

    return report
