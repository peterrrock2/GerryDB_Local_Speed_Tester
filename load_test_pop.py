"""Loads Census PL 94-171 tables P1 through P4 from the Census API."""

import logging
import os
from typing import Optional

import pandas as pd
from gerrydb import GerryDB
from gerrydb_etl import config_logger
from gerrydb_etl.bootstrap.pl_config import (
    AUXILIARY_LEVELS,
    LEVELS,
    MISSING_DATASETS,
    MissingDataset,
)

try:
    from gerrydb_etl.db import DirectTransactionContext
    from gerrydb_meta import crud, models
    from sqlalchemy import select
except ImportError:
    crud = None


import pandas as pd
import warnings
import click

warnings.filterwarnings("ignore")

log = logging.getLogger()

TABLES = ["P1", "P2", "P3", "P4"]
TABLES = ["P1"]
CENTRAL_SPINE_LEVELS = (
    "block",
    # "bg",
    # "tract",
    "county",
    # "state",
)
# Levels auxiliary to central spine.
AUXILIARY_LEVELS = (
    # "vtd",
    # "place",
    # "cousub",
    # "aiannh",  # American Indian/Alaska Native/Native Hawaiian Areas
)
LEVELS = CENTRAL_SPINE_LEVELS + AUXILIARY_LEVELS


def load_tables(
    namespace: str,
    year: str,
    table: str,
    level: str,
    fips: str,
    table_df: pd.DataFrame,
    user_email: Optional[str] = None,
):
    """
    Loads Census PL 94-171 tables P1 through P4 from the Census API.

    https://www.census.gov/content/dam/Census/data/developers/api-user-guide/api-guide.pdf
    https://api.census.gov/data.html

    """
    log.info(f"LOADING CENSUS {year} {level} {table} FOR {fips}")

    if MissingDataset(fips=fips, level=level, year=year) in MISSING_DATASETS:
        log.warning("Dataset not published by Census. Nothing to do.")
        exit()

    if fips is None:
        raise ValueError(f'Level "{level}" requires a state FIPS code.')

    if os.getenv("GERRYDB_BULK_IMPORT") and crud is None:
        raise RuntimeError("gerrydb_meta must be available in bulk import mode.")

    # Some geographies have a '/' in the geoid, which will mess up the path, so we remove it
    # and replace all instances of '/' with '--' in the dataframe
    table_df = table_df.applymap(
        lambda x: x.replace("/", "--") if isinstance(x, str) else x
    )

    if level == "block":
        id_cols = ("state", "county", "tract", "block")
    elif level == "bg":
        id_cols = ("state", "county", "tract", "block group")
    elif level == "tract":
        id_cols = ("state", "county", "tract")
    elif level == "county":
        id_cols = ("state", "county")
    elif level == "state":
        id_cols = ("state",)
    elif level == "vtd":
        id_cols = ("state", "county", "voting district")
    elif level == "place":
        id_cols = ("state", "place")
    elif level == "cousub":
        id_cols = ("state", "county", "county subdivision")
    elif level == "aiannh":
        id_cols = (
            "american indian area/alaska native area/hawaiian home land (or part)",
        )
    else:
        raise ValueError("Unknown level.")

    db = GerryDB(namespace=namespace)

    table_cols = db.column_sets[table.lower()]

    col_aliases = {}
    for col in table_cols.columns:
        for alias in col.aliases:
            col_aliases[alias] = col

    table_df["id"] = table_df[list(id_cols)].agg("".join, axis=1)

    if level in AUXILIARY_LEVELS:
        # since aiannh geographies cross state lines, the census subidivides the polygon but
        # uses the same geoid, we add the fips code to make the geoid unique
        table_df["id"] = (
            f"{level}:" + table_df["id"] + f":fips{fips}"
            if level == "aiannh"
            else f"{level}:" + table_df["id"]
        )

    table_df = table_df.rename(columns={col: col.lower() for col in table_df.columns})
    table_df = table_df.set_index("id")

    table_cols = {
        alias: col for alias, col in col_aliases.items() if alias in table_df.columns
    }
    for col in table_cols:
        table_df[col] = table_df[col].astype(int)

    import_notes = (
        f"ETL script {__file__}: loading data for {year} "
        f"U.S. Census P.L. 94-171 Table {table}"
    )

    with DirectTransactionContext(notes=import_notes, email=user_email) as ctx:
        namespace_obj = crud.namespace.get(db=ctx.db, path=namespace)
        assert namespace_obj is not None

        geographies = crud.geography.get_bulk(
            db=ctx.db,
            namespaced_paths=[(namespace, idx) for idx in table_df.index],
        )
        if len(geographies) < len(table_df):
            raise ValueError(
                f"Cannot perform bulk import (expected {len(table_df)} "
                f"geographies, found {len(geographies)})."
            )

        raw_cols = (
            ctx.db.query(models.DataColumn)
            .filter(
                models.DataColumn.col_id.in_(
                    select(models.ColumnRef.col_id).filter(
                        models.ColumnRef.path.in_(
                            col.path for col in table_cols.values()
                        ),
                        models.ColumnRef.namespace_id == namespace_obj.namespace_id,
                    )
                )
            )
            .all()
        )
        cols_by_canonical_path = {col.canonical_ref.path: col for col in raw_cols}

        cols_by_alias = {
            alias: cols_by_canonical_path[col.canonical_path]
            for alias, col in table_cols.items()
        }
        geos_by_path = {geo.path: geo for geo in geographies}

        ctx.load_column_values(cols=cols_by_alias, geos=geos_by_path, df=table_df)


@click.command()
@click.option("--large", type=int, help="Run on large data set.")
@click.option("--extreme", type=int, help="Run on extreme data set.")
def main(large, extreme):

    # convert int to bool
    large = large == 1
    extreme = extreme == 1

    file = "./WY_data/56_county_2010_P1.parquet"

    if large:
        file = "./WY_data/56_block_2010_P1.parquet"

    if extreme:
        file = "./TX_data/48_block_2010_P1.parquet"

    file_name = os.path.basename(file)
    fips = file_name.split("_")[0]
    level = file_name.split("_")[1]
    year = file_name.split("_")[2]
    table = file_name.split("_")[3].split(".")[0]
    namespace = f"census.{year}"

    print(f"load_tables({namespace}, {year}, {table}, {level}, {fips}, table_df)")
    table_df = pd.read_parquet(file)
    load_tables(
        namespace, year, table, level, fips, table_df, user_email="test@test.com"
    )


if __name__ == "__main__":
    config_logger(log)

    log.removeHandler(log.handlers[0])

    main()
