#!/bin/bash
LOCATION=$HOME/$NAME
PATH_TO_LOGS=$LOG_FILES

# Share location of the log file, we'll copy it before doing any reading
PAST_LOGS=$LOCATION/logs/
TIMESTAMP=$(date +%s)
LOG_COPY=$PAST_LOGS$TIMESTAMP.log

# Move and update
cd $LOCATION/binlogmon.git
git pull &>/dev/null

# Prep for actual execution
cp $PATH_TO_LOGS $LOG_COPY
python3 binglogmon.py -f $LOG_COPY --config config.json

# Cleanup
find $PAST_LOGS* -mtime +7 -exec rm {} \;
