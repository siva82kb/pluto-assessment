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
        # Update calibration status
        self._calib = self.pluto.calibration == 1
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


    # @property
    # def connected(self):
    #     return self._client is not None
    
    # def display(self, msg, currtime=True):
    #     _headstr = (f"[{dt.now().strftime('%y/%m/%d %H:%M:%S')}] "
    #                 if currtime
    #                 else "" )
    #     self.text_console.appendPlainText(
    #         f"{_headstr} {msg}"
    #     )
    
    # def display_response(self, msg, currtime=True):
    #     self.text_console.appendPlainText(
    #         f"{msg}"
    #     )
    
    # def _display_error(self, err1, err2):
    #     # Display all errors.
    #     _errs = [Error_Types1[i]
    #              for i, _b in enumerate(get_number_bits(err1)[::-1])
    #              if _b == 1]
    #     self.display(f"Error: {' | '.join(_errs)}")
    
    # def update_ui(self):
    #     # Update State and Error.
    #     if self._err == 0x00:
    #         self.lbl_status.setText(f"{ARIMU_States[self._prgState]} | No Errors")
    #     else:
    #         _errs = [Error_Types1[i]
    #                  for i, _b in enumerate(get_number_bits(self._err)[::-1])
    #                  if _b == 1]
    #         self.lbl_status.setText(f"{ARIMU_States[self._prgState]}"
    #                                 + f"| Error: {' | '.join(_errs)}")
        
    #     # Enable/Disable connect button.
    #     self.btn_connect_com.setEnabled(
    #         self.cb_com_devices.count() != 0 or 
    #         (self.cb_com_devices.count() > 0 and
    #          self.cb_com_devices.currentItem() is None)
    #         )
        
    #     if self.connected:
    #         self.cb_com_devices.setEnabled(False)
    #         self.btn_connect_com.setText("Disconnect")
    #     else:
    #         self.cb_com_devices.setEnabled(True)
    #         self.btn_connect_com.setText("Connect")
    #     # Enable ARIMU commands.
    #     self.btn_ping.setEnabled(self.connected)
    #     self.btn_get_time.setEnabled(self.connected)
    #     self.btn_set_time.setEnabled(self.connected)
    #     self.btn_get_files.setEnabled(self.connected)
    #     self.btn_start_stop_normal.setEnabled(self.connected and
    #                                           self._prgState == PRGSTATE_NONE or
    #                                           self._prgState == PRGSTATE_NORMAL)
    #     if (self._prgState == PRGSTATE_NORMAL):
    #         self.btn_start_stop_normal.setText("Stop Normal")
    #     else:
    #         self.btn_start_stop_normal.setText("Start Normal")
            
    #     self.btn_start_stop_expt.setEnabled(self.connected and
    #                                         self._prgState == PRGSTATE_NONE or
    #                                         self._prgState == PRGSTATE_EXPERIMENT)
    #     if (self._prgState == PRGSTATE_EXPERIMENT):
    #         self.btn_start_stop_expt.setText("Stop Experiment")
    #     else:
    #         self.btn_start_stop_expt.setText("Start Experiment")
            
    #     self.btn_start_stop_stream.setEnabled(self.connected and
    #                                           self._prgState == PRGSTATE_NONE or
    #                                           self._prgState == PRGSTATE_STREAMING)
    #     if (self._prgState == PRGSTATE_STREAMING):
    #         self.btn_start_stop_stream.setText("Stop Streaming")
    #     else:
    #         self.btn_start_stop_stream.setText("Start Streaming")
            
    #     self.btn_get_subjname.setEnabled(self.connected)
    #     self.btn_set_subjname.setEnabled(self.connected)
    #     self.btn_get_current_filename.setEnabled(self.connected)
        
    #     # Update start/stop experiment
    #     if (self._prgState == PRGSTATE_EXPERIMENT):
    #         self.btn_start_stop_expt.setText("Stop Experiment")
    #     else:
    #         self.btn_start_stop_expt.setText("Start Experiment")
            
    #     # Update start/stop straming
    #     if (self._prgState == PRGSTATE_STREAMING):
    #         self.btn_start_stop_stream.setText("Stop Streaming")
    #     else:
    #         self.btn_start_stop_stream.setText("Start Streaming")
    
    # def _callback_connect_to_arimu(self):
    #     self._client = qtjedi.JediComm(self.cb_com_devices.currentData(),
    #                                    115200)
    #     self._client.newdata_signal.connect(self._handle_new_packets)
    #     self._client.start()
    #     time.sleep(1.0)
    #     # Get the status of the device.
    #     self._client.send_message([STATUS])
    #     self.update_ui()
    
    # def _callback_status_time(self):
    #     if self.connected:
    #         self.update_ui()
        
    #     # Ping the docking station if in DOCKSTNCOMM mode.
    #     if self._prgState == PRGSTATE_DOCKSTNCOMM:
    #         self._client.send_message([DOCKSTNPING])
    
    # def _handle_new_packets(self, payload):
    #     # Handle packet.
    #     _cmd, self._prgState, self._err, *_pl = payload
    #     self._arimu_resp_hndlrs[_cmd](_pl)
    #     self.update_ui()
    
    # def _handle_status_response(self, payload):
    #     self.update_ui()
            
    # def _handle_ping_response(self, payload):
    #     self.display_response(f"Device name: {bytearray(payload).decode()}")
    
    # def _handle_gettime_response(self, payload):
    #     _pldbytes = [bytearray(payload[i:i+4])
    #                  for i in range(0, 28, 4)]
    #     # Group payload components.
    #     _temp = [struct.unpack('<L', _pldbytes[i])[-1]
    #              for i in range(7)]
    #     _ts = (f'{_temp[0]:02d}-{_temp[1]:02d}-{_temp[2]:02d}'
    #            + f'T{_temp[3]}:{_temp[4]}:{_temp[5]}.{_temp[6]}')
    #     _currt = dt.strptime(_ts, '%y-%m-%dT%H:%M:%S.%f')
    #     # Micros data.
    #     _microst = struct.unpack('<L', bytearray(payload[28:32]))[-1]
    #     self.display_response(f"Current time: {_currt} | Micros: {_microst} us")
    
    # def _handle_settime_response(self, payload):
    #     _pldbytes = [bytearray(payload[i:i+4])
    #                  for i in range(0, 28, 4)]
    #     # Group payload components.
    #     _temp = [struct.unpack('<L', _pldbytes[i])[-1]
    #              for i in range(7)]
    #     _ts = (f'{_temp[0]:02d}-{_temp[1]:02d}-{_temp[2]:02d}'
    #            + f'T{_temp[3]}:{_temp[4]}:{_temp[5]}.{_temp[6]}')
    #     _currt = dt.strptime(_ts, '%y-%m-%dT%H:%M:%S.%f')
    #     # Micros data.
    #     _microst = struct.unpack('<L', bytearray(payload[28:32]))[-1]
    #     self.display_response(f"Current time: {_currt} | Micros: {_microst} us")
    
    # def _handle_setsubject_response(self, payload):
    #     self.display_response(f"Current subject: {bytearray(payload).decode()}")
        
    # def _handle_getsubject_response(self, payload):
    #     self.display_response(f"Current subject: {bytearray(payload).decode()}")
    
    # def _handle_currentfilename_response(self, payload):
    #     self.display_response(f"Current filename: {bytearray(payload).decode()}")
    
    # def _handle_listfiles_response(self, payload):
    #     # Decode nad build file list.
    #     # 1. check if this is the start of file list.
    #     _str = bytearray(payload).decode()
    #     if _str[0] == '[':
    #         # Create a new list.
    #         self._flist = []
    #         self._flist_temp = bytearray(payload).decode()[1:-1].split(",")
    #     elif len(self._flist) == 0 and len(self._flist_temp) != 0:
    #         # Check if end of list is reached.
    #         if _str[-1] == ']':
    #             # End of file list.
    #             self._flist_temp += bytearray(payload).decode()[0:-2].split(",")
    #             self._flist = self._flist_temp
    #             self._flist_temp = []
    #         else:
    #             self._flist_temp += bytearray(payload).decode()[0:-1].split(",")
    #     if len(self._flist) != 0:
    #         self.display_response(f"List of fisles ({len(self._flist)}): {' | '.join(self._flist)}")
    #         self.lbl_stream.setText("")
    #     else:
    #         self.lbl_stream.setText(f"Getting file list ... {len(self._flist_temp)}")
    
    # def _handle_getfiledata_response(self, payload):
    #     if payload[0] == FILEHEADER:
    #         # Create new file.
    #         self._currfhndl = open(self._currfname, "wb")
    #         self.display_response(f"File size: {struct.unpack('<L', bytearray(payload[1:5]))}")
    #     else:
    #         sys.stdout.write(f"\rObtained: {payload[1] * 100 / 255:03.1f}%")
    #         if self._currfhndl is not None:
    #             self._currfhndl.write(bytearray(payload[2:]))
    #         if payload[1] == 255:
    #             self._currfhndl.close()
    #             self._currfname = ""
    #             self.display_response(f"File {self._currfname} saved!")
    
    # def _handle_deletefile_response(self, payload):
    #     if payload[0] == FILEDELETED:
    #         self.display_response(f"File {self._currfname} deleted!")
    #     if payload[0] == FILENOTDELETED:
    #         self.display_response(f"File {self._currfname} not deleted!")
            
    # def _handle_start_stream_response(self, payload):
    #     self._strm_disp_cnt += 1
    #     # Decode data and display on the streaming strip.
    #     if len(payload) == 20:
    #         _epoch = struct.unpack('<L', bytearray(payload[0:4]))[0]
    #         _micros = struct.unpack('<L', bytearray(payload[4:8]))[0]
    #         _imu = struct.unpack('<6h', bytearray(payload[8:20]))
    #         # Write row.
    #         if self._strm_fhndl is not None:
    #             _str = ",".join((f"{_epoch}",
    #                              f"{_micros}",
    #                              ",".join(map(str, _imu))))
    #             self._strm_fhndl.write(f"{_str}\n")
    #         if self._strm_disp_cnt % 10 == 0:
    #             _str = f"{_micros // 1000:06d} | acc: ({_imu[0]:+6d}, {_imu[1]:+6d}, {_imu[2]:+6d})"
    #             _str += f" | gyr: ({_imu[3]:+6d}, {_imu[4]:+6d}, {_imu[5]:+6d})"
    #             self.lbl_stream.setText(_str)
    
    # def _handle_stop_stream_response(self, payload):
    #     # Close stream file
    #     if self._strm_fhndl is not None:
    #         self._strm_fhndl.close()
    #         self._strm_fhndl = None
    #     self.lbl_stream.setText("")
    
    # def _handle_startnormal_response(self, payload):
    #     self.display_response("Started Normal Mode.")

    # def _handle_stopnormal_response(self, payload):
    #     self.display_response("Stopped Normal Mode.")

    # def _handle_startexpt_response(self, payload):
    #     self.display_response("Started Experiment Mode")
        
    # def _handle_stopexpt_response(self, payload):
    #     self.display_response("Stopped Experiment Mode")
    
    # def _handle_start_dockstncomm_response(self, payload):
    #     self.display_response("Started Docking Station Communication Mode.")
    #     self.gb_arimu_dockstn.setChecked(True)
        
    # def _handle_stop_dockstncomm_response(self, payload):
    #     self.display_response("Termianted Docking Station Communication Mode.")
    #     self.gb_arimu_dockstn.setChecked(False)
    
    # def _handle_settonone_response(self, payload):
    #     self.display_response("Set to None Mode.")

    # def _callback_ping_arimu(self):
    #     # Send PING message to ARIMU
    #     self.display("Pinging ARIMU ... ")
    #     self._client.send_message([PING])
    
    # def _callback_gettime_arimu(self):
    #     # Get time
    #     self.display("Getting time ... ")
    #     self._client.send_message([GETTIME])
    
    # def _callback_settime_arimu(self):
    #     # Set time
    #     _currt = dt.now()
    #     self.display(f"Setting time to {_currt.strftime('%y/%m/%d %H:%M:%S.%f')}")
    #     _dtvals = (struct.pack("<L", _currt.year % 100)
    #                + struct.pack("<L", _currt.month)
    #                + struct.pack("<L", _currt.day)
    #                + struct.pack("<L", _currt.hour)
    #                + struct.pack("<L", _currt.minute)
    #                + struct.pack("<L", _currt.second)
    #                + struct.pack("<L", _currt.microsecond // 10000))
    #     self._client.send_message(bytearray([SETTIME]) + _dtvals)
    
    # def _callback_get_subjname_arimu(self):
    #     self.display("Get Subject Name ... ")
    #     self._client.send_message([GETSUBJECT])
    
    # def _callback_set_subjname_arimu(self):
    #     self.display("Set Subject Name ... ")
    #     text, ok = QInputDialog.getText(self, 'Subject Name', 'Enter subjecty name:')
    #     if ok:
    #         self._client.send_message(bytearray([SETSUBJECT])
    #                                   + bytearray(text, "ascii")
    #                                   + bytearray([0]))
    
    # def _callback_set_currentfilename_arimu(self):
    #     self.display("Get Current Data Filename ... ")
    #     self._client.send_message([CURRENTFILENAME])
    
    # def _callback_get_files_arimu(self):
    #     self.display("Get list of files ... ")
    #     self._client.send_message([LISTFILES])
    
    # def _callback_get_file_data_arimu(self):
    #     _file, ok = QInputDialog.getItem(self, "Which file?", 
    #                                      "Select file: ", self._flist,
    #                                      0, False)
    #     if ok:                        
    #         self._currfname = _file
    #         self.display(f"Get file data ... {self._currfname}")
    #         self._client.send_message(bytearray([GETFILEDATA])
    #                                 + bytearray(self._currfname, "ascii")
    #                                 + bytearray([0]))

    # def _callback_delete_file_arimu(self):
    #     _file, ok = QInputDialog.getItem(self, "Which file?", 
    #                                      "Select file: ", self._flist,
    #                                      0, False)
    #     if ok:                        
    #         self._currfname = _file
    #         self.display(f"Delete file ... {self._currfname}")
    #         self._client.send_message(bytearray([DELETEFILE])
    #                                   + bytearray(self._currfname, "ascii")
    #                                   + bytearray([0]))
    
    # def _callback_start_stop_normal_arimu(self):
    #     # Check the current status.
    #     if self.btn_start_stop_normal.text() == "Start Normal":
    #         self.display("Starting Normal Mode ...")
    #         self._client.send_message([STARTNORMAL])
    #     else:
    #         self.display("Stopping Normal Mode ...")
    #         self._client.send_message([STOPNORMAL])
        
    # def _callback_start_stop_expt_arimu(self):
    #     # Check the current status.
    #     if self.btn_start_stop_expt.text() == "Start Experiment":
    #         self.display("Starting Experiment Mode ...")
    #         self._client.send_message([STARTEXPT])
    #     else:
    #         self.display("Stopping Experiment Mode ...")
    #         self._client.send_message([STOPEXPT])
        
    # def _callback_start_stop_strm_arimu(self):
    #     # Check the current status.
    #     if self.btn_start_stop_stream.text() == "Start Streaming":
    #         self.display("Starting Streaming Mode ...")
    #         self._client.send_message([STARTSTREAM])
    #         self._strm_disp_cnt = 0
    #         # open file.
    #         self._strm_fname = f"streamdata/stream_data_{dt.now().strftime('%y_%m_%d_%H_%M_%S')}.csv"
    #         self._strm_fhndl = open(self._strm_fname, "w")
    #         self._strm_fhndl.write("epoch,micros,ax,ay,az,gx,gy,gz\n")
    #     else:
    #         self.display("Stopping Streaming Mode ...")
    #         self._client.send_message([STOPSTREAM])

    # def _callback_dockstn_selected_arimu(self):
    #     # Check the current state.
    #     if self.gb_arimu_dockstn.isChecked():
    #         # Swtich on docking station mode.
    #         self.display("Starting Docking Station Communication Mode ...")
    #         self._client.send_message([STARTDOCKSTNCOMM])
    #     else:
    #         # Switch off docking station mode.
    #         self.display("Terminating Docking Station Communication Mode ...")
    #         self._client.send_message([STOPDOCKSTNCOMM])


if __name__ == "__main__":
    # Logger
    # _logfile = f"logs/log-{dt.now().strftime('%Y-%m-%d-%H-%M-%S')}.log"
    # _fmt = '%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s'
    # logging.basicConfig(filename=_logfile,
    #                     format=_fmt,
    #                     datefmt='%Y-%m-%d %H:%M:%S',
    #                     level=logging.INFO)
    
    app = QtWidgets.QApplication(sys.argv)
    mywin = PlutoPropAssesor("COM5")
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())