import sys
from PyQt5.QtWidgets import QApplication
from qtjedi import JediComm

from qtpluto import QtPluto

app = QApplication(sys.argv)
pluto = QtPluto(port="COM13")
pluto.stop_sensorstream()
pluto.get_version()
pluto.send_heartbeat()
pluto.start_sensorstream()
app.exec_()