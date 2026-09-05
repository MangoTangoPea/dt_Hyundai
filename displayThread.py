import cv2
import queue
import threading


class DisplayThread(threading.Thread):

    def __init__(self, frame_queue, stop_event, debug=False):
        super().__init__(daemon=True)

        self.frame_queue = frame_queue
        self.stop_event = stop_event
        self.debug = debug

    def run(self):

        print("Display thread started.")

        while not self.stop_event.is_set():

            try:
                frame = self.frame_queue.get(
                    timeout=0.1
                )

            except queue.Empty:
                continue

            if self.debug:

                cv2.imshow(
                    "Camera",
                    frame
                )

                # Necessary for OpenCV GUI events.
                key = cv2.waitKey(1) & 0xFF

                if key == 27:  # ESC
                    print("ESC pressed.")
                    self.stop_event.set()
                    break

        if self.debug:
            cv2.destroyAllWindows()

        print("Display thread stopped.")