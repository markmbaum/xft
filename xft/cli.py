import fsspec
import polars as pl
import typer
from omegaconf import OmegaConf
from rich import print as rprint
from rich.table import Table
import humanize

from typing import Annotated

from . import misc
from .download import BoardsConfig, download_boards, download_controls, write_parquet
from .consolidate import ConsolidationConfig, consolidate_boards


app = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

app_download = typer.Typer(no_args_is_help=True, pretty_exceptions_enable=False)

app.add_typer(
    app_download,
    name="download",
    help="Subapplication for downloading leaderboards and controls.",
)


@app_download.command(no_args_is_help=True)
def boards(
    config_path: Annotated[
        str | None,
        typer.Argument(help="Path to a download configuration yaml file."),
    ],
):
    """Downloads leaderboard pages into parquet files using parameters
    specified in a config (yaml) file or. See xft.downloads.BoardsConfig
    for the relevant parameters."""

    # Read in the configuration parameters if a config file is given.
    conf = OmegaConf.load(config_path)
    structured_conf = OmegaConf.structured(BoardsConfig)
    conf = OmegaConf.merge(structured_conf, conf)
    conf = OmegaConf.to_object(conf)

    rprint("Starting leaderboard downloads with the following parameters:")
    for k, v in vars(conf).items():
        rprint(f"  {k}: {v}")

    # Download in compressed chunks (a parquet file for each page)
    download_boards(
        output_directory=conf.output_directory,
        competition=conf.competition,
        years=conf.years,
        divisions=conf.divisions,
        min_page=conf.min_page,
        max_page=conf.max_page,
        force=conf.force,
        ignore_failures=conf.ignore_failures,
    )


@app_download.command(no_args_is_help=True)
def controls(
    output_directory: str, competition: str, years: list[int], force: bool = False
):
    """Downloads a control table to storage/disk."""
    download_controls(
        output_directory=output_directory,
        competition=competition,
        years=years,
        force=force,
    )


@app.command(no_args_is_help=True)
def consolidate(
    config_path: Annotated[
        str | None,
        typer.Argument(help="Path to a consolidation configuration yaml file."),
    ],
):
    """Consolidates leaderboard files into a single parquet file on storage.
    See the ConsolidationConfig dataclass for the parameters/arguments. Note
    that Games and Open results are automatically combined into files for
    each consolidated year."""

    conf = OmegaConf.load(config_path)
    structured_conf = OmegaConf.structured(ConsolidationConfig)
    conf = OmegaConf.merge(structured_conf, conf)
    conf = OmegaConf.to_object(conf)
    rprint(conf)

    if conf.divisions is None:
        conf.divisions = list(range(1, 11)) + list(range(12, 40))
        rprint(f"Using all individual divisions: {conf.divisions}")

    fs, url = fsspec.url_to_fs(conf.data_dir)
    output_dir = fs.sep.join([url, "boards", "consolidated"])
    fs.mkdirs(output_dir, exist_ok=True)

    for year in conf.years:
        output_path = fs.sep.join([url, "boards", "consolidated", f"{year}.parquet"])
        if conf.force or not fs.isfile(output_path):
            rprint(f"starting {year}")
            dfs = []
            for competition in ["games", "open"]:
                for division in conf.divisions:
                    df = consolidate_boards(conf.data_dir, competition, year, division)
                    if df is not None:
                        dfs.append(df)
            df = pl.concat(dfs, how="vertical")
            rprint(
                f"{year} table consolidated ({humanize.naturalsize(df.estimated_size())})"
            )
            write_parquet(fs, output_path, df)
            rprint(f"file written: {output_path}")
        else:
            rprint(f"file already existed and force={conf.force}: {output_path}")


@app.command()
def divisions():
    """Prints the division numbers with their names in a table. Takes no arguments."""
    table = Table(title="Competition Divisions")
    table.add_column("Division Number")
    table.add_column("Division Name")
    for number, name in misc.DIVISIONS.items():
        table.add_row(str(number), name)
    rprint(table)


@app.command(no_args_is_help=True)
def workout(
    competition: Annotated[
        str, typer.Argument(help="The competition type ('games' or 'open').")
    ],
    year: Annotated[int, typer.Argument(help="The year the workout took place.")],
    number: Annotated[int, typer.Argument(help="The workout number.")],
):
    """Prints the description/specification of a workout.
    Note that the workout descriptions apply to the main Men's and Women's divisions
    and may not apply to other divisions."""

    description = misc.get_workout_description(competition, year, number)
    if description is None:
        return None
    rprint(f"{competition.title()} {year}\nWorkout #{number}\n")
    for line in description.splitlines():
        rprint(f"  {line}")
    return None
