"""
QT script defininf the functionality of the PLUTO proprioception assessment window.

Author: Sivakumar Balasubramanian
Date: 24 July 2024
Email: siva82kb@gmail.com
"""

import sys
import os
from PyQt5 import (
    QtCore,
    QtWidgets,)
from PyQt5.QtCore import (
    pyqtSignal,
    QTimer,)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QMessageBox,
    QInputDialog
)
from datetime import datetime as dt
import re
import glob
import pathlib
import enum
import json
import random
import struct
# import asyncio
# import qasync
import numpy as np
import time
from qtpluto import QtPluto

import plutodefs as pdef
import plutostatemachines as psm
from ui_plutopropass import Ui_PlutoPropAssessor
from ui_plutocalib import Ui_CalibrationWindow
from ui_plutodataview import Ui_DevDataWindow
from ui_plutotestcontrol import Ui_PlutoTestControlWindow

# Module level constants.
DATA_DIR = "propassessment"

class PlutoPropAssesor(QtWidgets.QMainWindow, Ui_PlutoPropAssessor):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    def __init__(self, port, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoPropAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # PLUTO COM
        self.pluto = QtPluto(port)
        self.pluto.newdata.connect(self._callback_newdata)
        self.pluto.btnpressed.connect(self._callback_btn_pressed)
        self.pluto.btnreleased.connect(self._callback_btn_released)
        
        # Subject details
        self._subjid = None
        self._calib = False
        self._datadir = None
        
        # Initialize timers.
        self.sbtimer = QTimer()
        self.sbtimer.timeout.connect(self._callback_sb_timer)
        self.sbtimer.start(1000)

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbCalibration.clicked.connect(self._callback_calibrate)
        self.pbTestDevice.clicked.connect(self._callback_test_device)

        # Attach callback to other events
        # self.closeEvent = self._calibwnd_close_event

        # Other windows
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._assesswnd = None
        self._wnddata = {}

        # State machines for new windows
        self._smachines = {
            "calib": None
        }

        # Open the device data viewer by default.
        self._open_devdata_viewer() 

        # Update UI
        self.update_ui()
    
    #
    # Controls callback
    #
    def _callback_select_subject(self):
        _subjid, _done = QInputDialog.getText(
             self,
             'Select Subject',
             'Enter subject ID:'
        )
        # Check if a valid input was given.
        if _done is False:
            return
        
        # Only alphabets and numbers are allowed.
        if re.match("^[A-Za-z0-9_-]*$", _subjid):
            # Check if the user name already exists
            _path = pathlib.Path(DATA_DIR, _subjid.lower())
            # Check if the user knows that this user name exists.
            if _path.exists():
                # Check if the user is OK with this. Else they will need to
                # create a new subject ID.
                reply = QMessageBox.question(
                    self, 'Existing Subject ID',
                    f'Subject ID: [{_subjid.lower()}] exists? Continue with this ID?',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
            # Set subject ID, and create the folder if needed.
            self._set_subjectid(_subjid.lower())
        
        # update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Create an instance of the calibration window and open it as a modal 
        # window.
        # First reset calibration.
        self.pluto.calibrate("NOMECH")
        self.pluto.calibrate("NOMECH")
        self.pluto.calibrate("NOMECH")
        self._calibwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_CalibrationWindow()
        self._calibwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._calibwnd)
        self._calibwnd.closeEvent = self._calibwnd_close_event
        self._calibwnd.show()
        # Start the calibration statemachine
        self._smachines["calib"] = psm.PlutoCalibrationStateMachine(self.pluto)
        self._update_calibwnd_ui()
    
    def _callback_test_device(self):
        print("sdfhsdfh")
        self._testdevwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_PlutoTestControlWindow()
        self._testdevwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._testdevwnd)
        # Attach events to the controls.
        self._testdevwnd.closeEvent = self._calibwnd_close_event
        self._wndui.radioNone.clicked.connect(self._callback_test_device_control_selected)
        self._wndui.radioPosition.clicked.connect(self._callback_test_device_control_selected)
        self._wndui.radioTorque.clicked.connect(self._callback_test_device_control_selected)
        self._wndui.hSliderTgtValue.valueChanged.connect(self._callback_test_device_target_changed)
        self._testdevwnd.show()
        # Start the calibration statemachine
        # self._smachines["calib"] = psm.PlutoCalibrationStateMachine(self.pluto)
        self._update_testwnd_ui()

    # 
    # Timer callbacks
    #
    def _callback_sb_timer(self):
        _con = self.pluto.is_connected()
        self.statusBar().showMessage(
            ' | '.join((
                _con if _con != "" else "Disconnected",
                f"FR: {self.pluto.framerate():3.1f}Hz"
            ))
        )

    #
    # Signal callbacks
    #
    def _callback_newdata(self):
        """Update the UI of the appropriate window.
        """
        # Update data viewer window.
        self._disp_update_counter += 1
        self._disp_update_counter %= 10
        if self._disp_update_counter == 0:
            self._update_devdatawnd_ui()
            self.update_ui()
        # Update calibration status
        self._calib = (self.pluto.calibration == 1)
        # Update other windows
        if self._calibwnd is not None:
            self._smachines["calib"].run_statemachine(
                None,
                "HOC"
            )
            # Update UI
            self._update_calibwnd_ui()
    
    def _callback_btn_pressed(self):
        pass
    
    def _callback_btn_released(self):
        """
        Handle this depnding on what window is currently open.
        """
        # Calibration Window
        if self._calibwnd is not None:
            self._smachines["calib"].run_statemachine(
                psm.PlutoButtonEvents.RELEASED,
                "HOC"
            )
            # Update UI
            self._update_calibwnd_ui()

    #
    # Other callbacks
    #
    def _calibwnd_close_event(self, event):
        pass
    
    def _testwnd_close_event(self, event):
        pass

    #
    # UI Update function
    #
    def update_ui(self):
        # Disable buttons if needed.
        self.pbSubject.setEnabled(self._subjid is None)
        self.pbTestDevice.setEnabled(self._subjid is not None and self._calib is True)
        self.pbPropAssessment.setEnabled(self._subjid is not None and self._calib is True)

        # Calibration button
        if self._calib is False:
            self.pbCalibration.setText(f"Calibrate")
        else:
            self.pbCalibration.setText("Recalibrate")
        
        # Subject ID button
        if self._subjid is not None:
            self.pbSubject.setText(f"Subject: {self._subjid}")
        else:
            self.pbSubject.setText("Select Subject")

    #
    # Supporting functions
    #
    def _set_subjectid(self, subjid):
        self._subjid = subjid
        # set data dirr and create if needed.
        self._datadir = pathlib.Path(DATA_DIR, self._subjid)
        self._datadir.mkdir(exist_ok=True)
    
    #
    # Calibration Window Functions
    #
    def _update_calibwnd_ui(self):
        # Update based on the current state of the Calib statemachine
        if self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_ZERO_SET:
            self._wndui.lblCalibStatus.setText("Not done.")
            self._wndui.lblHandDistance.setText("- NA- ")
            self._wndui.lblInstruction2.setText("Press the PLUTO button set zero.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_ROM_SET:
            self._wndui.lblCalibStatus.setText("Zero set.")
            self._wndui.lblHandDistance.setText(f"{self.pluto.angle:3.1f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button set ROM.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_CLOSE:
            self._wndui.lblCalibStatus.setText("All Done!")
            self._wndui.lblHandDistance.setText(f"{self.pluto.angle:3.1f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.CALIB_ERROR:
            self._wndui.lblCalibStatus.setText("Error!")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        else:
            self._calibwnd.close()
            self._calibwnd = None
            self._wndui = None
            self._smachines["calib"] = None
    
    def _update_testwnd_ui(self):
        _nocontrol = not (self._wndui.radioTorque.isChecked()
                          or self._wndui.radioPosition.isChecked())
        self._wndui.hSliderTgtValue.setEnabled(not _nocontrol)
        # Check the status of the radio buttons.
        if _nocontrol:
            self._wndui.lblTargetValue.setText(f"No Control Selected")
        else:
            self._wndui.lblTargetValue.setText(f"Target Value:")

    #
    # Device Data Viewer Functions 
    #
    def _open_devdata_viewer(self):
        self._devdatawnd = QtWidgets.QMainWindow()
        self._devdatawndui = Ui_DevDataWindow()
        self._devdatawndui.setupUi(self._devdatawnd)
        self._devdatawnd.show()
        self._disp_update_counter = 0
        self._update_devdatawnd_ui()
    
    def _update_devdatawnd_ui(self):
        # Check if new data is available
        if len(self.pluto.currdata) == 0:
            self._devdatawndui.textDevData.setText("No data available.")
            return
        # New data available. Format and display
        _dispdata = (
            "PLUTO Data",
            "----------",
            f"Time    : {self.pluto.currdata[0]}",
            f"Status  : {pdef.OutDataType[self.pluto.datatype]} | {pdef.ControlType[self.pluto.controltype]} | {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Error   : {pdef.ErrorTypes[self.pluto.error]}",
            f"Mech    : {pdef.Mehcanisms[self.pluto.mechanism]:>5s} | Calib   : {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Actd    : {self.pluto.actuated}",
            f"Angle   : {self.pluto.angle:3.1f}deg",
            f"Torque  : {self.pluto.torque:3.1f}Nm",
            f"Control : {self.pluto.control:3.1f}",
            f"Target  : {self.pluto.desired:3.1f}Nm",
            f"Button  : {self.pluto.button}",
        )    
        self._devdatawndui.textDevData.setText('\n'.join(_dispdata))

    #
    # Test window controls
    #
    def _callback_test_device_control_selected(self, event):
        # Check what has been selected.
        if self._wndui.radioNone.isChecked():
            self.pluto.set_control("NONE")
        elif self._wndui.radioTorque.isChecked():
            self.pluto.set_control("TORQUE", 0)
        elif self._wndui.radioPosition.isChecked():
            self.pluto.set_control("POSITION", 0)
        self._update_testwnd_ui()
    
    def _callback_test_device_target_changed(self, event):
        self._update_testwnd_ui()

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        # Close the data viewer window
        if self._devdatawnd is not None:
            self._devdatawnd.close()



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoPropAssesor("COM5")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())