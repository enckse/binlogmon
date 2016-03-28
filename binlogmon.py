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

VERSION_NUMBER = "0.3.0"

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
BLACKLIST_KEY = 'blacklist'
WHITELIST_KEY = 'whitelist'
CACHE_KEY = 'cache'
LOCK_KEY = 'lock'
SHARED_KEY = 'shared'
OVERRIDE_KEY = 'override'

TWILIO_SECTION = 'twilio'
TO_KEY = 'to'
CALL_KEY = 'call'
CALL_URL_KEY = 'url'
SMS_TO_KEY = 'sms'
LONG_MESSAGE_KEY = 'long'
ACCOUNT_SID_KEY = 'sid'
AUTH_TOKEN_KEY = 'token'
FROM_KEY = 'from'
SMS_MESSAGE_KEY = "message"

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
OUT_DATE = '%Y-%m-%dT%H:%M:%S'
FILE_CHUNKSIZE = 8192
LOG_LEVEL = logging.INFO
MAX_ITEM_FAILURES = 100


def process_file(logger, file_bytes, cache_object, configuration):
    """
    Process the binary log file bytes.

    Perform the actual reading of the file bytes and conversion
    to an output message set.
    """
    offset = 0
    last_reported = []
    filters = []
    has_whitelist = False
    start_date = datetime.datetime.strptime(configuration[START_KEY],
                                            DATE_FORMAT)
    chunking = configuration[SIZE_KEY]
    pattern = configuration[PATTERN_KEY]
    message_idx = configuration[MESSAGE_KEY]
    time_idx = configuration[TIME_KEY]

    def _filter_setup(is_whitelist, entry, filter_set):
        logger.debug("filter {0} (whitelist: {1})".format(entry, is_whitelist))
        compiled = re.compile(entry)
        filter_set.append((is_whitelist, compiled))

    # Whitelist applied first, blacklist second (so whitelist _can_ be initial)
    for item in configuration[WHITELIST_KEY]:
        has_whitelist = True
        _filter_setup(True, item, filters)

    for item in configuration[BLACKLIST_KEY]:
        _filter_setup(False, item, filters)

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

        whitelist_matches = 0
        blacklist_matches = 0
        for item in filters:
            regex = item[1]
            is_whitelisted = item[0]
            result = regex.match(raw_message)
            was_match = result is not None
            logger.debug('{0} match {1}? {2} (wl: {3})'.format(regex,
                                                               raw_message,
                                                               was_match,
                                                               is_whitelisted))

            if is_whitelisted:
                if was_match:
                    whitelist_matches += 1
            else:
                if was_match:
                    blacklist_matches += 1

        blacklisted = blacklist_matches > 0
        whitelisted = True
        if has_whitelist:
            whitelisted = whitelist_matches > 0

        do_output = whitelisted
        if do_output:
            do_output = not blacklisted

        logger.debug('{0} will be output ? {1}'.format(raw_message, do_output))
        if do_output:
            obj = {}
            seconds = unpacked[time_idx]
            display_time = start_date + datetime.timedelta(seconds=seconds)

            # We can just sort and use the seconds offset
            # (even if it is abritrary because it still only counts up)
            obj[OBJECT_TIME] = seconds
            obj[OBJECT_MESSAGE] = raw_message

            # This is for actual troubleshooting/helping us
            # to provide the ability to see 'when' something actually happened
            obj[OBJECT_VIS_TIME] = str(display_time)

            if cache_time is None or obj[OBJECT_TIME] > cache_time:
                logger.debug(obj)
                last_reported.append(obj)
        offset += chunking
    return last_reported


class Message(object):
    """Base implementation for sending messages out."""

    def __init__(self):
        """Initialize the instance."""
        self.method = None
        self.logger = None

    def initialize(self, message_list, config, logger):
        """
        Initialize the message from the configuration.

        message_list - new messages from the binary input file
        config - the configuration definition
        logger - the logger object
        """
        raise Exception("base class can _NOT_ be initialized")

    def get_output_calls(self):
        """Get the output calls to make to send messages outward."""
        raise Exception("base class has _NO_ outputs")


class TwilioMessage(Message):
    """Twilio-backed messaging."""

    def __init__(self):
        """Initialize the instance."""
        self.sid = None
        self.token = None
        self.from_number = None
        self.to_numbers = None
        self.client = None

    def _init(self, config, logger):
        """Initialize the common Twilio settings."""
        self.logger = logger
        # Account sid (the account's sid on the dash/overall page)
        self.sid = config[ACCOUNT_SID_KEY]
        # Auth token (the account's auth token on the dash/overall page)
        self.token = config[AUTH_TOKEN_KEY]
        # NOTE: numbers must be 'verified'
        self.from_number = config[FROM_KEY]
        self._check_parameter(self.method, config)
        use_config = config[self.method]
        to_values = use_config[TO_KEY]
        self.to_numbers = set(to_values)
        if len(self.to_numbers) != to_values:
            logger.warn("duplicate numbers for messaging")
        self.client = None
        return use_config

    def get_output_calls(self):
        """Inherited from base."""
        self.logger.info('sending messages from %s' % self.from_number)
        for item in self.to_numbers:
            def call(dry_run, obj, send_to):
                """Perform the 'output' of messages (via twilio)."""
                if dry_run:
                    self._dry_run_message(send_to)
                else:
                    if self.client is None:
                        import twilio
                        import twilio.rest
                        self.client = twilio.rest.TwilioRestClient(self.sid,
                                                                   self.token)
                    result = obj._execute(self.client, send_to)
                    self.logger.debug(result.sid)
                    time.sleep(1)

            yield (item, self.method, call, self)

    def _execute(self, client, item):
        raise Exception("base twilio _MOST_ support execute")

    def _dry_run_message(self, to_number):
        dry_run_msg = self._get_dry_run_message()
        debug_message = 'from: {0}, to: {1}, ({2})'.format(self.from_number,
                                                           to_number,
                                                           dry_run_msg)
        self.logger.debug(debug_message)
        print(debug_message)

    def _get_dry_run_message(self):
        raise Exception("base twilio _MUST_ support dry-run")

    def _check_parameter(self, parameter, config):
        """Check a parameter for twilio subsection."""
        check_parameter(parameter, config, subsections=[TWILIO_SECTION,
                                                        self.method])


class TwilioCall(TwilioMessage):
    """Twilio phone calls."""

    def __init__(self):
        """Initialize the instance."""
        self.call_url = None

    def initialize(self, message_list, config, logger):
        """Inherited from base."""
        self.method = CALL_KEY
        use_config = self._init(config, logger)
        self._check_parameter(CALL_URL_KEY, use_config)
        self.call_url = use_config[CALL_URL_KEY]
        self.logger.debug('using url: %s' % self.call_url)

    def _execute(self, client, item):
        """Inherited from base."""
        call_object = client.calls.create(
            to=item,
            from_=self.from_number,
            url=self.call_url
        )

        return call_object

    def _get_dry_run_message(self):
        """Inherited from base."""
        return self.call_url


class TwilioSMS(TwilioMessage):
    """Twilio SMS."""

    def __init__(self):
        """Initialize the instance."""
        self.short_message = None

    def initialize(self, message_list, config, logger):
        """Inherited from base."""
        self.method = SMS_TO_KEY
        use_config = self._init(config, logger)
        self._check_parameter(SMS_MESSAGE_KEY, use_config)
        self._check_parameter(LONG_MESSAGE_KEY, use_config)
        long_message = use_config[LONG_MESSAGE_KEY]
        message_text = use_config[SMS_MESSAGE_KEY]
        self.short_message = TwilioSMS._format_message(message_text,
                                                       long_message,
                                                       message_list)
        self.logger.warn(self.short_message)

    def _format_message(message, long_message, message_list):
        """Format the SMS message."""
        replaces = {}
        replaces["{datetime}"] = datetime.datetime.now().strftime(OUT_DATE)
        replaces["{first}"] = message_list[0][0:SMS_LENGTH]
        long_text = ""
        if len(message_list) > 1:
            replaces["{remaining}"] = str(len(message_list) - 1)
            long_text = TwilioSMS._format_message_part(long_message, replaces)
        replaces["{long}"] = long_text
        return TwilioSMS._format_message_part(message, replaces)

    def _format_message_part(message, replaces):
        """Format a single message part for an SMS."""
        resulting = message
        for item in replaces:
            resulting = resulting.replace(item, replaces[item])
        return resulting

    def _execute(self, client, item):
        """Inherited from base."""
        message_object = client.messages.create(
            body=self.short_message,
            to=item,
            from_=self.from_number
        )

        return message_object

    def _get_dry_run_message(self):
        """Inherited from base."""
        return self.short_message


def send_message(logger, message_list, config, dry_run):
    """
    Send any applicable messages.

    Uses the configured API to send out messages for any new messages read
    from the binary log file.
    """
    queued = []
    raw_methods = []
    valid_method = False
    if TWILIO_SECTION in config:
        subsection = config[TWILIO_SECTION]
        if SMS_TO_KEY in subsection:
            valid_method = True
            raw_methods.append((subsection, TwilioSMS))

        if CALL_KEY in subsection:
            valid_method = True
            raw_methods.append((subsection, TwilioCall))

    if not valid_method:
        raise Exception("Not configured to message anyone...")

    queued = []
    for raw in raw_methods:
        method = raw[1]()
        config_to_use = raw[0]
        method.initialize(message_list, config_to_use, logger)
        for item in method.get_output_calls():
            queued.append(item)

    messaging_queue = deque(queued)
    failures = {}
    while len(messaging_queue) > 0:
        current_object = messaging_queue.popleft()
        item = current_object[0]
        function = current_object[1]
        callback = current_object[2]
        obj = current_object[3]
        try:
            logger.info("{0} to {1}".format(function, item))
            callback(dry_run, obj, item)
        except Exception as e:
            logger.warn('unable to send message to %s' % item)
            logger.error(e)
            messaging_queue.append(current_object)
            fail_key = "{0} ({1})".format(item, function)
            if fail_key not in failures:
                failures[fail_key] = 0
            failures[fail_key] += 1
            if failures[fail_key] > MAX_ITEM_FAILURES:
                logger.error("max failures reached {0}".format(fail_key))
                return False

    logger.info('messages sent')
    return True


def check_parameter(key, configuration, default=None, subsections=None):
    """
    Check for parameters.

    Check if a parameter is set.
    If it isn't and there is a default - use default
    else
    that's a problem.
    """
    if key not in configuration:
        if default is None:
            message = "missing required configuration item: %s" % key
            if subsections is not None and len(subsections) > 0:
                subsection = ".".join(subsections)
                message = "{0} (section: {1})".format(message, subsection)
            raise Exception(message)
        else:
            configuration[key] = default


def overriding(shared, config, override, logger):
    """Config overriding."""
    for key, value in shared.items():
        if key == SHARED_KEY:
            logger.warn("Nested config sharing is not supported")
            continue

        if isinstance(value, dict) and key in config:
            config[key] = overriding(value, config[key], override, logger)
        else:
            if key in config:
                logger.warn('%s has multiple values' % key)
                if override:
                    logger.warn("using child")
                    continue
                else:
                    logger.warn("using parent")
            config[key] = value
    return config


def main():
    """
    Main entry point.

    Handle logging, argument parsing, and general orchestration.
    """
    logger = logging.getLogger('binlogmon')
    logger.setLevel(LOG_LEVEL)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
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
        parser.add_argument('--log',
                            help='log file',
                            default='binlogmon.log')
        parser.add_argument('--version',
                            action='version',
                            version='%(prog)s {0}'.format(VERSION_NUMBER))

        args = parser.parse_args()
        handler = logging.handlers.RotatingFileHandler(args.log,
                                                       maxBytes=10*1024*1024,
                                                       backupCount=10)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
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
            shared_value = config_file[SHARED_KEY]
            logger.debug('loading shared config')
            if len(shared_value) > 0:
                with open(shared_value, 'r') as f:
                    shared_config = json.loads(f.read())
                    logger.debug(shared_config)
                    do_override = True
                    if OVERRIDE_KEY in config_file:
                        do_override = config_file[OVERRIDE_KEY]

                    # Replay this 'over' the given, it overrides
                    config_file = overriding(shared_config,
                                             config_file,
                                             do_override,
                                             logger)

        check_parameter(SIZE_KEY, config_file)
        check_parameter(START_KEY, config_file, '1970-01-01 00:00:00')
        check_parameter(PATTERN_KEY, config_file)
        check_parameter(MESSAGE_KEY, config_file)
        check_parameter(TIME_KEY, config_file)
        check_parameter(CACHE_KEY, config_file)
        check_parameter(WHITELIST_KEY, config_file, [])
        check_parameter(BLACKLIST_KEY, config_file, [])
        logger.debug('final config:')
        logger.debug(config_file)

        last_obj = None
        cache = config_file[CACHE_KEY]
        logger.debug('using cache: %s' % cache)
        if os.path.exists(cache):
            with open(cache, 'r') as cache_file:
                last_obj = json.loads(cache_file.read())
                logger.info('reading cache in, object: ')
                logger.info(last_obj)

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

            fd = None
            try:
                if locking:
                    logger.debug('performing lock operation')
                    fd = open(lock_file, 'w')
                    fcntl.lockf(fd.fileno(), fcntl.LOCK_EX)

                # Critical section for messaging outputs
                if not send_message(logger, messages, config_file, dry_run):
                    # Prevent writing out the 'latest' if this doesn't work
                    raise Exception("unable to report message out")
            finally:
                if locking and fd is not None:
                    logger.debug('unlocking...')
                    fcntl.lockf(fd.fileno(), fcntl.LOCK_UN)
                    fd.close()

        if latest_message is not None:
            logger.info('new message detected')
            last_json = json.dumps(latest_message)
            logger.info(last_json)
            with open(cache, 'w') as cache_write:
                cache_write.write(last_json)

        exit_code = 0
    except Exception as e:
        # Non-zero exit and make sure to output everything
        print(e)
        logger.error(e)
    logger.info('done')
    exit(exit_code)

if __name__ == "__main__":
    main()
