import logging
import pathlib
from rich import print

DIVISIONS = {
    1: "Men",
    2: "Women",
    3: "Men (45-49)",
    4: "Women (45-49)",
    5: "Men (50-54)",
    6: "Women (50-54)",
    7: "Men (55-59)",
    8: "Women (55-59)",
    9: "Men (60+)",
    10: "Women (60+)",
    11: "Team",
    12: "Men (40-44)",
    13: "Women (40-44)",
    14: "Boys (14-15)",
    15: "Girls (14-15)",
    16: "Boys (16-17)",
    17: "Girls (16-17)",
    18: "Men (35-39)",
    19: "Women (35-39)",
    20: "Men Upper Extremity",
    21: "Women Upper Extremity",
    22: "Men Lower Extremity",
    23: "Women Lower Extremity",
    24: "Men Multi-Extremity",
    25: "Women Multi-Extremity",
    26: "Men Vision",
    27: "Women Vision",
    28: "Men Short Stature",
    29: "Women Short Stature",
    30: "Men Seated (w/ hip)",
    31: "Women Seated (w/ hip)",
    32: "Men Seated (w/o hip)",
    33: "Women Seated (w/o hip)",
    34: "Men Intellectual",
    35: "Women Intellectual",
    36: "Men (60-64)",
    37: "Women (60-64)",
    38: "Men (65+)",
    39: "Women (65+)",
}


def get_division_name(division: int):
    try:
        name = str(DIVISIONS[division])
    except KeyError:
        raise ValueError(
            f"Division numbers can be between 1 and 39 but got {division}."
        )
    return name


def get_root_dir():
    return pathlib.Path(__file__).parent.parent


def get_workout_description(competition: str, year: int, number: int) -> str | None:
    path = (
        get_root_dir()
        / "workouts"
        / competition
        / str(year)
        / f"{competition}_{year}_individual_workout_{number}.txt"
    )
    if not path.is_file():
        print(
            f"""No workout description was found for {competition=}, {year=}, {number=}. The text description should be at this path: {path}."""
        )
        return None
    with path.open("r") as f:
        description = f.read()
    return description


def initialize_logger(
    name: str, level: int = logging.INFO, *, filename: str | None = None
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    if filename is not None:
        logdir = get_root_dir() / "logs"
        logdir.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(logdir / filename)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
