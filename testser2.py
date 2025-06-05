
from PyQt5 import QtWidgets
import sys

class CalibWindow(QtWidgets.QWidget):
    def __init__(self, on_close_callback=None):
        super().__init__()
        self.on_close_callback = on_close_callback

    def closeEvent(self, event):
        print("Close event triggered")
        if self.on_close_callback:
            self.on_close_callback()
        event.accept()

class Controller:
    def __init__(self):
        self._test = 0
        self._calibwnd = CalibWindow(on_close_callback=self._on_calib_window_closed)
        self._calibwnd.show()

    def _on_calib_window_closed(self):
        print("on_close_callback called")
        self._test += 1
        print("Test count:", self._test)

app = QtWidgets.QApplication(sys.argv)
controller = Controller()
sys.exit(app.exec_())
