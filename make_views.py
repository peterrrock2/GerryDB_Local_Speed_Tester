import gerrydb
from gerrydb import GerryDB
import time
from tqdm import tqdm
import click


@click.command()
@click.option("--large", type=int, help="Run on large data set.")
@click.option("--extreme", type=int, help="Run on extreme data set.")
def main(large, extreme):

    # convert int to bool
    large = large == 1
    extreme = extreme == 1

    base_namespace = "census.2010"

    with GerryDB(namespace=base_namespace) as db:
        if not extreme:
            locality = db.localities["wy"]
        else:
            locality = db.localities["tx"]

        if large or extreme:
            layer = db.geo_layers["block"]
        else:
            layer = db.geo_layers["county"]

        print("Getting graph...")
        t_start_get_graph = time.time()

        if extreme:
            graph = db.graphs["tx_block_2010_dual"]
        elif large:
            graph = db.graphs["wy_block_2010_dual"]
        else:
            graph = db.graphs["wy_county_2010_dual"]

        t_end_get_graph = time.time()
        print(f"Time to get graph: {t_end_get_graph - t_start_get_graph}")

        with db.context(notes="Creating views for census.2010") as ctx:
            columns1 = ["total_pop"]

            # Time render view from single column
            template1 = ctx.view_templates.create(
                path="test_single_column_view_template",
                columns=columns1,
                namespace=base_namespace,
                description="View containing a single column.",
            )

            print("Timing single column view creation...")
            t_start_single_column = time.time()
            ctx.views.create(
                path=f"test_single_column_view",
                namespace=base_namespace,
                template=template1,
                locality=locality,
                graph=graph,
                layer=layer,
            )
            t_end_single_column = time.time()
            print(
                f"Time to create first instance of column view: {(t_end_single_column - t_start_single_column)} s"
            )
            n_single_column_attempts = 3
            t_start_single_column = time.time()
            for i in tqdm(range(n_single_column_attempts)):
                ctx.views.create(
                    path=f"test_single_column_view_{i}",
                    namespace=base_namespace,
                    template=template1,
                    locality=locality,
                    graph=graph,
                    layer=layer,
                )
            t_end_single_column = time.time()
            print(
                f"Average time to create single column view after first attempt: {(t_end_single_column - t_start_single_column) / n_single_column_attempts} s"
            )

            # Time render medium view from medium column set
            column_set_columns2 = [
                "name",
                "one_race_pop",
                "two_or_more_races_pop",
                "area_land",
                "area_water",
                "nhpi_pop",
                "other_pop",
                "amin_pop",
                "asian_pop",
                "white_pop",
                "black_pop",
                "black_nhpi_pop",
                "black_other_pop",
                "black_amin_pop",
                "black_asian_pop",
                "white_nhpi_pop",
                "white_other_pop",
                "white_amin_pop",
                "white_asian_pop",
                "two_races_pop",
                "white_black_pop",
                "white_black_nhpi_pop",
                "white_black_amin_pop",
                "white_black_asian_pop",
                "nhpi_other_pop",
            ]

            ctx.column_sets.create(
                path="test_medium_column_set",
                columns=column_set_columns2,
                namespace=base_namespace,
                description="Small column set for testing.",
            )

            columns2 = [
                "total_pop",
            ]

            template2 = ctx.view_templates.create(
                path="test_medium_column_set_view_template",
                column_sets=["test_medium_column_set"],
                columns=columns2,
                description="View containing a few columns",
            )

            t_start_medium_view = time.time()
            ctx.views.create(
                path=f"test_medium_column_set_view",
                namespace=base_namespace,
                template=template2,
                locality=locality,
                graph=graph,
                layer=layer,
            )
            t_end_medium_view = time.time()

            print(
                f"Time to create first instance of medium view: {(t_end_medium_view - t_start_medium_view)} s"
            )
            n_medium_view_attempts = 3
            t_start_medium_view = time.time()
            for i in tqdm(range(n_medium_view_attempts)):
                ctx.views.create(
                    path=f"test_medium_column_set_view_{i}",
                    namespace=base_namespace,
                    template=template2,
                    locality=locality,
                    graph=graph,
                    layer=layer,
                )
            t_end_medium_view = time.time()

            print(
                f"Average time to create medium view after first attempt: {(t_end_medium_view - t_start_medium_view) / n_medium_view_attempts} s"
            )

            # Time render large view from large column set
            template3 = ctx.view_templates.create(
                path="test_large_column_set_view_template",
                column_sets=["p1"],
                namespace=base_namespace,
                description="View containing a large column set.",
            )

            t_start_large_view = time.time()
            ctx.views.create(
                path=f"test_large_column_set_view",
                namespace=base_namespace,
                template=template3,
                locality=locality,
                graph=graph,
                layer=layer,
            )
            t_end_large_view = time.time()

            print(
                f"Time to create first instance of large view: {(t_end_large_view - t_start_large_view)} s"
            )

            n_large_view_attempts = 3
            t_start_large_view = time.time()
            for l in tqdm(range(n_large_view_attempts)):
                ctx.views.create(
                    path=f"test_large_column_set_view_{l}",
                    namespace=base_namespace,
                    template=template3,
                    locality=locality,
                    graph=graph,
                    layer=layer,
                )
            t_end_large_view = time.time()

            print(
                f"Average time to create large view: {(t_end_large_view - t_start_large_view) / n_large_view_attempts} s"
            )


if __name__ == "__main__":

    main()
