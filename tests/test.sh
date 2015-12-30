#!/bin/bash

# The test.dat file was generated using python and the following snippet of code
# with open ('test.dat', 'wb') as f:
#     f.write(bytes([0x65, 0x66, 0x67, 0x00, 0x00, 0xF1, 0xAA, 0x30, 0x39, 0x31, 0x32]))
#     f.write(bytes([0x71, 0x66, 0x67, 0x68, 0x69, 0xF1, 0xAA, 0x30, 0x39, 0x31, 0x33]))
#     f.write(bytes([0x65, 0x68, 0x67, 0x00, 0x00, 0xF1, 0xAA, 0x30, 0x39, 0x32, 0x32]))

# Ability to control what tests run via CLI args
ARGS=$1
CACHE_TESTS=0
FILTER_TESTS=0
NORMAL_TESTS=0

if [ -z "$ARGS" ]; then
    CACHE_TESTS=1
    FILTER_TESTS=1
    NORMAL_TESTS=1
else
    case $ARGS in
        "--filter")
            FILTER_TESTS=1
            ;;
        "--cache")
            CACHE_TESTS=1
            NORMAL_TESTS=1
            ;;
        "--normal")
            NORMAL_TESTS=1
            ;;
        *)
            echo "Unknown argument: $ARGS"
            exit -1
            ;;
    esac    
fi

# Overall test variables
DEFAULT_CONFIG="config"
SHORT_SMS=")"
URL="(http://some/valid/twiml/url)"
SMS_NUMBER="number1 number2"
PHONE_NUMBER="number1 number3"
SMS="sms"
PHONE="phone"
RM_FILE=1

# The 'normal' cache variables
CACHE_DATE="2043-03-20 13:18:40"
CACHE_MSG="qfghi"
CACHE_TIME="858863920"
ALL_LONG=" (and 2 more messages)"

# Filter test data
FILTER_CONFIG="filters"
FILTER_CACHE_TIME="842152240"
FILTER_CACHE_MSG="ehg"
FILTER_CACHE_DATE="2042-09-08 03:10:40"
FILTER_ALL_LONG=" (and 1 more messages)"

# Run tests (config to use, indicator to delete cache file)
function run-test()
{
    if [ -z "$2" ]; then
        rm -f last.json
    fi
    result=$(python3 ../binlogmon.py -f test.dat --config test-$1.json --dry-run)
    echo "$result"
}

# Check if a cache value is set (contents, key, value)
function check-cache-value()
{
    echo "$1" | grep -q "\"$2\": $3"
    if [ $? -ne 0 ]; then
        echo "$1"
        echo "FAILED checking cached $2"
        exit -1
    fi   
}

# Check the cache value for items (time, datetime, message)
function check-cached()
{
    contents=$(cat last.json)
    check-cache-value "$contents" "time" "$1"
    check-cache-value "$contents" "datetime" "\"$2\""
    check-cache-value "$contents" "message" "\"$3\""    
}

# Check results for specified text (contents, type, number, message)
function check-results()
{
     subset=$(echo "$1" | grep "to: $3")
     echo "$subset" | grep -q " $4"
     if [ $? -ne 0 ]; then
        echo "$1"
        echo "FAILED result check: $2 (to: $3, message $4)"
        exit -1
     fi
}

# Check contents for multiple addresses/numbers (content, numbers, message, type)
function check-content()
{
    for num in $2; do
        check-results "$1" "$4" $num "$3"
    done
}

# Check all file contents (content, sms message, phone message)
function check-all-content()
{
    check-content "$1" "$SMS_NUMBER" "$2" "$SMS"
    check-content "$1" "$PHONE_NUMBER" "$3" "$PHONE"
}

# Normal cache check
function normal-cache()
{
    check-cached "$CACHE_TIME" "$CACHE_DATE" "$CACHE_MSG"
}

# Filter cache check
function filter-cache()
{
    check-cached "$FILTER_CACHE_TIME" "$FILTER_CACHE_DATE" "$FILTER_CACHE_MSG"   
}

if [ $NORMAL_TESTS -eq 1 ]; then
    echo "Normal test..."
    results=$(run-test "$DEFAULT_CONFIG")
    normal-cache
    check-all-content "$results" "$CACHE_MSG$ALL_LONG" "$URL"
fi

if [ $CACHE_TESTS -eq 1 ]; then
    echo "Cache test..."
    results=$(run-test "config" $RM_FILE)
    normal-cache
    if [[ "$results" != "" ]]; then
        echo "FAILED - result should be empty"
        exit -1
    fi
    
    sed -i -- "s/$CACHE_TIME/$((CACHE_TIME - 1))/g" last.json
    echo "Cache test partial..."
    results=$(run-test "config" $RM_FILE)
    normal-cache
    check-all-content "$results" "$CACHE_MSG$SHORT_SMS" "$URL"
fi

if [ $FILTER_TESTS -eq 1 ]; then
    echo "Filter test..."
    results=$(run-test "$FILTER_CONFIG")
    filter-cache
    check-all-content "$results" "$FILTER_CACHE_MSG$FILTER_ALL_LONG" "$URL"

    sed -i -- "s/$FILTER_CACHE_TIME/$((FILTER_CACHE_TIME - 1))/g" last.json
    echo "Filter cache test partial..."
    results=$(run-test "$FILTER_CONFIG" $RM_FILE)
    filter-cache
    check-all-content "$results" "$FILTER_CACHE_MSG$SHORT_SMS" "$URL"
fi