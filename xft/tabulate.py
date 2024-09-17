import polars as pl
import numpy as np

from . import clean

ENTRANT_COLS = {
    "competitorName": str,
    "gender": str,
    "age": int,
    "height": str,
    "weight": str,
    "competitorId": int,
    "divisionId": np.int8,
    "status": str,
    "countryOfOriginCode": str,
    "countryOfOriginName": str,
    "regionId": int,
    "regionName": str,
    "affiliateId": int,
    "affiliateName": str,
}


COMPETITION_COLS = {
    "year": np.int16,
    "competitionType": str,
}

CLEANING = {
    "height": clean.clean_height,
    "weight": clean.clean_weight,
    "age": clean.clean_age,
    "gender": clean.clean_gender,
    "workoutRank": clean.clean_rank,
    "workoutScore": clean.clean_score,
    "workoutValid": clean.clean_valid,
    "workoutScaled": clean.clean_scaled,
}

# Final types for all fields, using Polars classes.
SCHEMA = {
    "competitorName": str,
    "gender": pl.Int8,
    "age": pl.Int8,
    "height": pl.Float32,
    "weight": pl.Float32,
    "competitorId": int,
    "divisionId": pl.Int8,
    "status": str,
    "countryOfOriginCode": str,
    "countryOfOriginName": str,
    "regionId": int,
    "regionName": str,
    "affiliateId": int,
    "affiliateName": str,
    "overallRank": int,
    "overallScore": int,
    "workoutNumber": pl.Int8,
    "workoutRank": int,
    "workoutScore": str,
    "workoutValid": bool,
    "workoutScaled": bool,
    "year": pl.Int16,
    "competitionType": str,
}


def parse(value, target_type):
    try:
        value = target_type(value)
    except ValueError:
        if target_type is float:
            return np.nan
        else:
            return None
    return value


def clean_record(record: dict) -> None:
    for key, function in CLEANING.items():
        record[key] = function(record[key])
    return None


def tabulate_leaderboard_row(row: dict) -> pl.DataFrame:
    # The 'entrant' field is a dictionary of important personal information.
    record = {}
    for key, target_type in ENTRANT_COLS.items():
        value = row["entrant"][key]
        if value == "" or value == "None":
            record[key] = None
        else:
            record[key] = parse(value, target_type)

    # Include the overall score information from the top level 'row'.
    record |= {key: parse(row[key], int) for key in ("overallRank", "overallScore")}

    # Now create partially duplicated dicts for each workout's results,
    # which do need to be their own records because events have different
    # numbers of workouts.
    if "scores" in row:
        records = []
        for score in row["scores"]:
            workout = {}
            workout["workoutNumber"] = np.int8(score["ordinal"])
            workout["workoutRank"] = score["rank"]
            workout["workoutScore"] = score["scoreDisplay"]
            workout["workoutValid"] = score["valid"]
            workout["workoutScaled"] = score["scaled"]
            records.append(record | workout)
    else:
        # It's possible for this information to be missing...
        record["workoutNumber"] = None
        record["workoutRank"] = None
        record["workoutScore"] = None
        record["workoutValid"] = None
        workout["workoutScaled"] = None
        records = [record]

    # Apply cleaning functions (in-place) at this point rather than later.
    for i in range(len(records)):
        clean_record(records[i])
    return pl.concat(map(pl.DataFrame, records), how="vertical_relaxed")


def tabulate_leaderboard(board: dict) -> pl.DataFrame:
    # Arrange the leaderboard into a table by concatenating individual rows.
    records = map(tabulate_leaderboard_row, board["leaderboardRows"])
    # Stack all the rows into one frame.
    df = pl.concat(records, how="vertical_relaxed")
    # Include some competition-wide columns as well.
    cols = []
    for key, target_type in COMPETITION_COLS.items():
        value = parse(board["competition"][key], target_type)
        new_col = pl.lit(value).alias(key)
        cols.append(new_col)
    df = df.with_columns(*cols)
    # Make sure column types are consistent with the desired schema
    for col in df.columns:
        df = df.with_columns(pl.col(col).cast(SCHEMA[col]))

    return df


def tabulate_leaderboards(boards: list[dict]) -> pl.DataFrame:
    # Simply stack together the boards for individual pages/sections.
    return pl.concat(map(tabulate_leaderboard, boards), how="vertical_relaxed")


def tabulate_control(control: dict) -> pl.DataFrame:
    setting = {
        "year": control["year"],
        "competitionType": control["slug"],
        "startDate": control["start_date"][:10],
        "endDate": control["end_date"][:10],
    }
    for element in control["controls"]:
        if element["config_name"] == "division":
            dfs = []
            for data in element["data"]:
                records = []
                for workout in data["controls"][0]["data"][1:]:
                    division = {
                        "divisionId": int(data["value"]),
                        "divisionName": data["display"],
                    }
                    record = (
                        setting
                        | division
                        | {
                            "workoutNumber": int(workout["value"]),
                            "workoutName": workout["display"],
                        }
                    )
                    records.append(record)
                dfs.append(pl.from_dicts(records))
            df = pl.concat(dfs, how="vertical_relaxed", rechunk=True)

            # Convert to the right integer types.
            for col in df.columns:
                if col in SCHEMA:
                    df = df.with_columns(pl.col(col).cast(SCHEMA[col]))

            return df

    # The right information is not present.
    return None
