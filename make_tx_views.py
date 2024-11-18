import gerrydb
from gerrydb import GerryDB
import time

if __name__ == "__main__":
    base_namespace = "census.2010"

    with GerryDB(namespace=base_namespace) as db:
        print(db.namespaces.all())

        locality = db.localities["tx"]
        layer = db.geo_layers["block"]

        # print("Getting graph...")
        # t_start_get_graph = time.time()
        # graph = db.graphs["tx_block_2010_dual"]
        # t_end_get_graph = time.time()
        # print(f"Time to get graph: {t_end_get_graph - t_start_get_graph}")

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
            n_single_column_attempts = 10
            t_start_single_column = time.time()
            for i in range(n_single_column_attempts):
                ctx.views.create(
                    path=f"test_single_column_view_{i}",
                    namespace=base_namespace,
                    template=template1,
                    locality=locality,
                    # graph=graph,
                    layer=layer,
                )
            t_end_single_column = time.time()
            print(
                f"Average time to create single column view: {(t_end_single_column - t_start_single_column) / n_single_column_attempts}"
            )

            # Time create small column set

            column_set_columns2 = [
                "name",
                "one_race_pop",
                "two_or_more_races_pop",
            ]

            n_col_set_attempts = 10

            column_set2 = ctx.column_sets.create(
                path="test_small_column_set",
                columns=column_set_columns2,
                namespace=base_namespace,
                description="Small column set for testing.",
            )

            t_start_small_column_set = time.time()
            for j in range(n_col_set_attempts):
                ctx.column_sets.create(
                    path=f"test_small_column_set_{j}",
                    columns=column_set_columns2,
                    namespace=base_namespace,
                    description="Small column set for testing.",
                )
            t_end_small_column_set = time.time()

            print(
                f"Average time to create small column set: {(t_end_small_column_set - t_start_small_column_set) / n_col_set_attempts}"
            )
            # Time render small view from single column and small column set of 3 columns

            columns2 = [
                "total_pop",
            ]

            # Time create large column set

            all_columns = db.columns.all()
            column_set_columns3 = [col.canonical_path for col in all_columns]

            # Time render large view from large column set
