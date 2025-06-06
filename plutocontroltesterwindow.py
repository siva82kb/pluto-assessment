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
from ui_plutocontroltester import Ui_PlutoControlTesterWindow


class PlutoControlTesterWindow(QtWidgets.QMainWindow):
    """
    Class for handling the operation of the PLUTO test control window.
    """
    def __init__(self, parent=None, plutodev: QtPluto=None, limb=None, mech=None, modal=False, 
                 dataviewer=False, onclosedb=None, heartbeat=False):
        """
        Constructor for the PTestControlViewWindow class.
        """
        super(PlutoControlTesterWindow, self).__init__(parent)
        self.ui = Ui_PlutoControlTesterWindow()
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
        self.ui.radioPositionLinear.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioTorque.clicked.connect(self._callback_test_device_control_selected)
        self.ui.radioObjectSim.clicked.connect(self._callback_test_device_control_selected)
        self.ui.pbSetTarget.clicked.connect(self._callback_on_set_target)
        self.ui.pbCtrlHold.clicked.connect(self._callback_on_control_hold)
        self.ui.pbCtrlDecay.clicked.connect(self._callback_on_control_decay)

        # Update UI.
        self._dsbupdate = False
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
        _torqcontrol = self.ui.radioTorque.isChecked()
        _poscontrol = self.ui.radioPosition.isChecked() or self.ui.radioPositionLinear.isChecked()
        _objsimcontrol = self.ui.radioObjectSim.isChecked()
        # Enable/disable spinners
        self.ui.dsbTgtDur.setEnabled(_torqcontrol or _poscontrol)
        self.ui.dsbPosTgtValue.setEnabled(_poscontrol)
        self.ui.dsbTorqTgtValue.setEnabled(self.ui.radioTorque.isChecked())
        self.ui.dsbCtrlBndValue.setEnabled(_poscontrol)
        self.ui.dsbCtrlGainValue.setEnabled(_poscontrol)
        self.ui.dsbObjPos.setEnabled(_objsimcontrol)
        self.ui.dsbObjDelPos.setEnabled(_objsimcontrol)
        # Enable/disable control buttons
        self.ui.pbSetTarget.setEnabled(_torqcontrol or _poscontrol or _objsimcontrol)
        self.ui.pbCtrlHold.setEnabled(_poscontrol)
        self.ui.pbCtrlDecay.setEnabled(_poscontrol)
        
        # Check the status of the radio buttons.
        if not (_torqcontrol or _poscontrol or _objsimcontrol):
            self.ui.lblFeedforwardTorqueValue.setText("Feedforward Torque Value (Nm):")
            self.ui.lblPositionTargetValue.setText("Target Position Value (deg):")
            self.ui.lblControlBoundValue.setText("Control Bound Value:")
            self.ui.lblControlGainValue.setText("Control Gain Value:")
        elif _poscontrol:
            self.ui.lblFeedforwardTorqueValue.setText("Feedforward Torque Value (Nm):")
            if self._dsbupdate:
                # Update the target position DSB.
                self._update_tgtpos_dsb()
                # Control Bound
                self._update_ctrlbnd_dsb()
                # Control Gain
                self._update_ctrlgain_dsb()
                self._dsbupdate = False
        else:
            # Desired torque
            _str = "Feedforward Torque Value (Nm) "
            _str += f"[{pdef.PlutoTargetRanges['TORQUE'][0]:3.0f}, {pdef.PlutoTargetRanges['TORQUE'][1]:3.0f}]:"
            slrrange, valrange = self.get_torque_slider_value_ranges()
            _val = self._pos2tgt(slrrange, valrange, self.ui.dsbTorqTgtValue.value())
            _str += f" {_val:-3.1f}Nm"
            self.ui.lblFeedforwardTorqueValue.setText(_str)
            self.ui.lblPositionTargetValue.setText("Target Position Value (deg):")
            self.ui.lblControlBoundValue.setText("Control Bound Value:")
            self.ui.lblControlGainValue.setText("Control Gain Value:")
    
    def _update_tgtpos_dsb(self):
        _str = "Joint angle (deg): " if self._mech != "HOC" else "Hand Aperture (cm): "
        _scale = -pdef.HOCScale if self._mech == "HOC" else 1.0
        _posrange = [_scale * _v for _v in pdef.PlutoTargetRanges["POSITION"][self._mech]]
        # First disable the callback function for value change.
        self.ui.dsbPosTgtValue.blockSignals(True)
        self.ui.dsbPosTgtValue.setRange(_posrange[0], _posrange[1])
        self.ui.dsbPosTgtValue.setSingleStep(0.1 if self._mech != "HOC" else 1.0)
        self.ui.dsbPosTgtValue.setValue(self.pluto.hocdisp if self._mech == "HOC" else self.pluto.angle)
        # Renable the callback function for value change.
        self.ui.dsbPosTgtValue.blockSignals(False)
        # Update text
        _str += f"[{_posrange[0]:2.1f}, {_posrange[1]:2.1f}]:"
        _str += f" {self.ui.dsbPosTgtValue.value():2.2f}" + "cm" if self._mech == "HOC" else "deg"
        self.ui.lblPositionTargetValue.setText(_str)
    
    def _update_ctrlbnd_dsb(self):
        _str = "Control Bound Value:"
        _str += f"[{self.ui.dsbCtrlBndValue.minimum():1.1f}, {self.ui.dsbCtrlBndValue.maximum():1.1f}]:"
        self.ui.dsbCtrlBndValue.setValue(self.pluto.controlbound)
        _str += f" {self.ui.dsbCtrlBndValue.value():-1.2f}"
        self.ui.lblControlBoundValue.setText(_str)
    
    def _update_ctrlgain_dsb(self):
        _str = "Control Gain Value:"
        _str += f"[{self.ui.dsbCtrlGainValue.minimum():1.1f}, {self.ui.dsbCtrlGainValue.maximum():1.1f}]:"
        self.ui.dsbCtrlGainValue.setValue(self.pluto.controlgain)
        _str += f" {self.ui.dsbCtrlGainValue.value():-1.2f}"
        self.ui.lblControlGainValue.setText(_str)
    
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
        # self._set_torque_slider_value(0)
        # self._set_position_slider_value(self.pluto.angle)
        # Check what has been selected.
        if self.ui.radioNone.isChecked():
            self.pluto.set_control_type("NONE")
        elif self.ui.radioTorque.isChecked():
            self.pluto.set_control_type("TORQUE")
        elif self.ui.radioPosition.isChecked():
            self.pluto.set_control_type("POSITION")
        elif self.ui.radioPositionLinear.isChecked():
            self.pluto.set_control_type("POSITIONLINEAR")
        elif self.ui.radioObjectSim.isChecked():
            self.pluto.set_control_type("OBJECTSIM")
        self._dsbupdate = True
        self.update_ui()
    
    def _callback_test_position_target_changed(self, event):
        print(self.ui.dsbPosTgtValue.value())
        # Get the current target position and send it to the device.
        # slrrange, valrange = self.get_position_slider_value_ranges()
        # _tgt = self._pos2tgt(slrrange, valrange, self.ui.dsbPosTgtValue.value())
        # self.pluto.set_control_target(_tgt)
        self.update_ui()
    
    def _callback_test_torque_target_changed(self, event):
        # Get the current target position and send it to the device.
        slrrange, valrange = self.get_torque_slider_value_ranges()
        _tgt = self._pos2tgt(slrrange, valrange, self.ui.dsbTorqTgtValue.value())
        # self.pluto.set_control_target(_tgt, target0=self.pluto.desired, t0=0, dur=2.0)
        self.update_ui()
    
    def _callback_test_ctrlbnd_target_changed(self, event):
        self.pluto.set_control_bound((self.ui.dsbCtrlBndValue.value() * 1.0) / 255)
        self.update_ui()

    def _callback_test_ctrlgain_target_changed(self, event):
        _off = pdef.PlutoMinControlGain
        _scale = pdef.PlutoMaxControlGain - _off
        self.pluto.set_control_gain(_off + (_scale * self.ui.dsbCtrlGainValue.value()) / 255)
        self.update_ui()
    
    def _callback_on_set_target(self, event):
        _dur = self.ui.dsbTgtDur.value()
        # Check if object param is to be set.
        if self.ui.radioObjectSim.isChecked():
            _delposition = self.ui.dsbObjDelPos.value()
            _position = self.ui.dsbObjPos.value()
            self.pluto.set_object_param(_delposition, _position)
            QtCore.QThread.msleep(100)
            self.pluto.get_object_param()
            QtCore.QThread.msleep(100)
            self.pluto.set_diagnostic_mode()
            print(f"Delta Position: {_delposition}, Position: {_position}")
            return
        # Torque or position target is to be set.
        if self.ui.radioTorque.isChecked():
            _tgt = self.ui.dsbTorqTgtValue.value()
        elif self.ui.radioPosition.isChecked() or self.ui.radioPositionLinear.isChecked():
            _tgt = self.ui.dsbPosTgtValue.value()
            _tgt = - _tgt / pdef.HOCScale if self._mech == "HOC" else _tgt
            # Set control bound.
            self.pluto.set_control_bound(self.ui.dsbCtrlBndValue.value())
            # Wait for 100ms
            QtCore.QThread.msleep(100)
            # Set control gain.
            self.pluto.set_control_gain(self.ui.dsbCtrlGainValue.value())
            # Wait for 100ms
            QtCore.QThread.msleep(100)
        # Set the control target.
        self.pluto.set_control_target(
            target=_tgt,
            target0=self.pluto.angle,
            t0=0,
            dur=_dur
        )
    
    def _callback_on_control_hold(self, event):
        self.pluto.hold_control()

    def _callback_on_control_decay(self, event):
        self.pluto.decay_control()

    #
    # Supporting functions
    #
    def get_torque_slider_value_ranges(self):
        return (
            (self.ui.dsbTorqTgtValue.minimum(),
             self.ui.dsbTorqTgtValue.maximum()),
            (pdef.PlutoTargetRanges["TORQUE"][0],
             pdef.PlutoTargetRanges["TORQUE"][1])
        )

    def get_position_slider_value_ranges(self):
        _scale = -pdef.HOCScale if self._mech == "HOC" else 1.0
        return (
            (self.ui.dsbPosTgtValue.minimum(),
             self.ui.dsbPosTgtValue.maximum()),
            (_scale * pdef.PlutoTargetRanges["POSITION"][self._mech][0],
             _scale * pdef.PlutoTargetRanges["POSITION"][self._mech][1])
        )

    def get_ctrlbnd_slider_value_ranges(self):
        return (
            (self.ui.dsbCtrlBndValue.minimum(),
             self.ui.dsbCtrlBndValue.maximum()),    
            (pdef.PlutoMinControlBound, 
             pdef.PlutoMaxControlBound)
        )

    def get_ctrlgain_slider_value_ranges(self):
        return (
            (self.ui.dsbCtrlGainValue.minimum(),
             self.ui.dsbCtrlGainValue.maximum()),
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
        return self._pos2tgt(slrrange, valrange, self.ui.dsbPosTgtValue.value())
    
    def _set_torque_slider_value(self, value):
        slrrange, valrange = self.get_torque_slider_value_ranges()
        self.ui.dsbTorqTgtValue.setValue(self._tgt2pos(slrrange, valrange, value))

    def _get_position_slider_value(self):
        slrrange, valrange = self.get_position_slider_value_ranges()
        return self._pos2tgt(slrrange, valrange, self.ui.dsbPosTgtValue.value())
    
    def _set_position_slider_value(self, value):
        slrrange, valrange = self.get_position_slider_value_ranges()
        self.ui.dsbPosTgtValue.setValue(self._tgt2pos(slrrange, valrange, value))


if __name__ == '__main__':
    import qtjedi
    qtjedi._OUTDEBUG = False
    app = QtWidgets.QApplication(sys.argv)
    plutodev = QtPluto("COM13")
    pdataview = PlutoControlTesterWindow(plutodev=plutodev,
                                       mech="HOC",
                                       dataviewer=True,
                                       onclosedb=lambda: print("Window closed"),
                                       heartbeat=True)
    pdataview.show()
    sys.exit(app.exec_())
