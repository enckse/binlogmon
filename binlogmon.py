#!/usb/bin/python

"""Binary log file monitoring."""

import datetime
import array
import struct
import argparse
import logging
import logging.handlers
import json
import os
import re
import time
import fcntl
from collections import deque

VERSION_NUMBER = "0.2.0"

__version__ = VERSION_NUMBER

OBJECT_TIME = 'time'
OBJECT_MESSAGE = 'message'
OBJECT_VIS_TIME = "datetime"
SMS_LENGTH = 100

SIZE_KEY = 'size'
START_KEY = 'start'
PATTERN_KEY = 'pattern'
MESSAGE_KEY = 'message'
TIME_KEY = 'time'
FILTER_KEY = 'filters'
ACCOUNT_SID_KEY = 'sid'
AUTH_TOKEN_KEY = 'token'
SMS_TO_KEY = 'sms'
FROM_KEY = 'from'
CACHE_KEY = 'cache'
LONG_MESSAGE_KEY = 'long'
CALL_KEY = 'call'
CALL_URL_KEY = 'url'
LOCK_KEY = 'lock'
SHARED_KEY = 'shared'

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
OUT_DATE = '%Y-%m-%dT%H:%M:%S'
FILE_CHUNKSIZE = 8192
LOG_LEVEL = logging.INFO


def process_file(logger, file_bytes, cache_object, configuration):
    """
    Process the binary log file bytes.

    Perform the actual reading of the file bytes and conversion
    to an output message set.
    """
    offset = 0
    last_reported = []
    filters = []
    start_date = datetime.datetime.strptime(configuration[START_KEY],
                                            DATE_FORMAT)
    chunking = configuration[SIZE_KEY]
    pattern = configuration[PATTERN_KEY]
    message_idx = configuration[MESSAGE_KEY]
    time_idx = configuration[TIME_KEY]
    for item in configuration[FILTER_KEY]:
        filters.append(re.compile(item))

    cache_time = None
    if cache_object is not None:
        cache_time = cache_object[OBJECT_TIME]

    while offset < len(file_bytes):
        all_bytes = file_bytes[0 + offset: chunking + offset]
        unpacked = struct.unpack(pattern,
                                 array.array('B', all_bytes).tostring())

        # expects ascii here
        raw_data = [x for x in unpacked[message_idx] if x != 0]
        raw_message = array.array('B', raw_data).tostring().decode('ascii')
        filter_out = False
        for item in filters:
            result = item.match(raw_message)
            if result is not None:
                filter_out = True
                break

        if not filter_out:
            obj = {}
            seconds = unpacked[time_idx]
            time = start_date + datetime.timedelta(seconds=seconds)

            # We can just sort and use the seconds offset
            # (even if it is abritrary because it still only counts up)
            obj[OBJECT_TIME] = seconds
            obj[OBJECT_MESSAGE] = raw_message

            # This is for actual troubleshooting/helping us
            # to provide the ability to see 'when' something actually happened
            obj[OBJECT_VIS_TIME] = str(time)

            if cache_time is None or obj[OBJECT_TIME] > cache_time:
                last_reported.append(obj)
        offset += chunking
    return last_reported


def send_message(logger, message_list, config, dry_run):
    """
    Send any applicable messages.

    Uses the twilio API to send out messages for any new messages read
    from the binary log file.
    """
    # Account sid (the account's sid on the dash/overall page)
    account_sid = config[ACCOUNT_SID_KEY]

    # Auth token (the account's auth token on the dash/overall page)
    auth_token = config[AUTH_TOKEN_KEY]

    # phone numbers to send messages to
    # NOTE: if using a test/trial twilio account, numbers must be 'verified'
    send_sms_messages = SMS_TO_KEY in config
    make_calls = CALL_KEY in config
    queued = []
    short_message = None
    call_url = None
    methods = []
    if send_sms_messages:
        check_parameter(LONG_MESSAGE_KEY, config)
        long_message = config[LONG_MESSAGE_KEY]
        short_message = datetime.datetime.now().strftime(OUT_DATE)
        short_message = short_message + " - "
        short_message += message_list[0][0:SMS_LENGTH]
        if len(message_list) > 1:
            short_message += long_message.format(len(message_list) - 1)

        logger.warn(short_message)
        methods.append(SMS_TO_KEY)

    if make_calls:
        check_parameter(CALL_URL_KEY, config)
        call_url = config[CALL_URL_KEY]
        logger.debug('using url: %s' % call_url)
        methods.append(CALL_KEY)

    for method in methods:
        for item in config[method]:
            queued.append((item, method))

    if not make_calls and not send_sms_messages:
        raise Exception("Not configured to call or sms anyone...")

    messaging_queue = deque(queued)

    # Must be the twilio number (setup via twilio)
    from_number = config[FROM_KEY]

    logger.info('sending messages from %s' % from_number)
    if not dry_run:
        import twilio
        import twilio.rest
        client = twilio.rest.TwilioRestClient(account_sid, auth_token)

    while len(messaging_queue) > 0:
        current_object = messaging_queue.popleft()
        item = current_object[0]
        function = current_object[1]
        try:
            logger.info("{0} to {1}".format(function, item))
            debug_data = ""
            if send_sms_messages and function == SMS_TO_KEY:
                debug_data = short_message
                if not dry_run:
                    message_object = client.messages.create(
                        body=short_message,
                        to=item,
                        from_=from_number
                    )

                    logger.info(message_object.sid)
            if make_calls and function == CALL_KEY:
                debug_data = call_url
                if not dry_run:
                    call_object = client.calls.create(
                        to=item,
                        from_=from_number,
                        url=call_url
                    )

                    logger.info(call_object.sid)

            if dry_run:
                debug_message = 'from: {0}, to: {1}, ({2})'.format(from_number,
                                                                   item,
                                                                   debug_data)
                logger.debug(debug_message)
                print(debug_message)

            # throttle us otherwise twilio will
            if len(messaging_queue) > 1:
                time.sleep(1)
        except Exception as e:
            logger.warn('unable to send message to %s' % item)
            logger.error(e)
            messaging_queue.append(item)

    logger.info('messages sent')
    return True


def check_parameter(key, configuration, default=None):
    """
    Check for parameters.

    Check if a parameter is set.
    If it isn't and there is a default - use default
    else
    that's a problem.
    """
    if key not in configuration:
        if default is None:
            raise Exception("missing required configuration item: %s" % key)
        else:
            configuration[key] = default


def file_locking(logger, do_lock, lock_file, enable):
    """Perform a file lock operation."""
    if do_lock:
        logger.debug('performing lock operation where enable is %s' % enable)
        control = fcntl.LOCK_EX if enable else fcntl.LOCK_UN
        with open(lock_file, 'w') as fd:
            fcntl.lockf(fd.fileno(), control)


def main():
    """
    Main entry point.

    Handle logging, argument parsing, and general orchestration.
    """
    logger = logging.getLogger('binlogmon')
    logger.setLevel(LOG_LEVEL)
    handler = logging.handlers.RotatingFileHandler('binlogmon.log',
                                                   maxBytes=10*1024*1024,
                                                   backupCount=10)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    exit_code = -1
    try:
        parser = argparse.ArgumentParser(
            description='Parse and report any binary log messages.')
        parser.add_argument('-f', '--file',
                            help='file name to read/parse/report from',
                            required=True)
        parser.add_argument('--dry-run',
                            help='run but do NOT send any messages',
                            action='store_true',
                            dest='dryrun')
        parser.add_argument('--debug',
                            help='provide debugging output',
                            action='store_true',
                            dest='debug')
        parser.add_argument('--config',
                            help='configuration file',
                            required=True)

        args = parser.parse_args()
        if args.debug:
            logger.setLevel(logging.DEBUG)
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        logger.info("script version %s" % VERSION_NUMBER)

        bytes = list()
        logger.info('reading file: %s' % args.file)
        with open(args.file, 'rb') as f:
            while True:
                chunk = f.read(FILE_CHUNKSIZE)
                if chunk:
                    for b in chunk:
                        bytes.append(b)
                else:
                    break

        config_file = None
        with open(args.config, 'r') as f:
            logger.debug('loading config')
            config_file = json.loads(f.read())
            logger.debug(config_file)

        if SHARED_KEY in config_file:
            logger.debug('loading shared config')
            with open(config_file[SHARED_KEY], 'r') as f:
                shared_config = json.loads(f.read())
                logger.debug(shared_config)

                # Replay this 'over' the given, it overrides
                for key in shared_config:
                    config_file[key] = shared_config[key]

        check_parameter(SIZE_KEY, config_file)
        check_parameter(START_KEY, config_file, '1970-01-01 00:00:00')
        check_parameter(PATTERN_KEY, config_file)
        check_parameter(MESSAGE_KEY, config_file)
        check_parameter(TIME_KEY, config_file)
        check_parameter(FILTER_KEY, config_file, [])
        check_parameter(ACCOUNT_SID_KEY, config_file)
        check_parameter(AUTH_TOKEN_KEY, config_file)
        check_parameter(FROM_KEY, config_file)
        check_parameter(CACHE_KEY, config_file)
        logger.debug('final config:')
        logger.debug(config_file)

        last_obj = None
        cache = config_file[CACHE_KEY]
        logger.debug('using cache: %s' % cache)
        if os.path.exists(cache):
            with open(cache, 'r') as cache_file:
                last_obj = json.loads(cache_file.read())
                logger.debug('reading cache in, object: ')
                logger.debug(last_obj)

        results = process_file(logger, bytes, last_obj, config_file)
        results.sort(key=lambda x: x[OBJECT_TIME], reverse=True)
        messages = []
        latest_message = None
        for item in results:
            if latest_message is None:
                latest_message = item

            logger.debug(item)
            message_text = item[OBJECT_MESSAGE]
            logger.warn(message_text)
            messages.append(message_text)

        if len(messages) > 0:
            dry_run = args.dryrun
            locking = LOCK_KEY in config_file
            lock_file = None
            if locking:
                lock_file = config_file[LOCK_KEY]
                if not os.path.exists(lock_file):
                    logger.info('creating lock file %s' % lock_file)
                    # Creating the file if it doesn't exist
                    with open(lock_file, 'w+') as fd:
                        fd.write('')
            try:
                file_locking(logger, locking, lock_file, True)

                # Critical section for messaging outputs
                if not send_message(logger, messages, config_file, dry_run):
                    # Prevent writing out the 'latest' if this doesn't work
                    raise Exception("unable to report message out")
            finally:
                file_locking(logger, locking, lock_file, False)

        if latest_message is not None:
            logger.info('new message detected')
            logger.debug(latest_message)
            with open(cache, 'w') as cache_write:
                cache_write.write(json.dumps(latest_message))

        exit_code = 0
    except Exception as e:
        # Non-zero exit and make sure to output everything
        print(e)
        logger.error(e)
    logger.info('done')
    exit(exit_code)

if __name__ == "__main__":
    main()
