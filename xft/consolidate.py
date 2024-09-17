import fsspec
from concurrent.futures import ThreadPoolExecutor
import polars as pl
import warnings
import itertools
from dataclasses import dataclass
import humanize
from rich import print as rprint


def read_parquet(fs, url) -> pl.DataFrame:
    with fs.open(url, "rb") as f, warnings.catch_warnings():
        # Polars warns about using a file object instead of a path/string.
        warnings.filterwarnings("ignore", category=UserWarning)
        df = pl.read_parquet(f)
    return df


def read_parquets(fs, urls) -> list[pl.DataFrame]:
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(read_parquet, fs, url) for url in urls]
    dfs = [future.result() for future in futures]
    return dfs


def consolidate_boards(
    data_dir: str, competition: str, year: int, division: int
) -> pl.DataFrame | None:
    """Consolidates leaderboard files/chunks for a specific competition, year,
    and division."""
    fs, url = fsspec.url_to_fs(data_dir)
    urls = fs.glob(
        fs.sep.join(
            [url, "boards", competition, str(year), f"division-{division:02}/*.parquet"]
        )
    )
    # If there are no boards to read, return None instead of error.
    if len(urls) == 0:
        return None
    # Otherwise read the boards in parallel and concatenate then in to a single DataFrame.
    return pl.concat(read_parquets(fs, urls), rechunk=True, how="vertical")


def consolidate_year(
    data_dir: str, year: int, divisions: list[int]
) -> pl.DataFrame | None:
    """Consolidates leaderboard files/chunks for an entire year's results,
    including all divisions and both the Open and Games."""

    fs, url = fsspec.url_to_fs(data_dir)
    urls = []
    prod = itertools.product(["games", "open"], divisions)
    for competition, division in prod:
        components = [
            url,
            "boards",
            competition,
            str(year),
            f"division-{division:02}/*.parquet",
        ]
        urls += list(fs.glob(fs.sep.join(components)))
    # If there are no boards to read, return None instead of error.
    if len(urls) == 0:
        return None
    return pl.concat(read_parquets(fs, urls), rechunk=True, how="vertical")


@dataclass
class ConsolidationConfig:
    data_dir: str
    years: list[int]
    divisions: list[int] | None = None
    force: bool = False


def read_control(fs, url) -> pl.DataFrame:
    with fs.open(url, "rb") as f, warnings.catch_warnings():
        # Polars warns about using a file object instead of a path/string.
        warnings.filterwarnings("ignore", category=UserWarning)
        df = pl.read_csv(f)
    return df


def load_consolidated(data_dir: str) -> pl.DataFrame:
    """Loads consolidated data frames from the root of an xft file system (data_dir)."""
    fs, url = fsspec.url_to_fs(data_dir)
    urls = fs.glob(fs.sep.join([url, "boards", "consolidated", "*.parquet"]))
    if len(urls) == 0:
        raise FileNotFoundError("There are no consolidated boards files.")
    dfs = []
    for url in urls:
        df = read_parquet(fs, url)
        rprint(f"Loaded about {humanize.naturalsize(df.estimated_size())} from {url}.")
        dfs.append(df)

    df = pl.concat(dfs, how="vertical", rechunk=True)
    rprint(
        f"Total size of concatenated data frame is {humanize.naturalsize(df.estimated_size())}."
    )
    return df


def consolidate_controls(data_dir: str) -> pl.DataFrame | None:
    """Consolidates all contols files into a single DataFrame."""
    fs, url = fsspec.url_to_fs(data_dir)
    urls = fs.glob(fs.sep.join([url, "controls", "**/*.parquet"]))
    rprint(f"Found {len(urls)} consolidated tables.")
    if len(urls) == 0:
        return None
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(read_parquet, fs, url) for url in urls]
    dfs = [future.result() for future in futures]
    return pl.concat(dfs, rechunk=True, how="vertical_relaxed")
