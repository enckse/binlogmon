#!/usb/bin/python
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
from collections import deque

VERSION_NUMBER="0.1.0"

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
SMS_FROM_KEY = 'from'
CACHE_KEY = 'cache'
LONG_MESSAGE_KEY = 'long'

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
FILE_CHUNKSIZE = 8192
LOG_LEVEL = logging.INFO

def process_file(logger, file_bytes, cache_object, configuration):
    offset = 0
    last_reported = []
    filters = []
    start_date = datetime.datetime.strptime(configuration[START_KEY], DATE_FORMAT)
    chunking = configuration[SIZE_KEY]
    pattern = configuration[PATTERN_KEY]
    message_idx = configuration[MESSAGE_KEY]
    time_idx = configuration[TIME_KEY]    
    for item in configuration[FILTER_KEY]:
        filters.append(re.compile(item))
    
    while offset < len(file_bytes):
        all_bytes = file_bytes[0 + offset: chunking + offset]
        unpacked = struct.unpack(pattern, array.array('B', all_bytes).tostring())
        
        # expects ascii here
        raw_message = array.array('B', [x for x in unpacked[message_idx] if x != 0]).tostring().decode('ascii')
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
            
            # This is for actual troubleshooting/helping us know 'when' something happened
            obj[OBJECT_VIS_TIME] = str(time)
            
            if cache_object is None or obj[OBJECT_TIME] > cache_object[OBJECT_TIME]:
                last_reported.append(obj)
        offset += chunking
    return last_reported

def send_text(logger, message, config, dry_run):
    # Account sid (the account's sid on the dash/overall page)
    account_sid = config[ACCOUNT_SID_KEY]
    
    # Auth token (the account's auth token on the dash/overall page)
    auth_token  = config[AUTH_TOKEN_KEY]
    
    # phone numbers to send to (for trial/testing twilio account must be verified)
    sms_queue = deque(config[SMS_TO_KEY])
    
    # Must be the twilio number (setup via twilio)
    sms_from = config[SMS_FROM_KEY]
    
    logger.info('sending text messages')
    if not dry_run:
        import twilio
        import twilio.rest
        client = twilio.rest.TwilioRestClient(account_sid, auth_token)
    
    while len(sms_queue) > 0:
        item = sms_queue.popleft()
        try:
            logger.info("sending sms to %s" % item)
            
            if dry_run:
                logger.info('message sent')
                print('sending {0} to {1} from {2}'.format(message, item, sms_from))
            else:
                message_object = client.messages.create(
                    body=message,
                    to=item,
                    from_=sms_from
                )
                
                logger.info(message_object.sid)
            
            # throttle us otherwise twilio will
            if len(sms_queue) > 1:
                time.sleep(1)
        except Exception as e:
            logger.warn('unable to send message to %s' % item)
            logger.error(e)
            sms_queue.append(item)
    
    logger.info('messages sent')
    return True

def main():
    logger = logging.getLogger('binlogmon')
    logger.setLevel(LOG_LEVEL)
    handler = logging.handlers.RotatingFileHandler('binlogmon.log', maxBytes=10*1024*1024, backupCount=10)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    exit_code = -1
    try:
        parser = argparse.ArgumentParser(description='Parse and report any binary log messages.')
        parser.add_argument('-f', '--file', help='file name to read/parse/report from', required=True)
        parser.add_argument('--dry-run', help='run but do NOT send any messages', action='store_true', dest='dryrun')
        parser.add_argument('--config', help='configuration file', required=True)
        
        args = parser.parse_args()
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
            config_file = json.loads(f.read())
            logger.debug(config_file)
        
        last_obj = None
        cache = config_file[CACHE_KEY]
        logger.info('using cache: %s' % cache)
        if os.path.exists(cache):
            with open(cache, 'r') as cache_file:
                last_obj = json.loads(cache_file.read())
                logger.info('reading cache in, object: ')
                logger.debug(last_obj)
        
        results = process_file(logger, bytes, last_obj, config_file)
        results.sort(key=lambda x: x[OBJECT_TIME], reverse=True)
        new_messages = []
        latest_message = None
        for item in results:
            if latest_message is None:
                latest_message = item
            
            logger.debug(item)
            message_text = item[OBJECT_MESSAGE]
            logger.warn(message_text)
            new_messages.append(message_text)
        
        long_message = config_file[LONG_MESSAGE_KEY]
        if len(new_messages) > 0:
            output_message = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S') + " - "
            output_message += new_messages[0][0:SMS_LENGTH]
            if len(new_messages) > 1:
                output_message += long_message.format(len(new_messages) - 1)
       
            logger.warn(output_message)
            
            if not send_text(logger, output_message, config_file, args.dryrun):
                # Prevent writing out the 'latest' if this doesn't work
                raise Exception("unable to report message out")
        
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
