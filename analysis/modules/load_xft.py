import numpy as np
import pandas as pd
from pandas import DataFrame
from scipy import stats


def load_embeddings(fn: str) -> DataFrame:
    emb = pd.read_json(fn, orient="index")
    emb["embedding"] = emb.embedding.apply(np.array)
    emb.set_index(["year", "competitionType", "workoutNumber"], inplace=True)
    emb.sort_index(inplace=True)
    return emb


def inverse_normal_transform(x):
    r = stats.rankdata(x)
    p = r / (r.max() + 1)
    t = -stats.norm.ppf(p)
    return t


def standardize(x):
    return (x - x.mean()) / x.std()


def load_competition_results(fn: str, maxOverallRank=np.inf) -> DataFrame:
    xft = pd.read_parquet(fn)
    xft.gender = xft.gender.replace({True: "male", False: "female"})
    # xft = xft[xft.workoutValid.fillna(False)]
    xft = xft[
        [
            "year",
            "competitionType",
            "workoutNumber",
            "divisionNumber",
            "divisionName",
            "gender",
            "height",
            "weight",
            "age",
            "workoutRank",
            "overallRank",
        ]
    ]
    xft.dropna(inplace=True)
    xft = xft[xft.overallRank < maxOverallRank]

    # games workouts outside the main divisions are often different workouts/ordering
    xft = xft.query(
        """competitionType == "open" or (competitionType == "games" and divisionNumber <= 2)"""
    ).copy()

    xft.sort_values(
        ["year", "competitionType", "workoutNumber", "divisionNumber", "workoutRank"],
        inplace=True,
    )

    g = xft.groupby(["year", "competitionType", "workoutNumber", "divisionNumber"])
    xft["r"] = g["workoutRank"].transform(inverse_normal_transform)
    xft["o"] = g["overallRank"].transform(inverse_normal_transform)

    g = xft.groupby(["divisionNumber", "gender"])
    xft["h"] = g["height"].transform(standardize)
    xft["w"] = g["weight"].transform(standardize)
    xft["a"] = g["age"].transform(standardize)

    xft = xft.set_index(
        ["year", "competitionType", "workoutNumber", "divisionName"]
    ).sort_index()
    return xft
