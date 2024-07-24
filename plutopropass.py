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
import enum
import json
import random
import struct
# import asyncio
# import qasync
import numpy as np
import time
from qtjedi import JediComm

from ui_plutopropass import Ui_MainWindow

class PlutoPropAssesor(QtWidgets.QMainWindow, Ui_MainWindow):
    """Main window of the PLUTO proprioception assessment program.
    """
    
    
    def __init__(self, *args, **kwargs) -> None:
        """View initializer."""
        super(PlutoPropAssesor, self).__init__(*args, **kwargs)
        self.setupUi(self)

        # PLUTO COM
        self.pluto = JediComm("COM4")
        self.pluto.newdata_signal.connect(self.print)
        
        # # Fix size.
        # self.setFixedSize(self.geometry().width(),
        #                   self.geometry().height())
        
        # # BLE client.
        # self._client = None
        # self._fatal = False
        # self._prgState = PRGSTATE_NONE
        # self._err = 0
        
        # # File saving related variables.,
        # self._flist = []
        # self._flist_temp = []
        # self._currfname = []
        # self._currfhndl = None
        # self._strm_disp_cnt = 0
        # self._dockstn_enable = False
        
        # # stream logging.
        # self._strm_fname = ""
        # self._strm_fhndl = None
        
        # # Welcome message
        # self.display("Welcome to ARIMU Viewer", False)
        
        # # Populate COM ports combo box.
        # for p in comports():
        #     self.cb_com_devices.addItem(p.name, p.name)
        
        # # ARIMU Response Handler.
        # self._arimu_resp_hndlrs = {STATUS: self._handle_status_response,
        #                            PING: self._handle_ping_response,
        #                            LISTFILES: self._handle_listfiles_response,
        #                            GETFILEDATA: self._handle_getfiledata_response,
        #                            DELETEFILE: self._handle_deletefile_response,
        #                            SETTIME: self._handle_settime_response,
        #                            GETTIME: self._handle_gettime_response,
        #                            STARTSTREAM: self._handle_start_stream_response,
        #                            STOPSTREAM: self._handle_stop_stream_response,
        #                            STARTDOCKSTNCOMM: self._handle_start_dockstncomm_response,
        #                            STOPDOCKSTNCOMM: self._handle_stop_dockstncomm_response,
        #                            SETSUBJECT: self._handle_setsubject_response,
        #                            GETSUBJECT: self._handle_getsubject_response,
        #                            CURRENTFILENAME: self._handle_currentfilename_response,
        #                            STARTEXPT: self._handle_startexpt_response,
        #                            STOPEXPT: self._handle_stopexpt_response,
        #                            STARTNORMAL: self._handle_startnormal_response,
        #                            STOPNORMAL: self._handle_stopnormal_response,
        #                            SETTONONE: self._handle_settonone_response}
        
        # # Attach callbacks.
        # self.btn_connect_com.clicked.connect(self._callback_connect_to_arimu)
        # self.btn_ping.clicked.connect(self._callback_ping_arimu)
        # self.btn_get_time.clicked.connect(self._callback_gettime_arimu)
        # self.btn_set_time.clicked.connect(self._callback_settime_arimu)
        # self.btn_get_subjname.clicked.connect(self._callback_get_subjname_arimu)
        # self.btn_set_subjname.clicked.connect(self._callback_set_subjname_arimu)
        # self.btn_get_current_filename.clicked.connect(self._callback_set_currentfilename_arimu)
        # self.btn_get_files.clicked.connect(self._callback_get_files_arimu)
        # self.btn_get_file_data.clicked.connect(self._callback_get_file_data_arimu)
        # self.btn_delete_file.clicked.connect(self._callback_delete_file_arimu)
        # self.btn_start_stop_normal.clicked.connect(self._callback_start_stop_normal_arimu)
        # self.btn_start_stop_expt.clicked.connect(self._callback_start_stop_expt_arimu)
        # self.btn_start_stop_stream.clicked.connect(self._callback_start_stop_strm_arimu)
        # self.gb_arimu_dockstn.clicked.connect(self._callback_dockstn_selected_arimu)
        
        # # Populate the list of ARIMU devices.
        # self._timer = QTimer()
        # self._timer.timeout.connect(self._callback_status_time)
        # self._timer.start(500)
        # self.update_ui()
        self.pluto.start()
    
    # Print new data
    def print(self, data):
        self.lblTempText.setText(','.join([str(_d) for _d in data]))


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
    mywin = PlutoPropAssesor()
    # ImageUpdate()
    mywin.show()
    sys.exit(app.exec_())