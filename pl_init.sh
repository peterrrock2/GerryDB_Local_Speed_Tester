#!/bin/bash

### Bootstraps a new GerryDB instance with core Census metadata. ###
years=( "2010" "2020" )

# Just doing the central spine levels for speed testing
levels=(
    "state"
    "county"
    "tract"
    "bg"
    "block"
)
pl_source_url="https://www2.census.gov/geo/tiger/TIGER2020PL/"
base_dir="$( dirname -- "$0"; )"

# this has been run, all localities exist in DB
# suppress_existence flag handles error raised when a locality already exists
echo "Bootstrapping localities..."
python -m gerrydb_etl.bootstrap.pl_localities 

# echo "Bootstrapping Census namespaces..."
# for year in "${years[@]}"
# do
#     python -m gerrydb.create namespace \
#         "census.$year" \
#         --description "$year U.S. Census PL 94-171 release" \
#         --public
# done

# echo "Bootstrapping geographic layers..."
# for year in "${years[@]}"
# do
#     python -m gerrydb.create geo-layer \
#         block \
#         --namespace "census.$year" \
#         --description "$year U.S. Census blocks" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         bg \
#         --namespace "census.$year" \
#         --description "$year U.S. Census block groups" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         tract \
#         --namespace "census.$year" \
#         --description "$year U.S. Census tracts" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         county \
#         --namespace "census.$year" \
#         --description "$year U.S. Census counties" \
#         --source-url $pl_source_url 

#     python -m gerrydb.create geo-layer \
#         state \
#         --namespace "census.$year" \
#         --description "$year U.S. Census states" \
#         --source-url $pl_source_url 

#     python -m gerrydb.create geo-layer \
#         vtd \
#         --namespace "census.$year" \
#         --description "$year U.S. Census VTDs (voting tabulation districts)" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         place \
#         --namespace "census.$year" \
#         --description "$year U.S. Census places" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         cousub \
#         --namespace "census.$year" \
#         --description "$year U.S. Census county subdivisions" \
#         --source-url $pl_source_url

#     python -m gerrydb.create geo-layer \
#         aiannh \
#         --namespace "census.$year" \
#         --description "$year U.S. Census AIANNHs (American Indian/Alaska Native/Native Hawaiian Areas)" \
#         --source-url $pl_source_url
# done

# echo "Creating Census geographic columns..."
# for year in "${years[@]}"
# do
#     python -m gerrydb_etl.bootstrap.templated_columns \
#         --namespace "census.$year" \
#         --template "$base_dir/columns/pl_geo.yaml" \
#         --yr "${year:2:2}" \
#         --year $year
# done

# echo "Creating Census PL 94-171 population columns..."
# for year in "${years[@]}"
# do
#     python -m gerrydb_etl.bootstrap.pl_pop_table_columns \
#         --namespace "census.$year" \
#         --year $year
# done
