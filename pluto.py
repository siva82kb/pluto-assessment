
"""
Main script file for the PLUTO assessment program.

Author: Sivakumar Balasubramanian, CMC Vellore
Date: 12 July 2024
"""

import serial
import sys
import struct

# Read byte
read_byte = lambda ser: int.from_bytes(ser.read(), byteorder='big')

# Connect to the selected COM port
ser = serial.Serial("COM5")

# Main loop
pcktcount = 0
while True:
    print(read_byte(ser))
    # if read_byte(ser) == 255 and read_byte(ser) == 255:
    #     pcktcount += 1
    #     data_length = read_byte(ser)
    #     data = [_d for _d in ser.read(data_length)]
    #     # Unpack the data
    #     status = data[0]
    #     error = 255 * data[2] + data[1]
    #     actuated = data[3]
    #     # Unpack the next 20 bytes into 5 floats
    #     rdata = [struct.unpack('f', bytes(data[i:i+4]))[0] for i in range(4, 24, 4)]
    #     # Checksum verification
    #     _chksum = (255 + 255 + data_length + sum(data[:24])) % 256
    #     if _chksum == data[24]:
    #         sys.stdout.write(f"\nFound new data ({pcktcount:6d}): Angle: {rdata[0]:0.1f}")
            
    # else:
    #     sys.stdout.write(f"\rWaiting for data({pcktcount:6d})")
        # checksum = read_byte(ser)
        # if sum(data) % 256 == checksum:
        #     print(data)
        # else:
        #     print("Checksum error")
    #     # Read the data length
    #     data_length = ser.read()
    #     # Read the data
    #     data = ser.read(data_length)
    #     # Read the checksum
    #     checksum = ser.read()
    #     # Check if the checksum is correct
    #     if sum(data) % 256 == checksum:
    #         # Process the data
    #         print(data)
    #     else:
    #         print("Checksum error")
    # else:
    #     sys.stdout.write("\rWaiting for data")
    