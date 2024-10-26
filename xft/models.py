import polars as pl
import pymc as pm

from .analysis import (
    prepare_overall_open_games,
    prepare_overall_characteristics,
)
from .misc import get_division_name


def create_open_games_groups(
    boards: pl.DataFrame, divisionIds: list[int] | None = None
) -> dict:
    """Splits the consolidated frame into frames for each year and divison,
    including correct ordering between each Open-Games pair and transformed
    overall rankings in all frames."""

    if divisionIds is not None:
        boards = boards.filter(pl.col("divisionId").is_in(divisionIds))
    groups = dict()
    for key, group in boards.group_by(["year", "divisionId"]):
        opn, gms = prepare_overall_open_games(group)
        if not (opn.is_empty() or gms.is_empty()):
            if not (opn["competitorId"] == gms["competitorId"]).all():
                raise ValueError(
                    f"For {key=}, the competitor ids did not exactly match between Open and Games data frames."
                )
            year, divisionId = key
            label = f"{year} {get_division_name(divisionId)}"
            groups[label] = dict()
            groups[label]["opn"] = opn
            groups[label]["gms"] = gms

    return groups


def merge_rank_columns(groups: dict) -> dict:
    """Merges data frames for the Open and Games, as stored in a dictionary. Renames
    relevant columns with ...Open and ...Games as appropriate."""
    difs = dict()
    for label in groups:
        # Make sure compeititor ids are identical.
        opn = groups[label]["opn"].sort("competitorId")
        gms = groups[label]["gms"].sort("competitorId")
        if not (opn["competitorId"] == gms["competitorId"]).all():
            raise ValueError("Mismatched competitorIds.")
        # Select only the most relevant columns, if desired.
        df = opn[
            [
                "competitorName",
                "competitorId",
                "year",
                "divisionId",
                "age",
                "height",
                "weight",
            ]
        ]
        # Rename the original columns in each data frame before adding them to df.
        for col in [
            "overallRank",
            "overallScore",
            "overallRerank",
            "inverseNormalTransform",
            "normalizedRank",
        ]:
            df = df.with_columns(opn[col].alias(col + "Open"))
            df = df.with_columns(gms[col].alias(col + "Games"))
        # Add differences of ranking columns.
        for col in [
            "overallRank",
            "overallRerank",
            "inverseNormalTransform",
            "normalizedRank",
        ]:
            df = df.with_columns(
                (df[col + "Games"] - df[col + "Open"]).alias(col + "Difference")
            )
        # Finally, add this frame to the final dict.
        difs[label] = df
    return difs


def setup_overall_open_games_regression(
    boards: pl.DataFrame, divisionIds: list[int] | None = None
) -> tuple[list[str], dict[str], pm.Model]:
    """Sets up a hierarchical pymc model for regressions between transformed
    Open rankings and transformed Games rankings, indluding only specified
    division numbers."""

    groups = create_open_games_groups(boards, divisionIds)

    ngroup = len(groups)
    labels = sorted(groups.keys())

    with pm.Model() as model:
        # Hyper-prior for the overall slope/effect.
        # They are strictly bounded between -1 and 1 for transformed rankings.
        _B = pm.Beta("_B", alpha=2, beta=2)
        B = pm.Deterministic("B", _B * 2 - 1)

        # Effects and variability for each group.
        b = pm.Normal("b", mu=B, sigma=0.5, shape=ngroup)
        s = pm.Gamma("s", alpha=2, beta=2, shape=ngroup)
        a = pm.Normal("a", sigma=0.1, shape=ngroup)

        # Group-level likelihoods.
        for i, label in enumerate(labels):
            x = groups[label]["opn"]["inverseNormalTransform"].to_numpy()
            y = groups[label]["gms"]["inverseNormalTransform"].to_numpy()
            pm.Normal(f"{label} obs", mu=b[i] * x + a[i], sigma=s[i], observed=y)

    return labels, groups, model


def create_physical_regression_groups(
    df: pl.DataFrame,
    competitionType: str,
    divisionIds: list[int] | None = None,
    max_rank: int | None = None,
) -> tuple[dict, tuple[pl.DataFrame, pl.DataFrame]]:
    """Splits a data frame into year-division sub frames, taking only
    Games results, and adds appropriate column transformations and
    standardizations."""

    if max_rank is not None:
        df = df.filter(pl.col("overallRank") <= max_rank)
    if divisionIds is not None:
        df = df.filter(pl.col("divisionId").is_in(divisionIds))
    df, means, stds = prepare_overall_characteristics(df, competitionType)
    groups = dict()
    for key, group in df.group_by("year", "divisionId"):
        year, divisionId = key
        label = f"{year} {get_division_name(divisionId)}"
        groups[label] = group
    return groups, (means, stds)


def setup_overall_physical_regression(
    boards: pl.DataFrame,
    competitionType: str,
    divisionIds: list[int] | None = None,
    max_rank: int | None = None,
    years: list[int] | None = None,
) -> pm.Model:
    """Sets up hierarchical a pymc model for regressions of height, weight, and age
    against transformed rankings for all specified divisions and years. The model
    is a correlated effects model."""

    if years is not None:
        boards = boards.filter(pl.col("year").is_in(years))

    # Ignoring the standardization information for now.
    groups, _ = create_physical_regression_groups(
        boards, competitionType, divisionIds, max_rank
    )

    ngroup = len(groups)
    labels = sorted(groups.keys())

    with pm.Model() as model:
        M = pm.Normal("mu", shape=3)
        chol, corr, stds = pm.LKJCholeskyCov(
            "LKJ", eta=2, n=3, sd_dist=pm.HalfNormal.dist(sigma=1.0, size=3)
        )
        pm.Deterministic("corr", corr)
        pm.Deterministic("height-weight correlation", corr[0, 1])
        pm.Deterministic("height-age correlation", corr[0, 2])
        pm.Deterministic("weight-age correlation", corr[1, 2])
        pm.Deterministic("stds", stds)

        # non-centered correlated slopes/effects
        B_ = pm.Normal("B_", shape=(ngroup, 3))
        B = pm.Deterministic("B", M + pm.math.dot(chol, B_.T).T)

        # independent intercepts and standard deviations
        a = pm.Normal("intercept", shape=ngroup)
        sigma = pm.Gamma("sigma", alpha=2, beta=1, shape=ngroup)

        for i, label in enumerate(labels):
            g = groups[label]
            cols = ["standardizedHeight", "standardizedWeight", "standardizedAge"]
            X = g[cols].to_numpy()
            y = g["inverseNormalTransform"].to_numpy()
            b = pm.Deterministic(f"b {label}", B[i, :])
            mu = a[i] + pm.math.dot(X, b)
            pm.Normal(
                f"{label} obs",
                mu=mu,
                sigma=sigma[i],
                observed=y,
            )

    return labels, groups, model
