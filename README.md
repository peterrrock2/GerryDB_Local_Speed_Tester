# GerryDB Local Speed Tester

The main script in this file is `run_speed_test.sh` and it is meant to
be a quick way to test the speed of the view generation in GerryDB. The
vanilla version of the script tests tests against WY counties. Adding the
flag `--large, -l` will test against WY blocks and `--extreme, -x` will test
against TX blocks. Expect the TX block test to take a several hours.
