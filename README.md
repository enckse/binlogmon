binlogmon
=========
Monitor and send SMS messages out when new entries are written to a binary log file. It requires 2 major components in the binary file to be useful:
1. A message (to send)
2. A counter that only counts up

# Config
The following config is an example of what to include in the config file passed via the CLI
```
{
    "cache":"/path/to/cache/last/detected/last.json",
    "start":"2015-12-10 12:15:30",
    "size":1024,
    "pattern": "<5sxi",
    "message":0,
    "time":1,
    "filters":["test"],
    "long":" (and {0} more messages)",
    "sid": "twilio-sid",
    "token": "twilio-auth-token",
    "sms": ["number1", "number2"],
    "from": "from-number"
}
```

## Config (detail)

* Location to store the last detected/read message
```
    "cache":"/path/to/cache/last/detected/last.json",
```

* The time offset (for debug/testing) in the format "YYYY-MM-DD HH:mm:SS"
```
    "start":"2015-12-10 12:15:30",
```

* Binary file message size
```
    "size":1024,
```

* Struct (python) pattern to use to unpack the binary message, it _HAS_ to produce 2 items: a message (text) and a time offset (counting up)
```
    "pattern": "<5sxi",
```

* Location, from the pattern, the message text comes from
```
    "message":0,
```

* Location, from the pattern, the time offset comes from
```
    "time":1,
```

* Any message filters to apply
```
    "filters":["test"],
```

* Message text to use when more than 1 new message is detected
```
    "long":" (and {0} more messages)"
```

* Twilio account sid
```
    "sid": "twilio-sid",
```

* Twilio auth token
```
    "token": "twilio-auth-token",
```

* Phone numbers to SMS
```
    "sms": ["number1", "number2"],
```

* Phone number (from Twilio) to message from
```
    "from": "from-number"
```
    
# Execution

```
python3 binlogmon.py -f /path/to/binary/log/file.log --config /path/to/config.json
```
