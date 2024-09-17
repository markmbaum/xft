import numpy as np

NAN = np.float32(np.nan)


def clean_height(height: str) -> np.float32:
    if height is None or height == "":
        return NAN

    if "cm" in height:
        height = np.float32(height.replace("cm", "")) / 1e2
    elif "in" in height:
        height = np.float32(height.replace("in", "")) / 3.93e1
    else:
        raise ValueError(f"Not sure how to handle cleaning of height value '{height}'.")

    # These values are physically implausible, probably from data entry error.
    if (height < 1.2) or (height > 2.13):
        return NAN

    return height


def clean_weight(weight: str) -> np.float32:
    if weight is None or weight == "":
        return NAN

    if "lb" in weight:
        weight = np.float32(weight.replace("lb", "")) * 0.454
    elif "kg" in weight:
        weight = np.float32(weight.replace("kg", ""))
    else:
        raise ValueError(f"Not sure how to handle cleaning of weight value '{weight}'.")

    # These values are physically implausible.
    if (weight < 35) or (weight > 150):
        return NAN

    return weight


def clean_age(age: int) -> np.int8:
    if age is None:
        return None

    # There are no divisions for under 14 year olds.
    if (age < 14) or (age > 100):
        return None

    return np.int8(age)


def clean_rank(rank: str) -> int:
    try:
        rank = int(rank)
    except (ValueError, TypeError):
        pass
    else:
        return rank


def clean_gender(gender: str) -> np.int8 | None:
    if gender == "M":
        return np.int8(1)
    elif gender == "F":
        return np.int8(0)
    else:
        return None


def clean_score(score: str) -> str:
    if score is None or score == "":
        return None
    return score


def clean_valid(valid: str) -> bool:
    if valid == "" or valid is None:
        return False

    return bool(int(valid))


def clean_scaled(scaled: str) -> bool:
    if scaled == "" or scaled is None:
        return None

    return bool(int(scaled))
