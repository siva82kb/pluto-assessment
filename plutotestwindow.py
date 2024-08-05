"""
Module for handling the operation of the PLUTO test window.

Author: Sivakumar Balasubramanian
Date: 04 August 2024
Email: siva82kb@gmail.com
"""


import sys
import numpy as np

from qtpluto import QtPluto
    
from PyQt5 import (
    QtCore,
    QtWidgets,)

import plutodefs as pdef
from ui_plutotestcontrol import Ui_PlutoTestControlWindow


class PlutoTestControlWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO test control window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, modal=False):
        """
        Constructor for the PTestControlViewWindow class.
        """
        super(PlutoTestControlWindow, self).__init__(parent)
        self.ui = Ui_PlutoTestControlWindow()
        self.ui.setupUi(self)
        if modal:
            self.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        
        # PLUTO device
        self._pluto = plutodev

        # Display counter
        self._dispcount = 0

        # Attach callbacks
        self.pluto.newdata.connect(self._callback_pluto_newdata)

        # Attach controls callback
        self.ui.radioNone.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioPosition.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioTorque.clicked.connect(self._callback_test_device_control_selected)
        self.ui.hSliderTgtValue.valueChanged.connect(self._callback_test_device_target_changed)

        # Update UI.
        self.update_ui()

    @property
    def pluto(self):
        return self._pluto
    
    #
    # Update UI
    #
    def update_ui(self):
        _nocontrol = not (self.ui.radioTorque.isChecked()
                          or self.ui.radioPosition.isChecked())
        self.ui.hSliderTgtValue.setEnabled(not _nocontrol)
        # Check the status of the radio buttons.
        if _nocontrol:
            self.ui.lblTargetValue.setText(f"No Control Selected")
        else:
            # Set the text based on the control selected.
            _str = "Target Value: "
            _ctrl = "TORQUE" if self.ui.radioTorque.isChecked() else "POSITION"
            _str += f"[{pdef.PlutoTargetRanges[_ctrl][0]:3.0f}, {pdef.PlutoTargetRanges[_ctrl][1]:3.0f}]"
            _str += f" {self._pos2tgt(self.ui.hSliderTgtValue.value()):-3.1f}Nm"
            self.ui.lblTargetValue.setText(_str)
    
    #
    # Signal Callbacks
    # 
    def _callback_pluto_newdata(self):
        pass

    #
    # Control Callbacks
    #
    def _callback_test_device_control_selected(self, event):
        # Check what has been selected.
        if self.ui.radioNone.isChecked():
            self.pluto.set_control("NONE", 0)
        elif self.ui.radioTorque.isChecked():
            self.pluto.set_control("TORQUE", 0)
            # Reset the target value
            self.ui.hSliderTgtValue.setValue(self._tgt2pos(0))
            # Now send the target value.
            self.pluto.set_control("TORQUE", 0)
        elif self.ui.radioPosition.isChecked():
            self.pluto.set_control("POSITION", 0)
            # Reset the target value
            self.ui.hSliderTgtValue.setValue(self._tgt2pos(self.pluto.angle))
            # Now send the target value.
            self.pluto.set_control("POSITION", self.pluto.angle)
        self.update_ui()

    def _callback_test_device_target_changed(self, event):
        # Get the current target position and send it to the device.
        _tgt = self._pos2tgt(self.ui.hSliderTgtValue.value())
        _ctrl = "TORQUE" if self.ui.radioTorque.isChecked() else "POSITION"
        self.pluto.set_control(_ctrl, _tgt)
        self.update_ui()

    #
    # Supporting functions
    #
    def _tgt2pos(self, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self.ui.radioTorque.isChecked()
                or self.ui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = (self.ui.hSliderTgtValue.minimum(),
                        self.ui.hSliderTgtValue.maximum())
        _ctrl = 'POSITION' if self.ui.radioPosition.isChecked() else 'TORQUE'
        _minv, _maxv = (pdef.PlutoTargetRanges[_ctrl][0],
                        pdef.PlutoTargetRanges[_ctrl][1])
        return int(_mins + (_maxs - _mins) * (value - _minv) / (_maxv - _minv))

    def _pos2tgt(self, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self.ui.radioTorque.isChecked()
                or self.ui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = (self.ui.hSliderTgtValue.minimum(),
                        self.ui.hSliderTgtValue.maximum())
        _ctrl = 'POSITION' if self.ui.radioPosition.isChecked() else 'TORQUE'
        _minv, _maxv = (pdef.PlutoTargetRanges[_ctrl][0],
                        pdef.PlutoTargetRanges[_ctrl][1])
        return _minv + (_maxv - _minv) * (value - _mins) / (_maxs - _mins)


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM5")
    pdataview = PlutoTestControlWindow(plutodev=plutodev)
    pdataview.show()
    sys.exit(app.exec_())
