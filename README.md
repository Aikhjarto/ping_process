Python 3 module to help processing long running pings.

# Usage
``` 
ping -D 8.8.8.8 | python3 ping_process.py
```

To store also raw data:
```
ping -D 8.8.8.8 | tee raw.log | python3 ping_process.py
```

When USR1 signal is received, status is printed to stderr.


