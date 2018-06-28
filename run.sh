#!/bin/sh

cd "$(dirname "$0")"

. ./scripts/common_startup_functions.sh

# If there is a file that defines a shell environment specific to this
# instance of Galaxy, source the file.
if [ -z "$GALAXY_LOCAL_ENV_FILE" ];
then
    GALAXY_LOCAL_ENV_FILE='./config/local_env.sh'
fi

if [ -f $GALAXY_LOCAL_ENV_FILE ];
then
    . $GALAXY_LOCAL_ENV_FILE
fi

./scripts/common_startup.sh $common_startup_args || exit 1

parse_common_args $@

run_common_start_up

setup_python

if [ ! -z "$GALAXY_RUN_WITH_TEST_TOOLS" ];
then
    export GALAXY_CONFIG_OVERRIDE_TOOL_CONFIG_FILE="test/functional/tools/samples_tool_conf.xml"
    export GALAXY_CONFIG_ENABLE_BETA_WORKFLOW_MODULES="true"
    export GALAXY_CONFIG_OVERRIDE_ENABLE_BETA_TOOL_FORMATS="true"
    export GALAXY_CONFIG_OVERRIDE_WEBHOOKS_DIR="test/functional/webhooks"
fi

if [ -n "$GALAXY_UNIVERSE_CONFIG_DIR" ]; then
    python ./scripts/build_universe_config.py "$GALAXY_UNIVERSE_CONFIG_DIR"
fi

if [ -z "$GALAXY_CONFIG_FILE" ]; then
    if [ -f universe_wsgi.ini ]; then
        GALAXY_CONFIG_FILE=universe_wsgi.ini
    elif [ -f config/galaxy.ini ]; then
        GALAXY_CONFIG_FILE=config/galaxy.ini
    else
        GALAXY_CONFIG_FILE=config/galaxy.ini.sample
    fi
    export GALAXY_CONFIG_FILE
fi

if [ $INITIALIZE_TOOL_DEPENDENCIES -eq 1 ]; then
    # Install Conda environment if needed.
    python ./scripts/manage_tool_dependencies.py -c "$GALAXY_CONFIG_FILE" init_if_needed
fi

if [ -n "$GALAXY_RUN_ALL" ]; then
    servers=$(sed -n 's/^\[server:\(.*\)\]/\1/  p' "$GALAXY_CONFIG_FILE" | xargs echo)
    if [ -z "$stop_daemon_arg_set" -a -z "$daemon_or_restart_arg_set" ]; then
        echo "ERROR: \$GALAXY_RUN_ALL cannot be used without the '--daemon', '--stop-daemon' or 'restart' arguments to run.sh"
        exit 1
    fi
    for server in $servers; do
        if [ -n "$wait_arg_set" -a -n "$daemon_or_restart_arg_set" ]; then
            python ./scripts/paster.py serve "$GALAXY_CONFIG_FILE" --server-name="$server" --pid-file="$server.pid" --log-file="$server.log" $paster_args
            while true; do
                sleep 1
                printf "."
                # Grab the current pid from the pid file
                if ! current_pid_in_file=$(cat "$server.pid"); then
                    echo "A Galaxy process died, interrupting" >&2
                    exit 1
                fi
                # Search for all pids in the logs and tail for the last one
                latest_pid=$(egrep '^Starting server in PID [0-9]+\.$' "$server.log" -o | sed 's/Starting server in PID //g;s/\.$//g' | tail -n 1)
                # If they're equivalent, then the current pid file agrees with our logs
                # and we've succesfully started
                [ -n "$latest_pid" ] && [ "$latest_pid" -eq "$current_pid_in_file" ] && break
            done
            echo
        else
            echo "Handling $server with log file $server.log..."
            python ./scripts/paster.py serve "$GALAXY_CONFIG_FILE" --server-name="$server" --pid-file="$server.pid" --log-file="$server.log" $paster_args
        fi
    done
else
    # Handle only 1 server, whose name can be specified with --server-name parameter (defaults to "main")
    python ./scripts/paster.py serve "$GALAXY_CONFIG_FILE" $paster_args
fi
