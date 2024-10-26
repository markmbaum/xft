import itertools
import fsspec
from urllib.error import HTTPError
from rich.progress import track
from time import sleep
from dataclasses import dataclass, field
import warnings
import logging
import numpy as np

from . import fetch, tabulate, misc

DEFAULT_SLEEP_TIME = 0.01

DEFAULT_MAX_PAGE = 1_000


def write_parquet(fs, output_path, df) -> None:
    with fs.open(output_path, "wb") as f, warnings.catch_warnings():
        # Polars warns about using a file object instead of a path/string.
        warnings.filterwarnings("ignore", category=UserWarning)
        df.write_parquet(f)
    return None


def fetch_and_sleep(
    competition: str,
    year: int,
    division: int,
    page: int,
    sleep_time: float = DEFAULT_SLEEP_TIME,
    max_tries: int = 10,
    ignore_failures: bool = False,
    logger: logging.Logger | None = None,
) -> dict | None:
    tries = 0
    done = False
    while not done:
        try:
            board = fetch.fetch_leaderboard(competition, year, division, page)
        except HTTPError:
            sleep_time *= 2
            if logger is not None:
                logger.warning(
                    f"Leaderboard request failed for {competition=}, {year=}, {division=}, {page=}. Temporarily increasing sleep time to {sleep_time} seconds."
                )
        else:
            done = True
        tries += 1
        if tries > max_tries:
            if ignore_failures:
                if logger is not None:
                    logger.warning(
                        f"Could not download the target information. Ignoring because {ignore_failures=}."
                    )
                return None
            else:
                raise Exception(
                    f"Failed to request board for {competition=}, {year=}, {division=}, {page=} after {max_tries} attempts."
                )
        sleep(sleep_time)

    return board


def board_has_rows(board: dict) -> bool:
    if "leaderboardRows" in board and len(board["leaderboardRows"]) > 0:
        return True
    return False


def page_exists(competition: str, year: int, division: int, page: int) -> bool:
    board = fetch_and_sleep(
        competition, year, division, page, max_tries=2, ignore_failures=True
    )
    if board is not None and board_has_rows(board):
        return True
    return False


def find_last_page(
    competition: str, year: int, division: int, min_page: int, max_page: int
) -> int:
    if max_page <= min_page:
        raise ValueError(
            f"The maximum page must be greater than the minimum page but got {max_page=} and {min_page=}."
        )

    # Set the initial page numbers for a bisection search.
    page_lo = min_page
    page_mi = (max_page + min_page) // 2
    page_hi = max_page

    # A convenience closure for checking pages
    def check_page(page):
        return page_exists(competition, year, division, page)

    # There should be a valid response for the first page, otherwise there's no data.
    exists_lo = check_page(page_lo)

    if not exists_lo:
        # Returning zero indicates that no pages are valid.
        return 0

    # Set the initial response flags for the middle and high pages.
    exists_mi = check_page(page_mi)
    exists_hi = check_page(page_hi)

    # If the maximum page number is valid, that's the answer.
    if exists_hi:
        return page_hi

    # Simple bisection search.
    while page_hi - page_lo > 2:
        if exists_mi:
            page_lo = page_mi
            exists_lo = check_page(page_lo)
        else:
            page_hi = page_mi
            exists_hi = check_page(page_hi)
        page_mi = (page_hi + page_lo) // 2
        exists_mi = check_page(page_mi)

    if exists_mi:
        return page_mi
    else:
        return page_lo


def check_competition_years(competition: str, years: list[int]) -> None:
    if competition not in ("games", "open"):
        raise ValueError(
            f"The competition argument must be 'games' or 'open', but got '{competition}'."
        )
    if competition == "games" and np.min(years) < 2007:
        raise ValueError(
            f"The first year of the Games was 2007 but got year '{np.min(years)}'."
        )
    if competition == "open" and np.min(years) < 2011:
        raise ValueError(
            f"The first year of the Open was 2011 but got year '{np.min(years)}'."
        )
    return None


def download_boards(
    output_directory: str,
    competition: str,
    years: int | list[int],
    divisions: int | list[int] | None = None,
    *,
    min_page: int = 1,
    max_page: int = DEFAULT_MAX_PAGE,
    force: bool = False,
    ignore_failures: bool = False,
) -> None:
    logger = misc.initialize_logger(
        __name__, filename=f"download_boards_{competition}.log"
    )

    # Make sure these arguments are iterable, if passed as scalars.
    if isinstance(years, int):
        years = [years]
    if isinstance(divisions, int):
        divisions = [divisions]

    # If divisions are not specified, use all of them.
    if divisions is None:
        logger.info(
            "No division numbers were specified. All of them will be downloaded except the Team division."
        )
        divisions = list(range(1, 11)) + list(range(12, 40))

    # Some basic checks.
    check_competition_years(competition, years)
    if np.max(divisions) > 39:
        raise ValueError(
            f"The highest division number is 39 but got {np.max(divisions)}."
        )

    # Make an output path and, if needed, make the directory.
    fs, _ = fsspec.url_to_fs(output_directory)
    output_directory = fs.sep.join([output_directory, "boards", competition])
    fs.makedirs(output_directory, exist_ok=True)

    for year, division in itertools.product(years, divisions):
        logger.info("--------")
        logger.info(f"Starting {competition=}, {year=}, {division=}.")
        # Get the last valid page for this year and division.
        logger.info(
            f"Finding the final page of the leaderboard with a minimum of {min_page} and a cap of {max_page}."
        )
        last_page = find_last_page(competition, year, division, min_page, max_page)
        if last_page == 0:
            logger.info(
                f"There are no pages to download for page numbers in [{min_page},{max_page}]."
            )
        else:
            logger.info(f"The last page with data is number {last_page}.")
            # Download, tabulate, and store the pages as compressed tables.
            output_subdir = fs.sep.join(
                [output_directory, str(year), f"division-{division:02}"]
            )
            fs.makedirs(output_subdir, exist_ok=True)
            down = 0
            fail = 0
            skip = 0
            logger.info(
                f"Downloading {'' if force else 'or skipping '}pages {min_page} to {last_page}."
            )
            for page in track(
                range(min_page, last_page + 1), description="Downloading..."
            ):
                output_path = fs.sep.join([output_subdir, f"{page:06}.parquet"])
                # Only write a file if it's absent or we should overwrite.
                if force or not fs.isfile(output_path):
                    # Download the table as json and parse it into a dictionary
                    board = fetch_and_sleep(
                        competition,
                        year,
                        division,
                        page,
                        ignore_failures=ignore_failures,
                        logger=logger,
                    )
                    if board is not None:
                        # Arrange relevant information into a polars DataFrame
                        table = tabulate.tabulate_leaderboard(board)
                        write_parquet(fs, output_path, table)
                        # Increment the download counter
                        down += 1
                    else:
                        fail += 1
                else:
                    # Increment the skip counter
                    skip += 1
            logger.info(
                f"Downloaded {down} page(s). Skipped {skip} page(s) that were already present. Ignored {fail} page(s) that failed to download."
            )

    return None


@dataclass
class BoardsConfig:
    # The directory where files/pages are written.
    output_directory: str = "boards"
    # The competition type, which is either "games" or "open".
    competition: str = "games"
    # The competition years.
    years: list[int] = field(default_factory=lambda: list(range(2007, 2025)))
    # Division numbers to download.
    divisions: list[int] | None = None
    # The maximum page number to download.
    max_page: int = DEFAULT_MAX_PAGE
    # The minimum page number to download.
    min_page: int = 1
    # Whether to overwrite existing files.
    force: bool = False
    # Whether to ignore failed page downloads or raise an error.
    ignore_failures: bool = False


def download_controls(
    output_directory: str,
    competition: str,
    years: int | list[int],
    *,
    force: bool = False,
):
    logger = misc.initialize_logger(
        __name__, filename=f"download_controls_{competition}.log"
    )

    if isinstance(years, int):
        years = [years]

    check_competition_years(competition, years)
    fs, _ = fsspec.url_to_fs(output_directory)
    output_directory = fs.sep.join([output_directory, "controls", competition])
    fs.makedirs(output_directory, exist_ok=True)

    for year in years:
        output_path = fs.sep.join([output_directory, f"{year}_controls.parquet"])
        if force or not fs.isfile(output_path):
            control = fetch.fetch_controls(competition, year)
            sleep(DEFAULT_SLEEP_TIME)
            table = tabulate.tabulate_control(control)
            if table is not None:
                with fs.open(output_path, "wb") as f, warnings.catch_warnings():
                    # Polars warns about using a file object instead of a path/string.
                    warnings.filterwarnings("ignore", category=UserWarning)
                    table.write_parquet(f)
                    logger.info(f"Controls table written to {output_path}.")
            else:
                logger.info(f"Information not present for {year}.")
        else:
            logger.info(
                f"Skipped {year} because a file already exists at {output_path}."
            )
