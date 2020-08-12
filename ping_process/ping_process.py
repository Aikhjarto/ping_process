"""
Python 3 module to help processing long running pings.

Usage
-----
ping -D 8.8.8.8 | python3 ping_process.py

To store also raw data:
ping -D 8.8.8.8 | tee raw.log | python3 ping_process.py

When USR1 signal is received, status is printed to stderr.

"""

from datetime import datetime
import fileinput
import signal
import sys
import time
import argparse


class PingDProcessor:
    """
    Class to check consecutive lines of the ouput of "ping -D x.x.x.x" for 
    anomalies. Anomal lines (too long roundtrip time or missing sqeuence 
    number) are printed to stdout prefixed with a human readable timestamp.

    Parameters
    ----------
    max_time_ms : float
        Round-trip time exceeding this value in ms will be logged to stdout.

    datetime_fmt_string : str, optional
        If given, it overrides the default format string "%Y-%m-%d %H:%M:%S".

    heartbeat_interval : float, optional
        If given and greater than zero, a heartbeat message is sent to stdout
        when nothing was logged to stdout within the last 'heartbeat_intveral'
        seconds.

    heartbeat_pipe : object
        To not gobble out output, heartbeat can be redirected.
        `heartbeat_pipe` is used as 'file=' argument to print().

    allowed_seq_diff : int
        If icmp_seq differs more more than `allowed_seq_diff` from one line to
        the next, the incident is logged. Default: 1, i.e. every missed ping
        is logged.
    """

    def __init__(
        self,
        max_time_ms=1000,
        datetime_fmt_string=None,
        heartbeat_interval=0,
        heartbeat_pipe=None,
        allowed_seq_diff=1
    ):

        self.max_time_ms = max_time_ms

        self.datetime_fmt_string = (
            "%Y-%m-%d %H:%M:%S" if datetime_fmt_string is None else datetime_fmt_string
        )

        # heartbeat
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_pipe = heartbeat_pipe
        self.last_timestamp = time.time()

        # last line for status output
        self.last_line = ""
        self.last_timestring = ""

        self.last_seq = -1
        self.allowed_seq_diff = allowed_seq_diff

    def process(self, line):
        """
        Process a line of the output of `ping -D x.x.x.x` 

        Parameters
        ----------
        line : str
            String denoting one line of the output of ping.

        Notes
        -----
        Typical output of `ping -D` looks like
        ```
        PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
        [1597166438.798339] 64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=14.2 ms
        [1597166439.798003] 64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=13.8 ms
        [1597245144.447473] 64 bytes from 8.8.8.8: icmp_seq=877 ttl=118 time=244 ms (DUP!)
        ```
        """

        # store line without newline
        self.last_line = line.rstrip()

        a = line.split(" ")
        if len(a) == 8:
            raise RuntimeError(
                "Got 8 columns. Maybe you missed -D " 'when calling "ping -D x.x.x.x"'
            )

        if a[0] != "PING":
            # header line (starting with PING) is of no interest

            try:
                # strip square brackets from timestamp
                timestamp = float(a[0][1:-2])

                # get sequence number
                seq = int(a[5][9:])

                # get roundtrip time
                rt_time = float(a[7][5:])  # strip "time=" from "time=xx.x"

                # convert time when ping was sent in a human readable format
                time_string = datetime.fromtimestamp(timestamp).strftime(
                    self.datetime_fmt_string
                )
            except ValueError as ex:
                print('Unparseable line:', line)
                print('Unparseable line:', line, file=sys.stderr)
                raise ex

            self.last_timestring = time_string

            # log too long roundtrip time
            if rt_time > self.max_time_ms or len(a)>9:
                # len(a)>0 if suffix like (DUP!) was appended

                print(f"{time_string} {self.last_line}")

                # store time when stdout was written for next heartbeat
                self.last_timestamp = timestamp

            # check is sequence number increment is one
            if self.last_seq != -1 and seq - self.allowed_seq_diff != self.last_seq:
                # missed a ping
                print(f"{time_string} Missed icmp_seq={self.last_seq}:{seq}")
                self.last_timestamp = timestamp


            if (
                self.last_timestamp
                and self.heartbeat_interval > 0
                and timestamp - self.last_timestamp > self.heartbeat_interval
            ):
                print(
                    f"No anomalies found in the last {self.heartbeat_interval} s. "
                    f"Last input was at {self.last_timestring}",
                    file=self.heartbeat_pipe,
                )
                self.last_timestamp = time.time()

            self.last_seq=seq

    def print_status(self):
        """
        Callback for USR1 signal to print status to stderr.
        """
        print(f'Last line at {self.last_timestring}: "{self.last_line}"', file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument("--max-time-ms", "-t", type=float, default=500, metavar="T")

    parser.add_argument("--fmt", type=str, default="%Y-%m-%d %H:%M:%S")
    parser.add_argument("--heartbeat-interval", type=float, default=0)

    parser.add_argument("--allowed-seq-diff", type=int, default=1)

    args = parser.parse_args()

    return args


if __name__ == "__main__":

    args = parse_args()

    if sys.stdin.isatty():
        raise RuntimeError(
            "This script is supposed to read from " "a pipe and not from user input."
        )

    p = PingDProcessor(
        max_time_ms=args.max_time_ms,
        datetime_fmt_string=args.fmt,
        heartbeat_interval=args.heartbeat_interval,
        allowed_seq_diff=args.allowed_seq_diff
    )

    # callback for USR1
    signal.signal(signal.SIGUSR1, lambda sig, frame: p.print_status())

    # read from stdin and pass to PingDProcessor
    for line in fileinput.input("-"):
        p.process(line)
