#!/bin/bash
LOCATION=$HOME/$NAME
PATH_TO_LOGS=$LOG_FILES

# Share location of the log file, we'll copy it before doing any reading
PAST_LOGS=$LOCATION/logs-$NAME/
mkdir -p $PAST_LOGS
TIMESTAMP=$(date +%s)
LOG_COPY=$PAST_LOGS$TIMESTAMP.log

# Prep for actual execution
cp $PATH_TO_LOGS $LOG_COPY
python3 binlogmon.py -f $LOG_COPY --config $LOCATION/config-$NAME.json

# Cleanup
find $PAST_LOGS* -mtime +7 -exec rm {} \;
