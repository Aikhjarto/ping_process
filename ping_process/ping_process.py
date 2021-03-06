"""
Python 3 module to help processing long running pings.

Usage
-----
ping -D 8.8.8.8 | python3 ping_process.py

To store also raw data:
ping -D 8.8.8.8 | tee -a raw.log | python3 ping_process.py

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
        self.time_string = ""

        self.last_seq = -1
        self.allowed_seq_diff = allowed_seq_diff

    def process(self, line):
        """
        Process a line of the output of `ping -D x.x.x.x` 

        Parameters
        ----------
        line : str
            String denoting one line of the output of ping.

        Returns
        -------
        ret : int
            -1 for unparseable line
            1 if no time=xx.x tag is in line

        Notes
        -----
        Typical output of `ping -D` looks like
        ```
        PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
        [1597166438.798339] 64 bytes from 8.8.8.8: icmp_seq=1 ttl=118 time=14.2 ms
        [1597166439.798003] 64 bytes from 8.8.8.8: icmp_seq=2 ttl=118 time=13.8 ms
        [1597245144.447473] 64 bytes from 8.8.8.8: icmp_seq=877 ttl=118 time=244 ms (DUP!)
        [1597411489.934841] From x.x.x.x icmp_seq=14 Packet filtered
        [1597500391.382726] From x.x.x.x icmp_seq=13317 Destination Host Unreachable

        ```
        """

        # store line without newline
        self.last_line = line.rstrip()

        a = line.split(" ")
        if len(a) == 8:
            # ordinary ping message has 8 fields. '-D' adds the timestamp as prefix.
            raise RuntimeError(
                "Got 8 columns. Maybe you missed -D " 'when calling "ping -D x.x.x.x"'
            )

        if a[0] != "PING":
            # header line (starting with PING) is of no interest

            # check for valid timestamp
            try:
                # strip square brackets from timestamp
                timestamp = float(a[0][1:-2])
                
                # convert time when ping was sent in a human readable format
                self.time_string = datetime.fromtimestamp(timestamp).strftime(
                    self.datetime_fmt_string
                )
            except ValueError as ex:
                print('Unparseable timestamp:', self.last_line)
                print('Unparseable timestamp:', self.last_line, file=sys.stderr)
                
                # store time when stdout was written for next heartbeat
                self.last_timestamp = timestamp
                
                return -1

            # check for sequence number and roundtrip time
            try:
                # get sequence number
                seq = int(a[5][9:])

                # get roundtrip time
                rt_time = float(a[7][5:])  # strip "time=" from "time=xx.x"

            except ValueError as ex:
                # No parseable time=xx.x tag, thus assume an error and report it
                print(f"{self.time_string} {self.last_line}")
                
                # store time when stdout was written for next heartbeat
                self.last_timestamp = timestamp
                
                return 1

            # log too long roundtrip time or unusual suffix
            if rt_time > self.max_time_ms or len(a)>9:
                # len(a)>9 if suffix like (DUP!) was appended

                print(f"{self.time_string} {self.last_line}")

                # store time when stdout was written for next heartbeat
                self.last_timestamp = timestamp

            # check sequence number increment (wraps to 0 after 65535)
            if self.last_seq != -1 and seq > (self.last_seq + self.allowed_seq_diff) % 65536:
                # missed a ping
                print(f"{self.time_string} Missed icmp_seq={self.last_seq}:{seq} ({seq-self.last_seq} packets)")
                
                # store time when stdout was written for next heartbeat
                self.last_timestamp = timestamp

            # heartbeat message if nothing else happend
            if (
                self.last_timestamp
                and self.heartbeat_interval > 0
                and timestamp - self.last_timestamp > self.heartbeat_interval
            ):
                print(
                    f"No anomalies found in the last {self.heartbeat_interval} s. "
                    f"Last input was at {self.time_string}",
                    file=self.heartbeat_pipe,
                )
                self.last_timestamp = time.time()

            self.last_seq=seq

            return 0

    def print_status(self):
        """
        Callback for USR1 signal to print status to stderr.
        """
        print(f'Last line at {self.time_string}: "{self.last_line}"', file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser(description="Reads data from 'ping -D' and forwards only interesting lines.",
            epilog="Example usage: ping -D x.x.x.x | python3 ping_process.py"  )

    parser.add_argument("--max-time-ms", "-t", type=float, default=500, metavar="T",
            help="Roundtrip times exceeding T will be logged. Default %(default)s")

    parser.add_argument("--fmt", type=str, default="%Y-%m-%d %H:%M:%S",
            help=r"Format for the human readable timestamp passed to the 'datetime' module. "
            "Default: '%(default)s'")
    parser.add_argument("--heartbeat-interval", type=float, default=0, metavar="H",
            help="If H is greater than 0 and no output was produced within H seconds"
            "a status message indicating that this script is still alive will be printed." )

    parser.add_argument("--allowed-seq-diff", type=int, default=1, metavar="N",
            help="If N or more sequence numbers are missing, a corresponding "
            "line will be printed. Default: %(default)s")

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
