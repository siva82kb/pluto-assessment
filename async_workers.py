"""
Module for async worker threads to handle blocking I/O operations.

Author: Sivakumar Balasubramanian
Date: 2025
Email: siva82kb@gmail.com
"""

from PyQt5.QtCore import QThread, pyqtSignal
import traceback


class LimbSetupWorker(QThread):
    """Worker thread to handle blocking I/O operations for limb selection."""

    # Signals
    started = pyqtSignal()  # Emitted when worker starts
    finished = pyqtSignal()  # Emitted when I/O operations complete successfully
    error = pyqtSignal(str)  # Emitted if an error occurs
    progress = pyqtSignal(str)  # Emitted to provide progress updates

    def __init__(self, data_obj, limb_text, parent=None):
        """
        Initialize the worker.

        Args:
            data_obj: PlutoAssessmentData instance
            limb_text: The limb text (e.g., "Left" or "Right")
            parent: Parent QObject
        """
        super().__init__(parent)
        self.data_obj = data_obj
        self.limb_text = limb_text.lower()

    def run(self):
        """Run the blocking I/O operations in the worker thread."""
        try:
            self.started.emit()

            # Step 1: Set the limb (creates folder and JSON file) - blocking I/O
            self.progress.emit("Setting limb and creating session folder...")
            self.data_obj.set_limb(self.limb_text)

            # Step 2: Initialize protocol data (reads CSV, parses with pandas) - blocking I/O
            self.progress.emit("Initializing protocol...")
            self.data_obj.start_protocol()

            # All I/O operations completed successfully
            self.finished.emit()

        except Exception as e:
            error_msg = f"Error during limb setup: {str(e)}\n{traceback.format_exc()}"
            self.error.emit(error_msg)
