import os
from datetime import datetime, timezone
import pickle
from gerrydb import GerryDB
import click

from states_and_territories import states_and_territories


def import_graph(graph_file_name):

    base_name = os.path.basename(graph_file_name)
    fips = base_name.split("_")[0]
    state = states_and_territories[fips].lower()
    level = base_name.split("_")[1]
    year = base_name.split("_")[2].split(".")[0]

    with open(graph_file_name, "rb") as f:
        graph = pickle.load(f)

    db = GerryDB(namespace=f"census.{year}")
    root_loc = db.localities[fips]
    layer = db.geo_layers[level]

    print(f"Importing graph for {base_name}", flush=True)
    with db.context(
        notes=f"Imported using the make_a_graph.py script at {datetime.now(timezone.utc)}. "
        "Graphs were created using the gerrychain.Graph class and rook adjacency."
    ) as ctx:
        pass

        ctx.graphs.create(
            path=f"{state}_{level}_{year}_dual",
            locality=root_loc,
            layer=layer,
            graph=graph,
            description=f"Dual graph for {state} at {level} level in {year} from raw census shapefile",
        )

    print(f"\tFinished!", flush=True)


@click.command()
@click.option("--large", type=int, help="Run on large data set.")
@click.option("--extreme", type=int, help="Run on extreme data set.")
def main(large, extreme):

    # convert int to bool
    large = large == 1
    extreme = extreme == 1

    f = "./WY_data/56_county_2010.pkl"

    if large:
        f = "./WY_data/56_block_2010.pkl"

    if extreme:
        f = "./TX_data/48_block_2010.pkl"

    import_graph(f)

    print("Finished importing graph!", flush=True)


if __name__ == "__main__":
    main()
