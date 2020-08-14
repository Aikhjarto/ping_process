Python 3 module to help processing long running pings on Linux system.

It will read the output of `ping -D x.x.x.x` and forward only those
replies that have a (configurable) roundtrip time of more than 500 ms,
a missing sequence number or contain an error message.
Forwarded messages will be prefixed with a human-readable timestamp.

Other systems are not supported since the output of `ping` differs.

# Usage
```shell
ping -D 8.8.8.8 | python3 ping_process.py
```

Use `tee` to store also raw data,
```shell
ping -D 8.8.8.8 | tee raw.log | python3 ping_process.py
```
or duplicate output to file
```shell
ping -D 8.8.8.8 | python3 ping_process.py | tee interesting.log
```

## Show CLI options
```shell
python3 ping_process.py -h
```
```shell
usage: ping_process.py [-h] [--max-time-ms T] [--fmt FMT]
                       [--heartbeat-interval HEARTBEAT_INTERVAL]
                       [--allowed-seq-diff ALLOWED_SEQ_DIFF]

optional arguments:
  -h, --help            show this help message and exit
  --max-time-ms T, -t T
  --fmt FMT
  --heartbeat-interval HEARTBEAT_INTERVAL
  --allowed-seq-diff ALLOWED_SEQ_DIFF
```

## Show current status
When USR1 signal is received, current status is printed to `stderr`.

