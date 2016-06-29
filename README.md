binlogmon
=========
Monitor and send messages out when new entries are written to a binary log file. It requires 2 major components in the binary file to be useful:

1. A message (to send)

2. A counter that only counts up

[![Build Status](https://travis-ci.org/epiphyte/binlogmon.svg?branch=master)](https://travis-ci.org/epiphyte/binlogmon)

# Install
* Clone this repository and run something to one of the following depending on system configuration:
```
python setup.py install
```
or
```
pip install .
```
or
```
pip install -e .
```

# Usage

```
binlogmon -f /path/to/binary/log/file.log --config /path/to/config.json
```

# Config
An example config file "example.json" is in the root, the breakdown is below

## Config (detail)

* Location to store the last detected/read message
```
    "cache":"/path/to/cache/last/detected/last.json"
```

* The time offset (for debug/testing) in the format "YYYY-MM-DD HH:mm:SS"
```
    "start":"2015-12-10 12:15:30"
```

* Binary file message size
```
    "size":1024
```

* Struct (python) pattern to use to unpack the binary message, it _HAS_ to produce 2 items: a message (text) and a time offset (counting up)
```
    "pattern": "<5sxi"
```

* Location, from the pattern, the message text comes from
```
    "message":0,
```

* Location, from the pattern, the time offset comes from
```
    "time":1
```

* Whitelist of regular expressions that a message must match to be included (optional)
```
    "whitelist":[],
```

* Blacklist of regular expressions that will prevent messages from being included (optional)
```
    "blacklist":["test"],
```

* Path to a file that can be used as an exclusive lock (for multiple instances running)
```
    "lock": "/path/to/file/to/lock"
```

* Ability to use a common set of account information/numbers/etc. between multiple instances (optional)
```
    "shared": "/path/to/a/shared/config.json"
```

* Control whether to use a shared config's value (parent) or not (child) - true for child
```
    "override": false
```

* Any message filters to apply
```
    "filters":["test"]
```

### Twilio subsection

* The 'twilio' subsection is for messaging via twilio (call/sms/etc.)
```
{
    "twilio":
    {
        ...
    }
    ...
}
```

* Twilio account sid
```
    "sid": "twilio-sid"
```

* Twilio auth token
```
    "token": "twilio-auth-token",
```

* The 'sms' or 'call' sections require a 'to' for who to message to under each one (may want to SMS one number and call another)
```
    "to": ["number1", "number2"],
```

* Phone number (from Twilio) to message from
```
    "from": "from-number"
```

#### SMS subsection (twilio)

* The 'sms' section is for sending SMS messages (via Twilio here)
```
{
    "twilio":
    {
        ...
        "sms":
        {
            ...
        }
    }
    ...
}
```

* Message text to use when sending a message (will be formatted with placeholders)
```
    "message": "{datetime} - {first}{long}"
```

* Message text to use when more than 1 new message is detected (when using 'sms')
```
    "long":" (and {remaining} more messages)"
```

#### Call subsection (twilio)
* The 'call' section is for calling numbers (via Twilio here)
```
{
    "twilio":
    {
        ...
        "call":
        {
            ...
        }
    }
    ...
}
```

* TwiML valid URL to pass for making the call (when using 'call')
```
    "url": "http://some/valid/twiml/url"
```

# Wrapper

* Example wrapper to manage and use the logging monitor, assuming:
    * Setup has been run and binlogmon is in $PATH
    * $NAME and $LOG_FILES are set
    * Operating under a 'system' account in $PWD
    * The config is called 'config-$NAME.json' in the named location
    * Logging will be done to a log-$NAME.log file
