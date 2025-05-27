"""
Module containing miscellaneous useful functions for the PLUTO full assessment protocol.

Author: Sivakumar Balasubramanian
Date: 16 May 2025
Email: siva82kb@gmail.com
"""

import time
import csv


def rangea_within_rangeb(rangea: tuple[float], rangeb: tuple[float]) -> bool:
    """
    Check if rangea is within rangeb.

    Args:
        rangea (tuple[float]): The first range (start, end).
        rangeb (tuple[float]): The second range (start, end).

    Returns:
        bool: True if rangea is within rangeb, False otherwise.
    """
    return rangea[0] >= rangeb[0] and rangea[1] <= rangeb[1]


#
# CSV Buffered Writer
#
class CSVBufferWriter(object):

    def __init__(self, fname, header, flush_interval=5.0, max_rows=1000):
        self._header = header
        self._fname = fname
        self._flush_interval = flush_interval
        self._max_rows = max_rows
        self._buffer = []
        self._fhandle = open(self._fname, "w", newline='')
        # Write the header.
        self._writer = csv.writer(self._fhandle)
        self._buffer.append(self._header)
        self.flush()
        self._lastflush = time.time()
    
    @property
    def filename(self):
        return self._fname

    def write_row(self, rowdata):
        # Ensure the length of rowdata matches the header.
        if len(rowdata) != len(self._header):
            raise ValueError("Row data length does not match header length.")
        self._buffer.append(rowdata)
        # Check if its time to flush.
        if ((time.time() - self._lastflush) > self._flush_interval 
            or len(self._buffer) >= self._max_rows):
            self.flush()

    def flush(self):
        if self._buffer:
            self._writer.writerows(self._buffer)
            self._buffer.clear()
            self._lastflush = time.time()

    def close(self):
        self.flush()
        self._fhandle.close()