#!/bin/bash


run_with_spinner() {
    local pid=$!
    local spin='|/-\'
    local i=0

    # Display spinner while the background process runs
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) % 4 ))
        printf "\r$1 ${spin:$i:1}"  # Show spinner with carriage return
        sleep 0.5
    done
    echo
}


function show_help() {
    echo
    echo "Usage: run_speed_test.sh [OPTIONS]"
    echo
    echo "Description:"
    echo "  Run a speed test on the GerryDB server."
    echo "  When no flags are provided, the speed test will run on WY County data."
    echo
    echo "Options:"
    echo "  -l, --large       Run speed test on WY Block data. (Will take ~20-30 minutes.)"
    echo "  -x, --extreme     Run speed test on TX Block data. (Will take a couple of hours.)"
    echo "                      Overwrites --large flag."
    echo "  -h, --help        Show this help message and exit."
    echo
}


# Default values
large=0
extreme=0

# Parse options
while [[ $# -gt 0 ]]; do
  case $1 in
    -l|--large)   # Match both -l and --large
      large=1
      shift
      ;;
    -x|--extreme)
      extreme=1
      shift
      ;;
    -h|--help)
      show_help
      exit 0 
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done




# =====================
# Environment variables
# =====================
export PGPASSWORD='dev'
export GERRYDB_TEST_API_KEY="7w7uv9mi575n2dhlmg3wqba2imv1aqdys387tpbtpermujy1tuyqbxetygx8u3fr"
export COLUMN_CONFIG_PATH="./pl_geo.yaml"
export GERRYDB_DATABASE_URI="postgresql://postgres:dev@localhost:54320/gerrydb"



# ========================
# Check python environment
# ========================
python -c "import gerrydb; import gerrydb_meta; import gerrydb_etl"

if [ $? -ne 0 ]; then
    echo "Could not import relevant modules in python. Make sure the appropriate python environment is activated."
    exit 1
fi 


# ================================
# Checking if POSTGIS is installed
# ================================

postgis help > /dev/null 2>&1

if [ $? -ne 0 ]; then
    echo "Could not POSTGIS extension in path. Please install POSTGIS before running this script."
    exit 1
fi


# =============================
# Getting uvicorn server set up
# =============================
echo 

uvicorn uvicorn_runner:app --reload --port 8000 > LOG_uvicorn.log 2>&1 &
uvicorn_pid=$!

# Wait for the server to finish setting up
sleep 3

echo "Checking for uvicorn server..."
lsof -i :8000 | grep uvicorn > /dev/null

if [ $? -ne 0 ]; then
    echo "Could not find uvicorn server running on port 8000. Please start the server before running this script."
    exit 1
fi 

echo "Found uvicorn server running on port 8000!"
echo 

# =====================
# Getting Docker set up
# =====================
previous_context=$(docker context show)
echo "Current docker context is '$previous_context'"
echo "Creating 'speed_test' context for docker..."
docker context create speed_test > /dev/null

if [ $? -ne 0 ]; then
    echo "Could not create docker context. Please check your docker installation."
    exit 1
fi

docker context use speed_test > /dev/null
echo "Creating docker volume for database use in speed test..."
docker volume remove db_speed_test_data > /dev/null 2>&1
docker volume create db_speed_test_data > /dev/null
echo "Setting up docker containers..."
docker compose up -d 


echo "Checking for docker container on port 54320..."
lsof -i :54320 | grep dock > /dev/null
if [ $? -ne 0 ]; then
    echo "Could not find docker container running on port 54320.  "
    exit 1
fi
echo 


spin='|/-\'
i=0

until pg_isready -h localhost -p 54320 -U postgres > /dev/null 2>&1; do
    i=$(( (i+1) % 4 ))  # Cycle through spinner characters
    printf "\rWaiting for PostgreSQL to be ready... ${spin:$i:1}"  # Display spinner with carriage return
    sleep 0.5
done

echo


# # ===============================
# # Setting up Postgres Environment
# # ===============================
psql -U postgres -h localhost -p 54320 -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'gerrydb'" | grep -q 1 || \
psql -U postgres -h localhost -p 54320 -d postgres -c "CREATE DATABASE gerrydb;"
psql -U postgres -h localhost -p 54320 -d gerrydb -c "CREATE EXTENSION IF NOT EXISTS postgis;"


# =======================
# Initialize the database
# =======================
python gerrydb_init.py --name=test_user --email=test@test.com --reset --use-test-key > /dev/null <<EOF
y
EOF

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

SECONDS=0
python -m gerrydb_etl.bootstrap.pl_localities 1> LOG_localities.log 2>&1 & run_with_spinner "Bootstrapping localities..."
echo "Time to bootstrap localities: $SECONDS s"
# pg_restore -U postgres -h localhost -p 54320 -d gerrydb -c -Ft ./wy_init.tar

SECONDS=0
(
    for year in "${years[@]}"
    do
        python -m gerrydb.create namespace \
            "census.$year" \
            --description "$year U.S. Census PL 94-171 release" \
            --public
    done
) & run_with_spinner "Bootstrapping Census namespaces..."
echo "Time to bootstrap namespaces: $SECONDS s"


SECONDS=0
(
    for year in "${years[@]}"
    do
        python -m gerrydb.create geo-layer \
            block \
            --namespace "census.$year" \
            --description "$year U.S. Census blocks" \
            --source-url $pl_source_url

        python -m gerrydb.create geo-layer \
            bg \
            --namespace "census.$year" \
            --description "$year U.S. Census block groups" \
            --source-url $pl_source_url

        python -m gerrydb.create geo-layer \
            tract \
            --namespace "census.$year" \
            --description "$year U.S. Census tracts" \
            --source-url $pl_source_url

        python -m gerrydb.create geo-layer \
            county \
            --namespace "census.$year" \
            --description "$year U.S. Census counties" \
            --source-url $pl_source_url 

        python -m gerrydb.create geo-layer \
            state \
            --namespace "census.$year" \
            --description "$year U.S. Census states" \
            --source-url $pl_source_url 
    done
) & run_with_spinner "Bootstrapping geographic layers..."
echo "Time to bootstrap geographic layers: $SECONDS s"

echo "" > LOG_geo_columns.log
SECONDS=0
(
    for year in "${years[@]}"
    do
        python -m gerrydb_etl.bootstrap.templated_columns \
            --namespace "census.$year" \
            --template "./pl_geo.yaml" \
            --yr "${year:2:2}" \
            --year $year >> LOG_geo_columns.log 2>&1 
    done
) & run_with_spinner "Creating Census geographic columns... "
echo "Time to create geographic columns: $SECONDS s"

echo "" > LOG_pop_columns.log
SECONDS=0
(
    for year in "${years[@]}"
    do
        python -m gerrydb_etl.bootstrap.pl_pop_table_columns \
            --namespace "census.$year" \
            --year $year > LOG_pop_columns.log 2>&1
    done
) & run_with_spinner "Creating Census PL 94-171 population columns..."
echo "Time to create population columns: $SECONDS s"


# ===============
# Load State Data
# ===============

echo

SECONDS=0
python load_test_geo.py --large=$large --extreme=$extreme > /dev/null 2>&1 & run_with_spinner "Running load_wy_geo.py..."
echo
echo "Time to load geo: $SECONDS s"
echo
SECONDS=0
python load_test_graph.py --large=$large --extreme=$extreme > /dev/null 2>&1 & run_with_spinner "Running load_wy_graph.py..."
echo
echo "Time to load graph: $SECONDS s"
echo
SECONDS=0
python load_test_pop.py --large=$large --extreme=$extreme > /dev/null 2>&1 & run_with_spinner "Running load_wy_pop.py..."
echo
echo "Time to load pop: $SECONDS s"
echo


python make_views.py --large=$large --extreme=$extreme


# ==============================
# Tearing down docker containers
# ==============================

# kill $uvicorn_pid
# echo 
# echo "Tearing down docker containers..."
# docker compose down > /dev/null
# echo "Returning to previous context..."
# docker context use $previous_context > /dev/null
# docker context rm speed_test > /dev/null
# docker volume rm db_speed_test_data > /dev/null

