import cv2
import os
import time
import queue
import threading
from datetime import datetime

from camera import Camera
from displayThread import DisplayThread


# ============================================================
# CONFIGURATION
# ============================================================

CAMERA_INDEX = 0

# Visualization
DEBUG = True

# FPS sent to display thread
FPS_pipe = 1.0

# Recorded video directory
RECORD_DIR = "recordings"

# Keep only the newest visualization frame
PIPE_QUEUE_SIZE = 1


# ============================================================
# VIDEO RECORDER
# ============================================================

class VideoRecorder:

    def __init__(self, directory):

        self.directory = directory

        self.writer = None
        self.filename = None

        os.makedirs(
            self.directory,
            exist_ok=True
        )

    def start(self, width, height, fps):

        if self.writer is not None:
            print("Already recording.")
            return

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        self.filename = os.path.join(
            self.directory,
            f"video_{timestamp}.avi"
        )

        fourcc = cv2.VideoWriter_fourcc(
            *"XVID"
        )

        self.writer = cv2.VideoWriter(
            self.filename,
            fourcc,
            fps,
            (width, height)
        )

        if not self.writer.isOpened():

            self.writer = None
            self.filename = None

            raise RuntimeError(
                "Could not create video file"
            )

        print()
        print("Recording started:")
        print(f"  File: {self.filename}")
        print(
            f"  Resolution: {width}x{height}"
        )
        print(
            f"  FPS: {fps:.2f}"
        )
        print()

    def write(self, frame):

        if self.writer is not None:
            self.writer.write(frame)

    def stop(self):

        if self.writer is None:
            return

        self.writer.release()

        print()
        print(
            f"Recording stopped: {self.filename}"
        )
        print()

        self.writer = None
        self.filename = None

    def is_recording(self):

        return self.writer is not None


# ============================================================
# COMMAND THREAD
# ============================================================

class CommandThread(threading.Thread):

    def __init__(
        self,
        command_queue,
        stop_event
    ):

        super().__init__(daemon=True)

        self.command_queue = command_queue
        self.stop_event = stop_event

    def run(self):

        print()
        print("Commands:")
        print("  R - Record")
        print("  S - Stop")
        print("  E - Exit")
        print()

        while not self.stop_event.is_set():

            try:
                command = input("> ")

            except EOFError:

                self.command_queue.put(
                    "E"
                )

                return

            command = command.strip().upper()

            if command in (
                "R",
                "S",
                "E"
            ):

                self.command_queue.put(
                    command
                )

            else:

                print(
                    "Unknown command. "
                    "Use R, S or E."
                )


# ============================================================
# CAPTURE THREAD
# ============================================================

class CaptureThread(threading.Thread):

    def __init__(
        self,
        camera,
        recorder,
        frame_queue,
        command_queue,
        stop_event,
        fps_pipe
    ):

        super().__init__()

        self.camera = camera
        self.recorder = recorder

        self.frame_queue = frame_queue
        self.command_queue = command_queue

        self.stop_event = stop_event

        self.fps_pipe = fps_pipe

        self.last_pipe_time = 0.0

    # --------------------------------------------------------
    # COMMANDS
    # --------------------------------------------------------

    def process_commands(self):

        while True:

            try:
                command = (
                    self.command_queue
                    .get_nowait()
                )

            except queue.Empty:
                break

            if command == "R":

                if not self.recorder.is_recording():

                    self.recorder.start(
                        self.camera.width,
                        self.camera.height,
                        self.camera.fps
                    )

            elif command == "S":

                self.recorder.stop()

            elif command == "E":

                print(
                    "E command received."
                )

                self.recorder.stop()

                self.stop_event.set()

                break

    # --------------------------------------------------------
    # SEND FRAME TO DISPLAY
    # --------------------------------------------------------

    def send_to_display(self, frame):

        # Reduce ONLY the visualization copy.
        small_frame = cv2.resize(
            frame,
            (640, 480),
            interpolation=cv2.INTER_AREA
        )

        # Queue size = 1.
        #
        # If an old frame is waiting, discard it.
        try:

            self.frame_queue.put_nowait(
                small_frame
            )

        except queue.Full:

            try:
                self.frame_queue.get_nowait()
            except queue.Empty:
                pass

            try:
                self.frame_queue.put_nowait(
                    small_frame
                )
            except queue.Full:
                pass

    # --------------------------------------------------------
    # MAIN LOOP
    # --------------------------------------------------------

    def run(self):

        print("Capture thread started.")

        pipe_period = 1.0 / self.fps_pipe

        while not self.stop_event.is_set():

            # Check commands without blocking.
            self.process_commands()

            if self.stop_event.is_set():
                break

            # -----------------------------------------------
            # CAPTURE
            # -----------------------------------------------

            frame = self.camera.read()

            if frame is None:

                print(
                    "Camera capture failed."
                )

                self.stop_event.set()
                break

            # -----------------------------------------------
            # RECORD ORIGINAL FRAME
            # -----------------------------------------------

            if self.recorder.is_recording():

                self.recorder.write(frame)

            # -----------------------------------------------
            # PIPE
            # -----------------------------------------------

            now = time.monotonic()

            if (
                now - self.last_pipe_time
                >= pipe_period
            ):

                self.send_to_display(frame)

                self.last_pipe_time = now

        # Safety: close recording.
        self.recorder.stop()

        print(
            "Capture thread stopped."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("==============================")
    print(" Camera Capture Application")
    print("==============================")
    print()

    # --------------------------------------------------------
    # Camera
    # --------------------------------------------------------

    camera = Camera(
        CAMERA_INDEX
    )

    try:

        camera.open()

    except Exception as error:

        print(
            f"Camera initialization failed: "
            f"{error}"
        )

        return

    # --------------------------------------------------------
    # Communication
    # --------------------------------------------------------

    frame_queue = queue.Queue(
        maxsize=PIPE_QUEUE_SIZE
    )

    command_queue = queue.Queue()

    stop_event = threading.Event()

    # --------------------------------------------------------
    # Recorder
    # --------------------------------------------------------

    recorder = VideoRecorder(
        RECORD_DIR
    )

    # --------------------------------------------------------
    # Threads
    # --------------------------------------------------------

    display_thread = DisplayThread(
        frame_queue,
        stop_event,
        DEBUG
    )

    capture_thread = CaptureThread(
        camera,
        recorder,
        frame_queue,
        command_queue,
        stop_event,
        FPS_pipe
    )

    command_thread = CommandThread(
        command_queue,
        stop_event
    )

    # --------------------------------------------------------
    # Start threads
    # --------------------------------------------------------

    display_thread.start()
    command_thread.start()
    capture_thread.start()

    try:

        capture_thread.join()

    except KeyboardInterrupt:

        print()
        print("Ctrl+C received.")

        stop_event.set()

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------

    stop_event.set()

    capture_thread.join(
        timeout=2.0
    )

    display_thread.join(
        timeout=2.0
    )

    camera.release()

    print()
    print("Application terminated.")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()