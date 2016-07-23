#!/bin/bash

# The test.dat file was generated using python and the following snippet of code
# with open ('test.dat', 'wb') as f:
#     f.write(bytes([0x65, 0x66, 0x67, 0x00, 0x00, 0xF1, 0xAA, 0x30, 0x39, 0x31, 0x32]))
#     f.write(bytes([0x71, 0x66, 0x67, 0x68, 0x69, 0xF1, 0xAA, 0x30, 0x39, 0x31, 0x33]))
#     f.write(bytes([0x65, 0x68, 0x67, 0x00, 0x00, 0xF1, 0xAA, 0x30, 0x39, 0x32, 0x32]))

# Ability to control what tests run via CLI args
ARGS=$1
RUN_TEST=1
CACHE_TESTS=0
FILTER_TESTS=0
NORMAL_TESTS=0
OVERRIDE_TESTS=0
TYPE_TESTS=0

if [ -z "$ARGS" ]; then
    CACHE_TESTS=$RUN_TEST
    FILTER_TESTS=$RUN_TEST
    NORMAL_TESTS=$RUN_TEST
    OVERRIDE_TESTS=$RUN_TEST
    TYPE_TESTS=$RUN_TEST
else
    case $ARGS in
        "--filter")
            FILTER_TESTS=$RUN_TEST
            ;;
        "--cache")
            CACHE_TESTS=$RUN_TEST
            NORMAL_TESTS=$RUN_TEST
            ;;
        "--normal")
            NORMAL_TESTS=$RUN_TEST
            ;;
        "--override")
            OVERRIDE_TESTS=$RUN_TEST
            ;;
        "--types")
            TYPE_TESTS=$RUN_TEST
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
RAW_URL="http://some/valid/twiml/url"
URL="($RAW_URL)"
NUMBER1="number1"
NUMBER2="number2"
NUMBER3="number3"
LONG_MESSAGE=" (and {remaining} more messages)"
SMS_NUMBER="$NUMBER1 $NUMBER2"
PHONE_NUMBER="$NUMBER1 $NUMBER3"
SMS="sms"
PHONE="phone"
RM_FILE=1
CONFIG_PREFIX="test-"
CONFIG_POSTFIX=".json"
LAST_JSON="last.json"
NORMAL_MSG="$CACHE_MSG$ALL_LONG"

# The 'normal' cache variables
CACHE_DATE="2043-03-20 13:18:40"
CACHE_MSG="qfghi"
CACHE_TIME="858863920"
NORMAL_FROM="from-number"
ALL_LONG=$(echo "$LONG_MESSAGE" | sed -e "s/{0}/2/g")

# Filter test data
FILTER_CONFIG="filters"
FILTER_CACHE_TIME="842152240"
FILTER_CACHE_MSG="ehg"
FILTER_CACHE_DATE="2042-09-08 03:10:40"
FILTER_ALL_LONG=" (and 1 more messages)"
WHITELIST_CONFIG="whitelist"
WHITEBLACK_CONFIG="whiteblack"

# Override testing
OVERRIDE_ALT="alternative-num"
OVERRIDE_CONFIG="override"

# Example config
EXAMPLE_CONFIG="example"

# URL config
URL_CONFIG="url"

# Console config
CONSOLE_CONFIG="console"

function get-config-name()
{
    echo ${CONFIG_PREFIX}$1${CONFIG_POSTFIX}
}

CONFIG_FILE="{
    \"twilio\":
    {
        \"sid\": \"twilio-sid\",
        \"token\": \"twilio-auth-token\",
        \"from\": \"$NORMAL_FROM\",
        \"sms\": 
        {
            \"to\": [\"$NUMBER1\", \"$NUMBER2\"],
            \"long\": \"$LONG_MESSAGE\",
            \"message\": \"{datetime} - {first}{long}\"
        },
        \"call\":
        {
            \"to\": [\"$NUMBER1\", \"$NUMBER3\"],
            \"url\": \"$RAW_URL\"
        }
    },
    \"cache\":\"$LAST_JSON\",
    \"start\":\"2016-01-01 00:00:00\",
    \"size\":11,
    \"pattern\": \"<5sxsi\",
    \"message\":0,
    \"time\":2
}"

FILTER_FILE="{
    \"blacklist\":[\"$CACHE_MSG\"],
    \"shared\": \"$(get-config-name $DEFAULT_CONFIG)\"
}"


WHITELIST_FILE="{
    \"shared\": \"$(get-config-name $DEFAULT_CONFIG)\",
    \"whitelist\":[\"^((?!$CACHE_MSG).)*\$\"]
}"

WHITEANDBLACKLIST_FILE="{
    \"blacklist\":[\"$CACHE_MSG\"],
    \"whitelist\":[\"^((?!$CACHE_MSG).)*\$\", \"$CACHE_MSG\"],
    \"shared\": \"$(get-config-name $DEFAULT_CONFIG)\"
}"

OVERRIDE_FILE="{
    \"twilio\":
    {
        \"from\": \"$OVERRIDE_ALT\"
    },
    \"override\": false,
    \"shared\": \"$(get-config-name $DEFAULT_CONFIG)\"
}"

URL_TEST="http://test/url"
URL_TEST_P1="p1"
URL_FILE=$(echo "$CONFIG_FILE" | head -n -1)",
    \"post\":
    {
        \"urls\": 
        [
            {
                \"url\": \"$URL_TEST\",
                \"kv\":{
                    \"$URL_TEST_P1\": \"xyz\",
                    \"p2\": \"abc\"
                },
                \"populate\":{\"key_value\":\"test\"},
                \"headers\": {}
            },
            {
                \"url\": \"$URL_TEST\",
                \"kv\":{
                    \"$URL_TEST_P1\": \"xyz\"
                },
                \"populate\":{\"key_value\":\"test\"},
                \"headers\": {\"h1\": \"x\", \"h2\": \"y\"}
            }
        ]
    }
}
"

CONSOLE_CMD="--console"
CONSOLE_FILE=$(echo "$CONFIG_FILE" | head -n -1)",
    \"console\":{}
}"

EXAMPLE_FILE=$(cat ../example.json | sed "s/\/path\/to\/cache\/last\/detected\///g" | sed "s/\/path\/to\/file\/to\/lock/lock.json/g" | sed "s/\/path\/to\/a\/shared\/config.json//g")

PHONE_CONFIG=$(echo "$CONFIG_FILE" | sed "s/\"sms\"/\"other\"/g")
SMS_CONFIG=$(echo "$CONFIG_FILE" | sed "s/\"call\"/\"other\"/g")

# Run tests (config to use, indicator to delete cache file)
function run-test()
{
    do_remove=1
    added_args=${@:2}
    if [ -z "$2" ]; then
        do_remove=0
    else
        if [[ "$2" == "$CONSOLE_CMD" ]]; then
            do_remove=0
        else
            added_args=${@:3}
        fi
    fi
    if [ $do_remove -eq 0 ]; then
        rm -f $LAST_JSON
    fi

    execute-run $1 "-f test.dat" $added_args
}

function execute-run()
{
    result=$(binlogmon $2 --config $(get-config-name $1) --dry-run ${@:3})
    echo "$result"
}

# Check if a cache value is set (contents, key, value)
function check-cache-value()
{
    echo "$1" | grep -q "\"$2\": $3"
    if [ $? -ne 0 ]; then
        echo "$1"
        echo "FAILED checking cached $2 ($3)"
        exit -1
    fi   
}

# Check the cache value for items (time, datetime, message)
function check-cached()
{
    contents=$(cat $LAST_JSON)
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

# Save a config file to disk (content, file name)
function save-config()
{
    echo "$1" > $(get-config-name $2)
}

# Test a single sms/phone/etc type of output (config, numbers, message)
function single-type-test()
{
    results=$(run-test "$1")
    check-content "$results" "$2" "$3" "$1"
    normal-cache
    if [ $(echo "$results" | grep -co "$3") -ne 2 ]; then
        echo "FAILED: should only see outputs of type $1"
        exit -1
    fi
}

# Override test (from)
function override-test()
{
    results=$(run-test "$OVERRIDE_CONFIG")
    check-all-content "$results" "$NORMAL_MSG" "$URL"
    normal-cache
    if [ $(echo "$results" | grep -co "$1") -ne 4 ]; then
        echo "FAILED: should only see numbers from $1"
        exit -1
    fi
}

# Cleanup and setup before any and all tests
rm -f *.log
rm -f *.json
save-config "$CONFIG_FILE" $DEFAULT_CONFIG
save-config "$FILTER_FILE" $FILTER_CONFIG
save-config "$PHONE_CONFIG" $PHONE
save-config "$SMS_CONFIG" $SMS
save-config "$OVERRIDE_FILE" $OVERRIDE_CONFIG
save-config "$EXAMPLE_FILE" $EXAMPLE_CONFIG
save-config "$WHITELIST_FILE" $WHITELIST_CONFIG
save-config "$WHITEANDBLACKLIST_FILE" $WHITEBLACK_CONFIG
save-config "$URL_FILE" $URL_CONFIG
save-config "$CONSOLE_FILE" $CONSOLE_CONFIG

if [ $NORMAL_TESTS -eq $RUN_TEST ]; then
    echo "Message test..."
    results=$(execute-run "$DEFAULT_CONFIG" "-t qfghii10913")
    check-all-content "$results" "$NORMAL_MSG" "$URL"
    normal-cache

    echo "Normal test..."
    results=$(run-test "$DEFAULT_CONFIG")
    check-all-content "$results" "$NORMAL_MSG" "$URL"
    normal-cache

    echo "Normal (call-only)..."
    single-type-test "$PHONE" "$PHONE_NUMBER" "$URL"
    
    echo "Normal (sms-only)..."
    single-type-test "$SMS" "$SMS_NUMBER" "$NORMAL_MSG"
    
    echo "Example test..."
    results=$(run-test "$EXAMPLE_CONFIG")
    check-all-content "$results" "$NORMAL_MSG" "$URL"
    normal-cache
fi

function console-test()
{
    check-all-content "$1" "$NORMAL_MSG" "$URL"
    cli_count=$(echo "$1" | grep "(DRYRUN)" | wc -l)
    if [ $cli_count -ne 3 ]; then
        echo "FAILED - should have dryrun for each message output on CLI"
        exit -1
    fi
}

if [ $TYPE_TESTS -eq $RUN_TEST ]; then
    echo "URL test..."
    results=$(run-test "$URL_CONFIG")
    check-all-content "$results" "$NORMAL_MSG" "$URL"
    url_count=$(echo "$results" | grep "$URL_TEST" | grep "$URL_TEST_P1" | wc -l)
    if [ $url_count -ne 6 ]; then
        echo "FAILED - should have had multiple urls"
        exit -1
    fi
    url_count=$(echo "$results" | grep "$URL_TEST" | grep "h1" | wc -l)
    if [ $url_count -ne 3 ]; then
        echo "FAILED - should have had headers in a url"
        exit -1
    fi
    url_count=$(echo "$results" | grep "$URL_TEST" | grep "p2" | wc -l)
    if [ $url_count -ne 3 ]; then
        echo "FAILED - should have had p2 in a url"
        exit -1
    fi
    normal-cache

    echo "Console test..."
    results=$(run-test "$CONSOLE_CONFIG")
    console-test "$results"
    normal-cache
    
    echo "Console (cli) test..."
    results=$(run-test "$DEFAULT_CONFIG" $CONSOLE_CMD)
    console-test "$results"
    normal-cache
fi

if [ $CACHE_TESTS -eq $RUN_TEST ]; then
    echo "Cache test..."
    results=$(run-test "config" $RM_FILE)
    if [[ "$results" != "" ]]; then
        echo "FAILED - result should be empty"
        exit -1
    fi
    normal-cache
    
    sed -i -- "s/$CACHE_TIME/$((CACHE_TIME - 1))/g" $LAST_JSON
    echo "Cache test partial..."
    results=$(run-test "config" $RM_FILE)
    check-all-content "$results" "$CACHE_MSG$SHORT_SMS" "$URL"
    normal-cache
fi

if [ $FILTER_TESTS -eq $RUN_TEST ]; then
    echo "Filter test..."
    results=$(run-test "$FILTER_CONFIG")
    check-all-content "$results" "$FILTER_CACHE_MSG$FILTER_ALL_LONG" "$URL"
    filter-cache

    sed -i -- "s/$FILTER_CACHE_TIME/$((FILTER_CACHE_TIME - 1))/g" $LAST_JSON
    echo "Filter cache test partial..."
    results=$(run-test "$FILTER_CONFIG" $RM_FILE)
    check-all-content "$results" "$FILTER_CACHE_MSG$SHORT_SMS" "$URL"
    filter-cache

    echo "Whitelist test..."
    results=$(run-test "$WHITELIST_CONFIG")
    check-all-content "$results" "$FILTER_CACHE_MSG$FILTER_ALL_LONG" "$URL"
    filter-cache

    echo "Whitelist/blacklist test..."
    results=$(run-test "$WHITEBLACK_CONFIG")
    check-all-content "$results" "$FILTER_CACHE_MSG$FILTER_ALL_LONG" "$URL"
    filter-cache
fi

if [ $OVERRIDE_TESTS -eq $RUN_TEST ]; then
    echo "Override test (normal)..."
    override-test "$NORMAL_FROM"
    
    sed -i -- "s/false/true/g" $(get-config-name $OVERRIDE_CONFIG)
    echo "Override test..."
    override-test "$OVERRIDE_ALT"
fi
