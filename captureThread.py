import cv2
import time
import queue
import threading

from grabacion_db3 import DB3Recorder
from realsense_camera import RealSenseCamera
from displayThread import DisplayThread


# ============================================================
# CONFIGURATION
# ============================================================

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

# ============================================================
# COMMAND THREAD
# ============================================================

class CommandThread(threading.Thread):

    def __init__(
        self,
        command_queue,
        stop_event,
        recorder
    ):

        super().__init__(daemon=True)

        self.command_queue = command_queue
        self.stop_event = stop_event
        self.recorder = recorder

    def ask_category(self):
        valid_categories = "/".join(
            self.recorder.CATEGORIES
        )

        while True:
            print(
                f"Recording class ({valid_categories}): ",
                end="",
                flush=True,
            )
            category = input().strip().upper()

            if category in self.recorder.CATEGORIES:
                return category

            print(
                f"Invalid class. Choose: {valid_categories}."
            )

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

                if command in ("S", "E") and self.recorder.is_recording():
                    command = (command, self.ask_category())

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

            category = None
            if isinstance(command, tuple):
                command, category = command

            if command == "R":

                if not self.recorder.is_recording():

                    self.recorder.start(self.camera)

            elif command == "S":

                self.recorder.stop(category)

            elif command == "E":

                print(
                    "E command received."
                )

                self.recorder.stop(category)

                self.stop_event.set()

                break

    # --------------------------------------------------------
    # SEND FRAME TO DISPLAY
    # --------------------------------------------------------

    def send_to_display(self, frame):

        # Reduce ONLY the visualization copy.
        small_frame = cv2.resize(
            frame.color,
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

            capture = self.camera.read()

            if capture is None:

                print(
                    "Camera capture failed."
                )

                self.stop_event.set()
                break

            # -----------------------------------------------
            # RECORD ORIGINAL FRAME
            # -----------------------------------------------

            if self.recorder.is_recording():

                self.recorder.write(capture)

            # -----------------------------------------------
            # PIPE
            # -----------------------------------------------

            now = time.monotonic()

            if (
                now - self.last_pipe_time
                >= pipe_period
            ):

                self.send_to_display(capture)

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

    camera = RealSenseCamera()

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

    recorder = DB3Recorder(RECORD_DIR)

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
        stop_event,
        recorder,
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