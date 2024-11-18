"""Imports base Census geographies."""

import logging
import os
from datetime import datetime, timezone
import geopandas as gpd
import shapely.wkb
import yaml
from gerrydb import GerryDB
from gerrydb_etl import TabularConfig, config_logger
from gerrydb_etl.bootstrap.pl_config import (
    AUXILIARY_LEVELS,
    LEVELS,
    MISSING_DATASETS,
    MissingDataset,
)
from jinja2 import Template
from shapely import Point
import geopandas as gpd
import click

try:
    from gerrydb_meta import crud
except ImportError:
    crud = None


log = logging.getLogger()


COLUMN_CONFIG_PATH = "./pl_geo.yaml"


if COLUMN_CONFIG_PATH is None:
    raise RuntimeError(
        "COLUMN_CONFIG_PATH environment variable must be set."
        " This is generally stored in the gerrydb-etl/gerrydb_etl/bootstrap/columns/pl_geo.yaml"
    )


LAYER_URLS = {
    "block/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/TABBLOCK/2010/tl_2020_{fips}_tabblock10.zip",
    "block/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/TABBLOCK/2020/tl_2020_{fips}_tabblock20.zip",
    "bg/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/BG/2010/tl_2020_{fips}_bg10.zip",
    "bg/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/BG/2020/tl_2020_{fips}_bg20.zip",
    "tract/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/TRACT/2010/tl_2020_{fips}_tract10.zip",
    "tract/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/TRACT/2020/tl_2020_{fips}_tract20.zip",
    "county/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/COUNTY/2010/tl_2020_{fips}_county10.zip",
    "county/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/COUNTY/2020/tl_2020_{fips}_county20.zip",
    "state/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/STATE/2010/tl_2020_{fips}_state10.zip",
    "state/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/STATE/2020/tl_2020_{fips}_state20.zip",
    "vtd/2010": "https://www2.census.gov/geo/tiger/TIGER2012/VTD/tl_2012_{fips}_vtd10.zip",
    "vtd/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/VTD/2020/tl_2020_{fips}_vtd20.zip",
    "place/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/PLACE/2010/tl_2020_{fips}_place10.zip",
    "place/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/PLACE/2020/tl_2020_{fips}_place20.zip",
    "cousub/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/COUSUB/2010/tl_2020_{fips}_cousub10.zip",
    "cousub/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/COUSUB/2020/tl_2020_{fips}_cousub20.zip",
    "aiannh/2010": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/AIANNH/2010/tl_2020_{fips}_aiannh10.zip",
    "aiannh/2020": "https://www2.census.gov/geo/tiger/TIGER2020PL/LAYER/AIANNH/2020/tl_2020_{fips}_aiannh20.zip",
}


def load_geo(
    fips: str,
    level: str,
    year: str,
    namespace: str,
    layer_gdf: gpd.GeoDataFrame,
    layer_hash: str,
):
    """Imports base Census geographies.

    Preconditions:
        * A `Locality` aliased to `fips` exists.
        * `namespace` exists.
        * A `GeoLayer` with path `<level>/<year>` exists in the namespace.
    """
    log.info(f"LOADING GEO FOR {fips} {level} {year}")

    # Some geographies have a '/' in the geoid, which will mess up the path, so we remove it
    # and replace all instances of '/' with '--' in the dataframe
    try:
        layer_gdf = layer_gdf.applymap(
            lambda x: x.replace("/", "--") if isinstance(x, str) else x
        )
    except Exception as e:
        if "Unable to avoid copy" in str(e):
            log.error("Bad version of Numpy installed. Downgrade to 1.26.4")
        raise RuntimeError

    if MissingDataset(fips=fips, level=level, year=year) in MISSING_DATASETS:
        log.warning("Dataset not published by Census. Nothing to do.")
        exit()

    if os.getenv("GERRYDB_BULK_IMPORT") and crud is None:
        raise RuntimeError("gerrydb_meta must be available in bulk import mode.")

    db = GerryDB(namespace=namespace)
    root_loc = db.localities[fips]
    layer = db.geo_layers[level]

    with open(COLUMN_CONFIG_PATH) as config_fp:
        config_template = Template(config_fp.read())
    rendered_config = config_template.render(yr=year[2:], year=year)
    config = TabularConfig(**yaml.safe_load(rendered_config))

    layer_url = LAYER_URLS[f"{level}/{year}"].format(fips=fips)
    index_col = "GEOID" + year[2:]
    county_col = "COUNTYFP" + year[2:]

    # Some Census shapefiles have completely duplicate rows (e.g. CA in 2010)
    # so we drop any duplicates here to avoid path collisions in the DB.
    # Note: The `drop_duplicates` method only drops the row if all columns are the same.
    # log.info("Dropping duplicates from layer_gdf")
    n_rows = len(layer_gdf)
    layer_gdf = layer_gdf.drop_duplicates()
    if len(layer_gdf) < n_rows:
        log.info(f"\tDropped {n_rows - len(layer_gdf)} duplicate rows")

    geos_by_county = (
        dict(layer_gdf.groupby(county_col)[index_col].apply(list))
        if county_col in layer_gdf.columns
        else {}
    )

    if level in AUXILIARY_LEVELS:
        # since aiannh geographies cross state lines, the census subidivides the polygon but
        # uses the same geoid, we add the fips code to make the geoid unique

        # remove the r,t that stands for reservation, trust which only appears
        # at geo level, but not in pop data
        if level == "aiannh":

            def categorize_trust_res(x):
                if x[-1].lower() == "t":
                    return "trust"
                elif x[-1].lower() == "r":
                    return "reservation"
                else:
                    raise ValueError(f"Not a trust or reservation at geoid {x}")

            layer_gdf["res_trust_class"] = layer_gdf[index_col].apply(
                lambda x: categorize_trust_res(x)
            )
            layer_gdf[index_col] = layer_gdf[index_col].apply(
                lambda x: f"{level}:" + x.rstrip("rtRT") + f":fips{fips}"
            )
            yr = year[2:]

            # if there was a geoid with both an R and T tag
            if len(layer_gdf[index_col]) != len(set(layer_gdf[index_col])):
                new_rows = {}

                for row, data in layer_gdf.iterrows():
                    if data[index_col] not in new_rows:
                        new_rows[data[index_col]] = data
                        new_rows[data[index_col]]["collision_count"] = 0

                    # if geoid already exists, indicates R/T collision
                    else:
                        new_rows[data[index_col]]["collision_count"] += 1
                        if new_rows[data[index_col]]["collision_count"] > 1:
                            raise ValueError(
                                f"There has been a collision of 3 geoids {data[index_col]}"
                            )

                        # add land and water, change res/trust class, union geometry
                        new_rows[data[index_col]][f"ALAND{yr}"] += data[f"ALAND{yr}"]
                        new_rows[data[index_col]][f"AWATER{yr}"] += data[f"AWATER{yr}"]
                        new_rows[data[index_col]]["res_trust_class"] = "union"
                        new_rows[data[index_col]]["geometry"] = shapely.unary_union(
                            [new_rows[data[index_col]]["geometry"], data["geometry"]]
                        )

                        if new_rows[data[index_col]][f"NAME{yr}"] != data[f"NAME{yr}"]:
                            if data[index_col] in [
                                "aiannh:1075:fips32",
                                "aiannh:1070:fips32",
                            ]:
                                # the Fallon Paiute-Shoshone name has an extra (Reservation/Colony) appended
                                pass
                            else:
                                print("geoid", (data[index_col]))
                                print("name 1", new_rows[data[index_col]][f"NAME{yr}"])
                                print("name 2", data[f"NAME{yr}"])
                                raise ValueError(
                                    f"NAME{yr} does not match across R and T land in geoid {data[index_col]}"
                                )

                layer_gdf = gpd.GeoDataFrame.from_dict(
                    new_rows, orient="index"
                ).set_crs(layer_gdf.crs)
            layer_gdf = layer_gdf[
                [
                    f"NAME{yr}",
                    index_col,
                    "geometry",
                    f"INTPTLAT{yr}",
                    f"INTPTLON{yr}",
                    "res_trust_class",
                ]
            ]

        else:
            layer_gdf[index_col] = f"{level}:" + layer_gdf[index_col]
        geos_by_county = {
            county: [f"{level}:{unit}" for unit in units]
            for county, units in geos_by_county.items()
        }

    layer_gdf = layer_gdf.set_index(index_col)

    columns = {
        col.source: db.columns[col.target]
        for col in config.columns
        if col.source in layer_gdf.columns
    }

    internal_latitudes = layer_gdf[f"INTPTLAT{year[2:]}"].apply(float)
    internal_longitudes = layer_gdf[f"INTPTLON{year[2:]}"].apply(float)
    layer_gdf["internal_point"] = [
        Point(long, lat) for long, lat in zip(internal_longitudes, internal_latitudes)
    ]

    import_notes = (
        f"Loaded by ETL script pl_geo.py from {year} U.S. Census {level} "
        f"shapefile {layer_url} (SHA256: {layer_hash})"
    )

    with db.context(notes=import_notes) as ctx:

        ctx.load_dataframe(
            df=layer_gdf,
            columns=columns,
            create_geo=True,
            locality=root_loc,
            layer=layer,
        )

        for county_fips, county_geos in geos_by_county.items():
            full_fips = fips + county_fips
            ctx.geo_layers.map_locality(
                layer=layer, locality=full_fips, geographies=county_geos
            )


@click.command()
@click.option("--large", type=int, help="Run on large data set.")
@click.option("--extreme", type=int, help="Run on extreme data set.")
def main(large, extreme):

    # convert int to bool
    large = large == 1
    extreme = extreme == 1

    file = "./WY_data/56_county_2010--707029ed009370e99b66c9f83300bdb6f2fe936f97be8bcb6de127a06a123d1b.parquet"

    if large:
        file = "./WY_data/56_block_2010--ef36f7336669e0ef5a758b8fba0441ac1dfb8cfc531ad4ee14731480039c708b.parquet"

    if extreme:
        file = "./TX_data/48_block_2010--167bc0750535ffae8f14dd3e58d921a8439fcedd86b5fe576cbe82d7eb8f8d80.parquet"

    file_name = os.path.basename(file)
    fips = file_name.split("_")[0]
    level = file_name.split("_")[1]
    year = file_name.split("_")[2].split("--")[0]
    layer_hash = file_name.split("--")[1].split(".")[0]
    namespace = f"census.{year}"

    print("\t", fips, level, year, layer_hash)
    layer_gdf = gpd.read_parquet(file)

    try:
        load_geo(fips, level, year, namespace, layer_gdf, layer_hash)

    except Exception as e:
        log.error(f"ERROR loading {fips} {level} {year}\n{e}")


if __name__ == "__main__":
    config_logger(log)

    log.removeHandler(log.handlers[0])

    main()
