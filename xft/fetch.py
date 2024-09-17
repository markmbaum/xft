from urllib.parse import urlunsplit, urlencode
from urllib.request import urlopen
import json


def make_leaderboard_url(competition: str, year: int, division: int, page: int) -> str:
    scheme = "https"
    host = "c3po.crossfit.com"
    # The API path changes for 2024 games, for unknown reasons, and the query does too.
    if competition == "games" and year == 2024:
        path = "api/leaderboards/v2/competitions/finals/2024/leaderboards"
        if division <= 2:
            final = 225
        elif 3 <= division <= 13:
            final = 242
        else:
            final = 241
        query = urlencode({"final": final, "page": page, "division": division})
    else:
        path = f"api/competitions/v2/competitions/{competition}/{year}/leaderboards"
        query = urlencode({"page": page, "division": division})
    components = (scheme, host, path, query, "")
    return urlunsplit(components)


def make_controls_url(competition: str, year: int) -> str:
    scheme = "https"
    host = "games.crossfit.com"
    path = f"competitions/api/v1/competitions/{competition}/{year}"
    query = urlencode({"expand[]": "controls"})
    components = (scheme, host, path, query, "")
    return urlunsplit(components)


def fetch(url) -> str:
    with urlopen(url) as response:
        contents = response.read().decode("utf-8")
    contents = json.loads(contents)
    return contents


def fetch_leaderboard(competition: str, year: int, division: int, page: int) -> str:
    return fetch(make_leaderboard_url(competition, year, division, page))


def fetch_controls(competition: str, year: int) -> str:
    return fetch(make_controls_url(competition, year))
