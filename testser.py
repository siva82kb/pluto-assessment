import serial

ser = serial.Serial("COM13", 115200, timeout=0.1)

while True:
    if ser.in_waiting:
        data = ser.read(ser.in_waiting)
        print("Data:", data)