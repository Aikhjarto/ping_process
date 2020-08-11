Python 3 module to help processing long running pings.

It will read the output of `ping -D x.x.x.x` and forwards only those
replies that have a (configurable) roundtrip time of more than 500 ms.

# Usage
``` 
ping -D 8.8.8.8 | python3 ping_process.py
```

To store also raw data:
```
ping -D 8.8.8.8 | tee raw.log | python3 ping_process.py
```

Show CLI options
```
python3 ping_process.py
```

When USR1 signal is received, status is printed to stderr.


