"""
QT script defininf the functionality of the PLUTO proprioception assessment window.

Author: Sivakumar Balasubramanian
Date: 24 July 2024
Email: siva82kb@gmail.com
"""

import sys
import re
import pathlib
import json
from qtpluto import QtPluto
from datetime import datetime as dt

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
import pyqtgraph as pg

import plutodefs as pdef
import plutostatemachines as psm
from ui_plutopropass import Ui_PlutoPropAssessor
from ui_plutocalib import Ui_CalibrationWindow
from ui_plutodataview import Ui_DevDataWindow
from ui_plutotestcontrol import Ui_PlutoTestControlWindow
from ui_plutoromassess import Ui_RomAssessWindow
from ui_plutopropassessctrl import Ui_ProprioceptionAssessWindow

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
        self._currsess = None
        self._calib = False
        self._datadir = None
        self._romdata = {
            "AROM": 5.0,
            "PROM": 7.0
        }
        # self._romdata = {
        #     "AROM": 0.0,
        #     "PROM": 0.0
        # }
        self._propassdata = None
        self._set_subjectid("test")
        
        # Initialize timers.
        self.sbtimer = QTimer()
        self.sbtimer.timeout.connect(self._callback_sb_timer)
        self.sbtimer.start(1000)

        # Attach callback to the buttons
        self.pbSubject.clicked.connect(self._callback_select_subject)
        self.pbCalibration.clicked.connect(self._callback_calibrate)
        self.pbTestDevice.clicked.connect(self._callback_test_device)
        self.pbRomAssess.clicked.connect(self._callback_assess_rom)
        self.pbPropAssessment.clicked.connect(self._callback_assess_prop)

        # Attach callback to other events
        # self.closeEvent = self._calibwnd_close_event

        # Other windows
        self._devdatawnd = None
        self._calibwnd = None
        self._testdevwnd = None
        self._romwnd = None
        self._propwnd = None
        self._wnddata = {}

        # State machines for new windows
        self._smachines = {
            "calib": None,
            "rom": None,
            "prop": None
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
        
        # Write the subject details JSON file.
        self._write_subject_json()

        # update UI
        self.update_ui()
    
    def _callback_calibrate(self):
        # Create the calibration statemachine
        self._smachines["calib"] = psm.PlutoCalibrationStateMachine(self.pluto)
        
        # First reset calibration.
        self.pluto.calibrate("NOMECH")
        self.pluto.calibrate("NOMECH")
        self.pluto.calibrate("NOMECH")
        
        # Create an instance of the calibration window and open it as a modal 
        # window.
        self._calibwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_CalibrationWindow()
        self._calibwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._calibwnd)
        self._calibwnd.closeEvent = self._calibwnd_close_event
        self._calibwnd.show()
        self._update_calibwnd_ui()
    
    def _callback_test_device(self):
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
        self._update_testwnd_ui()

    def _callback_assess_rom(self):
        # Create the ROM statemachine
        self._smachines["rom"] = psm.PlutoRomAssessmentStateMachine(
            self.pluto,
            self._romdata["AROM"],
            self._romdata["PROM"]
        )
        
        # Create the window
        self._romwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_RomAssessWindow()
        self._romwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._romwnd)
        
        # Add graph to the window
        self._romassess_add_graph()

        # Attach events to the controls.
        self._romwnd.closeEvent = self._romwnd_close_event
        self._wndui.pbArom.clicked.connect(self._callback_arom_clicked)
        self._wndui.pbProm.clicked.connect(self._callback_prom_clicked)
        self._romwnd.show()
        self._update_romwnd_ui()

    def _callback_assess_prop(self):
        # Create the proprioception assessment statemachine
        self._smachines["prop"] = None
        
        # Create the window
        self._propwnd = QtWidgets.QMainWindow()
        self._wndui = Ui_ProprioceptionAssessWindow()
        self._propwnd.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._wndui.setupUi(self._propwnd)
        
        # Add graph to the window
        self._propassess_add_graph()

        # Attach events to the controls.
        self._propwnd.closeEvent = self._propwnd_close_event
        self._propwnd.show()
        self._update_propwnd_ui()

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
        
        if self._romwnd is not None:
            self._smachines["rom"].run_statemachine(
                None
            )
            self._update_romwnd_ui()

        if self._propwnd is not None:
            self._update_propwnd_ui()
    
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
            return
        
        # ROM Assessment Window
        if self._romwnd is not None:
            self._smachines["rom"].run_statemachine(
                psm.PlutoButtonEvents.RELEASED
            )
            # Update ROM data
            self._romdata["AROM"] = self._smachines["rom"].arom
            self._romdata["PROM"] = self._smachines["rom"].prom
            
            # Update IO
            self._update_romwnd_ui()
            return

    #
    # Other callbacks
    #
    def _calibwnd_close_event(self, event):
        self._calibwnd = None
        self._wndui = None
        self._smachines["calib"] = None
    
    def _testwnd_close_event(self, event):
        self._testwnd = None
        self._wndui = None

    def _romwnd_close_event(self, event):
        print("ROM Close")
        # Write the subject details JSON file.
        self._write_subject_json()
        # Reset variables
        self._romwnd = None
        self._wndui = None
        self._smachines["rom"] = None

    def _propwnd_close_event(self, event):
        # Reset variables
        self._propwnd = None
        self._wndui = None
        self._smachines["prop"] = None

    #
    # UI Update function
    #
    def update_ui(self):
        # Disable buttons if needed.
        self.pbSubject.setEnabled(self._subjid is None)
        self.pbTestDevice.setEnabled(self._subjid is not None and self._calib is True)
        self.pbRomAssess.setEnabled(self._subjid is not None and self._calib is True)
        self.pbPropAssessment.setEnabled(
            self._subjid is not None 
            and self._calib is True
            and self._romdata["AROM"] > 0
            and self._romdata["PROM"] > 0
        )

        # Calibration button
        if self._calib is False:
            self.pbCalibration.setText(f"Calibrate")
        else:
            self.pbCalibration.setText("Recalibrate")
        
        # Subject ID button
        if self._subjid is not None:
            self.pbSubject.setText(f"Subject: {self._subjid} [{self._currsess}]")
        else:
            self.pbSubject.setText("Select Subject")
        
        # Update ROM values on button text.
        if self._romdata["AROM"] > 0 and self._romdata["PROM"] > 0:
            self.pbRomAssess.setText(f"Assess ROM [AROM: {self._romdata['AROM']:5.2f}cm | AROM: {self._romdata['PROM']:5.2f}cm]")
        else:
            self.pbRomAssess.setText("Assess ROM")

    #
    # Supporting functions
    #
    def _set_subjectid(self, subjid):
        self._subjid = subjid
        self._currsess = dt.now().strftime("%Y-%m-%d-%H-%M-%S")
        # set data dirr and create if needed.        
        self._datadir = pathlib.Path(DATA_DIR, self._subjid, self._currsess)
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
            self._wndui.lblHandDistance.setText(f"{self.pluto.hocdisp:5.2f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button set ROM.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.WAIT_FOR_CLOSE:
            self._wndui.lblCalibStatus.setText("All Done!")
            self._wndui.lblHandDistance.setText(f"{self.pluto.hocdisp:5.2f}cm")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        elif self._smachines['calib'].state == psm.PlutoCalibStates.CALIB_ERROR:
            self._wndui.lblCalibStatus.setText("Error!")
            self._wndui.lblInstruction2.setText("Press the PLUTO button to close window.")
        else:
            self._calibwnd.close()
    
    def _update_testwnd_ui(self):
        _nocontrol = not (self._wndui.radioTorque.isChecked()
                          or self._wndui.radioPosition.isChecked())
        self._wndui.hSliderTgtValue.setEnabled(not _nocontrol)
        # Check the status of the radio buttons.
        if _nocontrol:
            self._wndui.lblTargetValue.setText(f"No Control Selected")
        else:
            # Set the text based on the control selected.
            _str = "Target Value: "
            _ctrl = "TORQUE" if self._wndui.radioTorque.isChecked() else "POSITION"
            _str += f"[{pdef.PlutoTargetRanges[_ctrl][0]:3.0f}, {pdef.PlutoTargetRanges[_ctrl][1]:3.0f}]"
            _str += f" {self._pos2tgt(self._wndui.hSliderTgtValue.value()):-3.1f}Nm"
            self._wndui.lblTargetValue.setText(_str)
    
    def _update_romwnd_ui(self):
        # Update the graph display
        # Current position
        if self._smachines["rom"].state == psm.PlutoRomAssessStates.FREE_RUNNING:
            self._wndui.currPosLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.currPosLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        elif self._smachines["rom"].state == psm.PlutoRomAssessStates.AROM_ASSESS:
            self._wndui.currPosLine1.setData([0, 0], [-30, 30])
            self._wndui.currPosLine2.setData([0, 0], [-30, 30])
            # AROM position
            self._wndui.aromLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.aromLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )
        elif self._smachines["rom"].state == psm.PlutoRomAssessStates.PROM_ASSESS:
            self._wndui.currPosLine1.setData([0, 0], [-30, 30])
            self._wndui.currPosLine2.setData([0, 0], [-30, 30])
            # PROM position
            self._wndui.promLine1.setData(
                [self.pluto.hocdisp, self.pluto.hocdisp],
                [-30, 30]
            )
            self._wndui.promLine2.setData(
                [-self.pluto.hocdisp, -self.pluto.hocdisp],
                [-30, 30]
            )

        # Udpate based on the current state of the ROM statemachine
        if self._wndui is None:
            return
        
        # Window still exists.
        self._wndui.textInstruction.setText(self._smachines['rom'].instruction)
        self._wndui.label.setText(f"PLUTO ROM Assessment [{self.pluto.hocdisp:5.2f}cm]")
        self._wndui.pbArom.setText(f"Assess AROM [{self._romdata['AROM']:5.2f}cm]")
        self._wndui.pbProm.setText(f"Assess PROM [{self._romdata['PROM']:5.2f}cm]")
        self._wndui.pbArom.setEnabled(
            self._smachines['rom'].state == psm.PlutoRomAssessStates.FREE_RUNNING
        )
        self._wndui.pbProm.setEnabled(
            self._smachines['rom'].state == psm.PlutoRomAssessStates.FREE_RUNNING
        )

        # Close if needed
        if self._smachines['rom'].state == psm.PlutoRomAssessStates.ROM_DONE:
            self._romwnd.close()
    
    def _update_propwnd_ui(self):
        # Update current hand position
        self._wndui.currPosLine1.setData(
            [self.pluto.hocdisp, self.pluto.hocdisp],
            [-30, 30]
        )
        self._wndui.currPosLine2.setData(
            [-self.pluto.hocdisp, -self.pluto.hocdisp],
            [-30, 30]
        )
        # Update hand displacement display
        self._wndui.label.setText(f"PLUTO Proprioception Assessment [{self.pluto.hocdisp:5.2f}cm]")

    def _romassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self._wndui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        _pgobj.setXRange(-10, 10)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self._wndui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        self._wndui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=2)
        )
        _pgobj.addItem(self._wndui.currPosLine1)
        _pgobj.addItem(self._wndui.currPosLine2)
        
        # AROM Lines
        self._wndui.aromLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        self._wndui.aromLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=2)
        )
        _pgobj.addItem(self._wndui.aromLine1)
        _pgobj.addItem(self._wndui.aromLine2)
        
        # PROM Lines
        self._wndui.promLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=2)
        )
        self._wndui.promLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=2)
        )
        _pgobj.addItem(self._wndui.promLine1)
        _pgobj.addItem(self._wndui.promLine2)
    
    def _propassess_add_graph(self):
        """Function to add graph and other objects for displaying HOC movements.
        """
        _pgobj = pg.PlotWidget()
        _templayout = QtWidgets.QGridLayout()
        _templayout.addWidget(_pgobj)
        _pen = pg.mkPen(color=(255, 0, 0))
        self._wndui.hocGraph.setLayout(_templayout)
        _pgobj.setYRange(-20, 20)
        _pgobj.setXRange(-10, 10)
        _pgobj.getAxis('bottom').setStyle(showValues=False)
        _pgobj.getAxis('left').setStyle(showValues=False)
        
        # Current position lines
        self._wndui.currPosLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        self._wndui.currPosLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#FFFFFF',width=1)
        )
        _pgobj.addItem(self._wndui.currPosLine1)
        _pgobj.addItem(self._wndui.currPosLine2)
        
        # AROM Lines
        self._wndui.aromLine1 = pg.PlotDataItem(
            [self._romdata["AROM"], self._romdata["AROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        self._wndui.aromLine2 = pg.PlotDataItem(
            [-self._romdata["AROM"], -self._romdata["AROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#FF8888',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self._wndui.aromLine1)
        _pgobj.addItem(self._wndui.aromLine2)
        
        # PROM Lines
        self._wndui.promLine1 = pg.PlotDataItem(
            [self._romdata["PROM"], self._romdata["PROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        self._wndui.promLine2 = pg.PlotDataItem(
            [-self._romdata["PROM"], -self._romdata["PROM"]],
            [-30, 30],
            pen=pg.mkPen(color = '#8888FF',width=1, style=QtCore.Qt.DotLine)
        )
        _pgobj.addItem(self._wndui.promLine1)
        _pgobj.addItem(self._wndui.promLine2)
        
        # Target Lines
        self._wndui.tgtLine1 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        self._wndui.tgtLine2 = pg.PlotDataItem(
            [0, 0],
            [-30, 30],
            pen=pg.mkPen(color = '#00FF00',width=2)
        )
        _pgobj.addItem(self._wndui.tgtLine1)
        _pgobj.addItem(self._wndui.tgtLine2)
    
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
        _dispdata = [
            "PLUTO Data",
            "----------",
            f"Time    : {self.pluto.currdata[0]}",
            f"Status  : {pdef.OutDataType[self.pluto.datatype]} | {pdef.ControlType[self.pluto.controltype]} | {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Error   : {pdef.ErrorTypes[self.pluto.error]}",
            f"Mech    : {pdef.Mehcanisms[self.pluto.mechanism]:<5s} | Calib   : {pdef.CalibrationStatus[self.pluto.calibration]}",
            f"Actd    : {self.pluto.actuated}",
        ]
        _dispdata += [
            f"Angle   : {self.pluto.angle:-07.2f}deg"
            + f" [{self.pluto.hocdisp:05.2f}cm]" if self._calib else ""
        ]
        _dispdata += [
            f"Torque  : {self.pluto.torque:3.1f}Nm",
            f"Control : {self.pluto.control:3.1f}",
            f"Target  : {self.pluto.desired:3.1f}",
            f"Button  : {self.pluto.button}",
        ]
        self._devdatawndui.textDevData.setText('\n'.join(_dispdata))

    #
    # Test window controls
    #
    def _callback_test_device_control_selected(self, event):
        # Check what has been selected.
        if self._wndui.radioNone.isChecked():
            self.pluto.set_control("NONE", 0)
        elif self._wndui.radioTorque.isChecked():
            self.pluto.set_control("TORQUE", 0)
            # Reset the target value
            self._wndui.hSliderTgtValue.setValue(self._tgt2pos(0))
            # Now send the target value.
            self.pluto.set_control("TORQUE", 0)
        elif self._wndui.radioPosition.isChecked():
            self.pluto.set_control("POSITION", 0)
            # Reset the target value
            self._wndui.hSliderTgtValue.setValue(self._tgt2pos(self.pluto.angle))
            # Now send the target value.
            self.pluto.set_control("POSITION", self.pluto.angle)
        self._update_testwnd_ui()
    
    def _callback_test_device_target_changed(self, event):
        # Get the current target position and send it to the device.
        _tgt = self._pos2tgt(self._wndui.hSliderTgtValue.value())
        _ctrl = "TORQUE" if self._wndui.radioTorque.isChecked() else "POSITION"
        self.pluto.set_control(_ctrl, _tgt)
        self._update_testwnd_ui()
    
    def _tgt2pos(self, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self._wndui.radioTorque.isChecked()
                or self._wndui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = (self._wndui.hSliderTgtValue.minimum(),
                        self._wndui.hSliderTgtValue.maximum())
        _ctrl = 'POSITION' if self._wndui.radioPosition.isChecked() else 'TORQUE'
        _minv, _maxv = (pdef.PlutoTargetRanges[_ctrl][0],
                        pdef.PlutoTargetRanges[_ctrl][1])
        return int(_mins + (_maxs - _mins) * (value - _minv) / (_maxv - _minv))

    def _pos2tgt(self, value):
        # Make sure this is not called by mistake for no control selection.
        if not (self._wndui.radioTorque.isChecked()
                or self._wndui.radioPosition.isChecked()):
            return 0
        # Make the convesion
        _mins, _maxs = (self._wndui.hSliderTgtValue.minimum(),
                        self._wndui.hSliderTgtValue.maximum())
        _ctrl = 'POSITION' if self._wndui.radioPosition.isChecked() else 'TORQUE'
        _minv, _maxv = (pdef.PlutoTargetRanges[_ctrl][0],
                        pdef.PlutoTargetRanges[_ctrl][1])
        return _minv + (_maxv - _minv) * (value - _mins) / (_maxs - _mins)

    # ROM Window Controls
    def _callback_arom_clicked(self, event):
        self._smachines["rom"].run_statemachine(
            psm.PlutoRomAssessEvent.AROM_SELECTED
        )
        self._update_romwnd_ui()
    
    def _callback_prom_clicked(self, event):
        self._smachines["rom"].run_statemachine(
            psm.PlutoRomAssessEvent.PROM_SELECTED
        )
        self._update_romwnd_ui()

    #
    # Main window close event
    # 
    def closeEvent(self, event):
        # Close the data viewer window
        if self._devdatawnd is not None:
            self._devdatawnd.close()

    #
    # Data logging fucntions
    #
    def _write_subject_json(self):
        _subjdata = {
            "SubjectID": self._subjid,
            "Session": self._currsess,
            "ROM": self._romdata,
            "PropAssessment": self._propassdata
        }
        with open(self._datadir / "session_details.json", "w") as _f:
            json.dump(_subjdata, _f, indent=4)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoPropAssesor("COM5")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())