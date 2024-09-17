import os
import polars as pl
import numpy as np
from scipy import stats
from humanize import naturalsize


def nan_fraction(df: pl.DataFrame, col: str) -> float:
    return np.isnan(df[col].to_numpy()).sum() / len(df)


def fill_column_nans(df: pl.DataFrame, col: str) -> pl.DataFrame:
    # Create a mapping between competitior IDs and non-nan values in the target col.
    b = ~np.isnan(df[col].to_numpy())
    cid = df["competitorId"].to_numpy()
    val = df[col].to_numpy()
    cid, val = cid[b], val[b]
    cid2val = dict(zip(cid, val))
    # Replace nans in the target column where possible.
    cid, val = df["competitorId"], df[col].to_numpy()
    for i in range(len(val)):
        if np.isnan(val[i]) and cid[i] in cid2val:
            val[i] = cid2val[cid[i]]
    # Replace the column.
    df = df.with_columns(pl.Series(col, val))
    return df


def load_cached_boards(
    data_dir: str,
    file_name: str = "boards.parquet",
    fill_height: bool = True,
    fill_weight: bool = True,
) -> pl.DataFrame:
    """Loads and concatenates consolidated data frames from the given data directory
    and stores the whole frame locally for faster retrieval. Height and weight columns
    are also optionally filled using averages of non-nan values."""

    if os.path.isfile(file_name):
        boards = pl.read_parquet(file_name)
    else:
        boards = pl.concat(
            [
                pl.read_parquet(f"{data_dir}/boards/consolidated/{year}.parquet")
                for year in range(2007, 2025)
            ]
        )
        if fill_height:
            boards = fill_column_nans(boards, "height")
        if fill_weight:
            boards = fill_column_nans(boards, "weight")
        boards.write_parquet(file_name)
    print(f"{naturalsize(boards.estimated_size())} loaded")
    return boards


def overall_results(df: pl.DataFrame) -> pl.DataFrame:
    """Converts a data frame into overall results only, getting rid
    of the workout-level data."""
    df = df.unique(["competitorId", "competitionType", "year", "divisionId"])
    df = df.drop(
        "workoutNumber", "workoutRank", "workoutScore", "workoutValid", "workoutScaled"
    )
    df = df.filter(pl.col("overallRank").is_not_null())
    return df


def split_competition(
    df: pl.DataFrame, year: int | None = None, divisionId: int | None = None
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Splits a data frame into Open and Games results, optionally
    also taking a specific year and/or division."""

    opn = df.filter(pl.col("competitionType") == "open")
    gms = df.filter(pl.col("competitionType") == "games")

    if year is not None:
        opn = opn.filter(pl.col("year") == year)
        gms = gms.filter(pl.col("year") == year)

    if divisionId is not None:
        opn = opn.filter(pl.col("divisionId") == divisionId)
        gms = gms.filter(pl.col("divisionId") == divisionId)

    return opn, gms


def intersect_athletes(
    df1: pl.DataFrame, df2: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Filters data frames such that the athlete ids are matching. Drops
    non-unique athlete ids in the process."""

    # If duplicates are found, ignore all of them.
    df1 = df1.filter(
        df1["competitorId", "competitionType", "year", "divisionId"].is_unique()
    )
    df2 = df2.filter(
        df2["competitorId", "competitionType", "year", "divisionId"].is_unique()
    )
    # Take common individual athlete IDs.
    ids = set(df1["competitorId"]) & set(df2["competitorId"])
    df1 = df1.filter(pl.col("competitorId").is_in(ids)).sort("competitorId")
    df2 = df2.filter(pl.col("competitorId").is_in(ids)).sort("competitorId")
    # Check and return.
    if len(df1) != len(df2):
        raise ValueError("Intersected frames have different numbers of rows.")
    if (df1["competitorId"] != df2["competitorId"]).any():
        raise ValueError("Intersected frames do not have matching competitor IDs.")
    return df1, df2


def inverse_normal_transform(ranks):
    # The sign change puts lowest (best) rankings at the highest transformed values.
    return -stats.norm.ppf(ranks / (len(ranks) + 1))


def with_invnt(df: pl.DataFrame, col: str, rerank: bool = True) -> pl.DataFrame:
    """Adds the inverse normal transformation to a data frame, optionally reranking
    the rankings before transformation"""
    if rerank:
        invnt = inverse_normal_transform(df[col].rank())
    else:
        invnt = inverse_normal_transform(df[col])
    df = df.with_columns(inverseNormalTransform=invnt)
    return df


def with_normalized_rank(
    df: pl.DataFrame, col: str, rerank: bool = True
) -> pl.DataFrame:
    """Adds the normalized rank to a data frame, optionally reranking
    the rankings before normalization."""
    if rerank:
        rank = df[col].rank()
    else:
        rank = df[col]
    norm = (rank - 1) / (len(rank) - 1)
    df = df.with_columns(normalizedRank=norm)
    return df


def prepare_overall_open_games(df: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Takes an entire year's consoldated leaderboard and returns two
    data frames with cooresponding overall rankings for the Open and Games,
    including inverse normal transformation and simple normalization of the
    overall rankings."""
    df = overall_results(df)
    opn, gms = split_competition(df)
    opn, gms = intersect_athletes(opn, gms)
    opn = with_invnt(opn, "overallRank")
    opn = with_normalized_rank(opn, "overallRank")
    opn = opn.with_columns(opn["overallRank"].rank().alias("overallRerank"))
    gms = with_invnt(gms, "overallRank")
    gms = with_normalized_rank(gms, "overallRank")
    gms = gms.with_columns(gms["overallRank"].rank().alias("overallRerank"))
    assert (opn["competitorId"] == gms["competitorId"]).all()
    return opn, gms


def prepare_overall_characteristics(
    df: pl.DataFrame, competitionType: str | None = None
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Prepares a data frame for analysis with height, weight, age, and rankings,
    including standardization of the columns representing athlete physical
    characteristics. Also returns the means and standard deviations for the
    standardization groups."""

    # Optionally filter the competition type.
    if competitionType is not None:
        df = df.filter(df["competitionType"] == competitionType)
    # Get only the overall results, not individual workouts.
    df = overall_results(df)
    # Take only the columns relevant for regressions.
    df = df[
        [
            "competitorName",
            "year",
            "divisionId",
            "gender",
            "height",
            "weight",
            "age",
            "overallRank",
        ]
    ]
    # Remove all rows with a NaN value.
    df = df.filter(
        np.isnan(df[["height", "weight", "age", "overallRank"]]).sum(axis=1) == 0
    )
    # Add the inverse normal transform for each event, separated by divisions of course.
    df = df.group_by("year", "divisionId").map_groups(
        lambda g: g.with_columns(
            inverseNormalTransform=inverse_normal_transform(g["overallRank"].rank()),
        )
    )
    # Compute standards
    gb = df.group_by("divisionId")
    means = gb.agg(pl.col("height", "weight", "age").mean())
    stds = gb.agg(pl.col("height", "weight", "age").std())
    # Standardize
    df = df.group_by("divisionId").map_groups(
        lambda g: g.with_columns(
            standardizedHeight=(pl.col("height") - pl.col("height").mean())
            / pl.col("height").std(),
            standardizedWeight=(pl.col("weight") - pl.col("weight").mean())
            / pl.col("weight").std(),
            standardizedAge=(pl.col("age") - pl.col("age").mean())
            / pl.col("age").std(),
        )
    )
    df = df.sort("year", "divisionId", "overallRank")
    return df, means, stds
