"""
Shared definitions for Parts 4 and 5 (BFT65B): sample split and the
preprocessing pipeline. Imported by 06_features.py and 07_model.py so that
both parts use exactly the same split and the same preprocessing.

Every preprocessing step LEARNS its parameters in .fit(), which is called on
the development (training) period only; the test period is only .transform()-ed.
"""

from datetime import date

import numpy as np
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# ------------------------------------------------------------------ split
DEV_START, DEV_END = date(1984, 3, 31), date(2006, 12, 31)     # development (train + validation)
GAP_START, GAP_END = date(2007, 3, 31), date(2007, 12, 31)     # 4-quarter gap, not used
TEST_START, TEST_END = date(2008, 3, 31), date(2025, 6, 30)    # test, used once
# A dev row at 2006Q4 looks for failures up to 2007Q4, so no dev label overlaps the test period.

# ------------------------------------------------------------------ features
FEATURES = [
    # C - capital
    "F_EQ_TA", "F_LEV_RATIO", "F_EQ_TA_CHG_4Q", "F_EQ_TA_PCTRANK",
    # A - asset quality
    "F_NPL", "F_RES_LN", "F_PROV_LN", "F_NCO_LN", "F_ORE_TA", "F_NPL_CHG_1Q", "F_NPL_PCTRANK",
    # M - management (proxy: aggressive balance-sheet growth)
    "F_TA_GROWTH_4Q",
    # E - earnings
    "F_ROA_Q", "F_NIM_Q", "F_ROA_4Q_AVG", "F_ROA_VS_MEDIAN",
    # L - liquidity and funding
    "F_LIQ", "F_BRO_DEP", "F_LN_DEP",
    # size
    "F_LOG_TA",
]


class Winsorizer(BaseEstimator, TransformerMixin):
    """Clip each feature to its [lower, upper] quantiles LEARNED IN fit()."""

    def __init__(self, lower=0.01, upper=0.99):
        self.lower = lower
        self.upper = upper

    def fit(self, X, y=None):
        X = np.asarray(X, dtype="float64")
        self.low_ = np.nanquantile(X, self.lower, axis=0)
        self.high_ = np.nanquantile(X, self.upper, axis=0)
        self.n_features_in_ = X.shape[1]
        return self

    def transform(self, X):
        X = np.asarray(X, dtype="float64")
        return np.clip(X, self.low_, self.high_)  # NaN stays NaN (imputed in the next step)

    def get_feature_names_out(self, input_features=None):
        return np.asarray(input_features if input_features is not None
                          else [f"x{i}" for i in range(self.n_features_in_)], dtype=object)


def build_preprocessor():
    """winsorise (train quantiles) -> impute median (train) + missing flags -> standardise (train)."""
    return Pipeline([
        ("winsorize", Winsorizer(0.01, 0.99)),
        ("impute", SimpleImputer(strategy="median", add_indicator=True)),
        ("scale", StandardScaler()),
    ])