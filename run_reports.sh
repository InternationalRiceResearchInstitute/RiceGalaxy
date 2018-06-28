#!/bin/sh


# Usage: ./run_reports.sh [--sync-config] <start|stop>
#
#
# Description: This script can be used to start or stop the galaxy
# reports web application. Passing in --sync-config as the first
# argument to this will cause Galaxy's database and path parameters
# from galaxy.ini to be copied over into reports.ini.

cd "$(dirname "$0")"

GALAXY_REPORTS_PID=${GALAXY_REPORTS_PID:-reports_webapp.pid}
GALAXY_REPORTS_LOG=${GALAXY_REPORTS_LOG:-reports_webapp.log}
PID_FILE=$GALAXY_REPORTS_PID
LOG_FILE=$GALAXY_REPORTS_LOG

. ./scripts/common_startup_functions.sh

if [ "$1" = "--sync-config" ];
then
    python ./scripts/sync_reports_config.py
    shift
fi

parse_common_args $@

run_common_start_up

setup_python

if [ -z "$GALAXY_REPORTS_CONFIG" ]; then
    if [ -f reports_wsgi.ini ]; then
        GALAXY_REPORTS_CONFIG=reports_wsgi.ini
    elif [ -f config/reports_wsgi.ini ]; then
        GALAXY_REPORTS_CONFIG=config/reports_wsgi.ini
    elif [ -f config/reports.ini ]; then
        GALAXY_REPORTS_CONFIG=config/reports.ini
    elif [ -f config/reports.yml ]; then
        GALAXY_REPORTS_CONFIG=config/reports.yml
    else
        GALAXY_REPORTS_CONFIG=config/reports.yml.sample
    fi
    export GALAXY_REPORTS_CONFIG
fi

if [ -n "$GALAXY_REPORTS_CONFIG_DIR" ]; then
    python ./scripts/build_universe_config.py "$GALAXY_REPORTS_CONFIG_DIR" "$GALAXY_REPORTS_CONFIG"
fi

find_server $GALAXY_REPORTS_CONFIG
$run_server $server_args
