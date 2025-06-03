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
from PyQt5.QtCore import QTimer

import plutodefs as pdef
from plutodataviewwindow import PlutoDataViewWindow
from ui_plutotestcontrol import Ui_PlutoTestControlWindow


class PlutoTestControlWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO test control window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, limb=None, mech=None, modal=False, 
                 dataviewer=False, onclosedb=None, heartbeat=False):
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
        self._limb = limb
        self._mech = mech

        # Heartbeat timer
        self._heartbeat = heartbeat
        if self._heartbeat:
            self.heartbeattimer = QTimer()
            self.heartbeattimer.timeout.connect(lambda: self.pluto.send_heartbeat())
            self.heartbeattimer.start(250)

        # Attach callbacks
        self._attach_pluto_callbacks()
        # self.pluto.newdata.connect(self._callback_pluto_newdata)

        # Attach controls callback
        self.ui.radioNone.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioPosition.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioTorque.clicked.connect(self._callback_test_device_control_selected)
        self.ui.hSliderTorqTgtValue.valueChanged.connect(self._callback_test_torque_target_changed)
        self.ui.hSliderPosTgtValue.valueChanged.connect(self._callback_test_position_target_changed)
        self.ui.hSliderCtrlBndValue.valueChanged.connect(self._callback_test_ctrlbnd_target_changed)
        self.ui.hSliderCtrlGainValue.valueChanged.connect(self._callback_test_ctrlgain_target_changed)

        # Update UI.
        self.update_ui()

        # Open the PLUTO data viewer window for sanity
        if dataviewer:
            # Open the device data viewer by default.
            self._open_devdata_viewer()

        # Close event callback
        self.on_close_callback = onclosedb

    @property
    def pluto(self):
        return self._pluto
    
    # Overriding the closeEvent method
    def closeEvent(self, event):
        # Run the callback
        if self.on_close_callback:
            self.on_close_callback()
        
        # Close the data viewer window if it is open.
        if hasattr(self, "_devdatawnd"):
            self._devdatawnd.close()
        
        # Disconnect the PLUTO callbacks.
        self._detach_pluto_callbacks()
        return super().closeEvent(event)

    #
    # Update UI
    #
    def update_ui(self):
        _nocontrol = not (self.ui.radioTorque.isChecked()
                          or self.ui.radioPosition.isChecked())
        # Enable/disable sliders
        self.ui.hSliderPosTgtValue.setEnabled(self.ui.radioPosition.isChecked())
        self.ui.hSliderTorqTgtValue.setEnabled(self.ui.radioTorque.isChecked())
        self.ui.hSliderCtrlBndValue.setEnabled(self.ui.radioPosition.isChecked())
        self.ui.hSliderCtrlGainValue.setEnabled(self.ui.radioPosition.isChecked())
        
        # Check the status of the radio buttons.
        if _nocontrol:
            self.ui.lblFeedforwardTorqueValue.setText("Feedforward Torque Value (Nm):")
            self.ui.lblPositionTargetValue.setText("Target Position Value (deg):")
            self.ui.lblControlBoundValue.setText("Control Bound Value:")
            self.ui.lblControlGainValue.setText("Control Gain Value:")
        else:
            # Desired torque
            _str = "Feedforward Torque Value (Nm) "
            _str += f"[{pdef.PlutoTargetRanges['TORQUE'][0]:3.0f}, {pdef.PlutoTargetRanges['TORQUE'][1]:3.0f}]:"
            slrrange, valrange = self.get_torque_slider_value_ranges()
            _val = self._pos2tgt(slrrange, valrange, self.ui.hSliderTorqTgtValue.value())
            _str += f" {_val:-3.1f}Nm"
            self.ui.lblFeedforwardTorqueValue.setText(_str)
            # Desired position
            # Set the text based on the control selected.
            _str = "Target Position Value (deg):"
            _str += f"[{pdef.PlutoTargetRanges['POSITION'][self._mech][0]:3.0f}, {pdef.PlutoTargetRanges['POSITION'][self._mech][1]:3.0f}]:"
            slrrange, valrange = self.get_position_slider_value_ranges()
            _val = self._pos2tgt(slrrange, valrange, self.ui.hSliderPosTgtValue.value())
            _str += f" {_val:-3.1f}deg"
            self.ui.lblPositionTargetValue.setText(_str)
            # Control Bound
            # Set the text based on the control selected.
            _str = "Control Bound Value:"
            _str += f"[0, 1]:"
            slrrange, valrange = self.get_ctrlbnd_slider_value_ranges()
            _val = self._pos2tgt(slrrange, valrange, self.ui.hSliderCtrlBndValue.value())
            _str += f" {_val:-1.2f}"
            self.ui.lblControlBoundValue.setText(_str)
    
    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = PlutoDataViewWindow(plutodev=self.pluto,
                                               mode="DIAGNOSTICS",
                                               pos=(50, 300))
        self._devdatawnd.show()

    #
    # Signal Callbacks
    # 
    def _attach_pluto_callbacks(self):
        pass
    
    def _detach_pluto_callbacks(self):
        pass

    #
    # Control Callbacks
    #
    def _callback_test_device_control_selected(self, event):
        # Reset the torque & position slider values
        self._set_torque_slider_value(0)
        self._set_position_slider_value(self.pluto.angle)
        # Check what has been selected.
        if self.ui.radioNone.isChecked():
            self.pluto.set_control_type("NONE")
        elif self.ui.radioTorque.isChecked():
            self.pluto.set_control_type("TORQUE")
        elif self.ui.radioPosition.isChecked():
            self.pluto.set_control_type("POSITION")
        self.update_ui()
    
    def _callback_test_position_target_changed(self, event):
        # Get the current target position and send it to the device.
        slrrange, valrange = self.get_position_slider_value_ranges()
        _tgt = self._pos2tgt(slrrange, valrange, self.ui.hSliderPosTgtValue.value())
        self.pluto.set_control_target(_tgt)
        self.update_ui()
    
    def _callback_test_torque_target_changed(self, event):
        # Get the current target position and send it to the device.
        slrrange, valrange = self.get_torque_slider_value_ranges()
        _tgt = self._pos2tgt(slrrange, valrange, self.ui.hSliderTorqTgtValue.value())
        self.pluto.set_control_target(_tgt, target0=self.pluto.desired, t0=0, dur=2.0)
        self.update_ui()
    
    def _callback_test_ctrlbnd_target_changed(self, event):
        self.pluto.set_control_bound((self.ui.hSliderCtrlBndValue.value() * 1.0) / 255)
        self.update_ui()

    def _callback_test_ctrlgain_target_changed(self, event):
        _off = pdef.PlutoMinControlGain
        _scale = pdef.PlutoMaxControlGain - _off
        self.pluto.set_control_gain(_off + (_scale * self.ui.hSliderCtrlGainValue.value()) / 255)
        self.update_ui()

    #
    # Supporting functions
    #
    def get_torque_slider_value_ranges(self):
        return (
            (self.ui.hSliderTorqTgtValue.minimum(),
             self.ui.hSliderTorqTgtValue.maximum()),
            (pdef.PlutoTargetRanges["TORQUE"][0],
             pdef.PlutoTargetRanges["TORQUE"][1])
        )

    def get_position_slider_value_ranges(self):
        return (
            (self.ui.hSliderPosTgtValue.minimum(),
             self.ui.hSliderPosTgtValue.maximum()),
            (pdef.PlutoTargetRanges["POSITION"][self._mech][0],
             pdef.PlutoTargetRanges["POSITION"][self._mech][1])
        )

    def get_ctrlbnd_slider_value_ranges(self):
        return (
            (self.ui.hSliderCtrlBndValue.minimum(),
             self.ui.hSliderCtrlBndValue.maximum()),
            (pdef.PlutoMinControlBound, 
             pdef.PlutoMaxControlBound)
        )

    def get_ctrlgain_slider_value_ranges(self):
        return (
            (self.ui.hSliderCtrlGainValue.minimum(),
             self.ui.hSliderCtrlGainValue.maximum()),
            (pdef.PlutoMinControlGain, 
             pdef.PlutoMaxControlGain)
        )
    
    def _tgt2pos(self, sldrrange, valrange, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self.ui.radioTorque.isChecked()
                or self.ui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = sldrrange
        _minv, _maxv = valrange
        return int(_mins + (_maxs - _mins) * (value - _minv) / (_maxv - _minv))

    def _pos2tgt(self, sldrrange, valrange, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self.ui.radioTorque.isChecked()
                or self.ui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = sldrrange
        _minv, _maxv = valrange
        return _minv + (_maxv - _minv) * (value - _mins) / (_maxs - _mins)

    def _get_torque_slider_value(self):
        slrrange, valrange = self.get_torque_slider_value_ranges()
        return self._pos2tgt(slrrange, valrange, self.ui.hSliderPosTgtValue.value())
    
    def _set_torque_slider_value(self, value):
        slrrange, valrange = self.get_torque_slider_value_ranges()
        self.ui.hSliderTorqTgtValue.setValue(self._tgt2pos(slrrange, valrange, value))

    def _get_position_slider_value(self):
        slrrange, valrange = self.get_position_slider_value_ranges()
        return self._pos2tgt(slrrange, valrange, self.ui.hSliderPosTgtValue.value())
    
    def _set_position_slider_value(self, value):
        slrrange, valrange = self.get_position_slider_value_ranges()
        self.ui.hSliderPosTgtValue.setValue(self._tgt2pos(slrrange, valrange, value))


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM13")
    pdataview = PlutoTestControlWindow(plutodev=plutodev,
                                       mech="HOC",
                                       dataviewer=True,
                                       onclosedb=lambda: print("Window closed"),
                                       heartbeat=True)
    pdataview.show()
    sys.exit(app.exec_())
