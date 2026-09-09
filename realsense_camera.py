from dataclasses import dataclass

import numpy as np
import pyrealsense2 as rs


@dataclass
class RealSenseFrame:
    color: np.ndarray
    depth: np.ndarray
    infrared_left: np.ndarray
    infrared_right: np.ndarray
    timestamp_ms: float
    metadata: dict


class RealSenseCamera:
    """Intel RealSense D435 using synchronized color/depth streams."""

    def __init__(
        self,
        color_size=(1280, 720),
        depth_size=(1280, 720),
        fps=30,
    ):
        self.color_size = color_size
        self.depth_size = depth_size
        self.fps = float(fps)
        self.pipeline = None
        self.profile = None
        self.align = None
        self.width = color_size[0]
        self.height = color_size[1]
        self.depth_scale = 0.001

    def open(self):
        print("Opening RealSense D435...")

        self.pipeline = rs.pipeline()
        config = rs.config()
        config.enable_stream(
            rs.stream.color,
            self.color_size[0], self.color_size[1],
            rs.format.bgr8, int(self.fps),
        )
        config.enable_stream(
            rs.stream.depth,
            self.depth_size[0], self.depth_size[1],
            rs.format.z16, int(self.fps),
        )
        config.enable_stream(
            rs.stream.infrared,
            1,
            self.depth_size[0], self.depth_size[1],
            rs.format.y8, int(self.fps),
        )
        config.enable_stream(
            rs.stream.infrared,
            2,
            self.depth_size[0], self.depth_size[1],
            rs.format.y8, int(self.fps),
        )

        try:
            self.profile = self.pipeline.start(config)
        except Exception:
            self.pipeline = None
            raise

        self.align = rs.align(rs.stream.color)
        depth_sensor = self.profile.get_device().first_depth_sensor()
        self.depth_scale = depth_sensor.get_depth_scale()
        print(
            f"RealSense D435: {self.width}x{self.height} "
            f"@ {self.fps:.2f} FPS, depth scale={self.depth_scale}"
        )

    def read(self):
        if self.pipeline is None:
            raise RuntimeError("RealSense camera is not open")

        frames = self.pipeline.wait_for_frames()
        aligned_frames = self.align.process(frames)
        color_frame = aligned_frames.get_color_frame()
        depth_frame = aligned_frames.get_depth_frame()
        infrared_left = frames.get_infrared_frame(1)
        infrared_right = frames.get_infrared_frame(2)

        if not all((color_frame, depth_frame, infrared_left, infrared_right)):
            return None

        return RealSenseFrame(
            color=np.asanyarray(color_frame.get_data()),
            depth=np.asanyarray(depth_frame.get_data()),
            infrared_left=np.asanyarray(infrared_left.get_data()),
            infrared_right=np.asanyarray(infrared_right.get_data()),
            timestamp_ms=frames.get_timestamp(),
            metadata={
                "depth_scale": self.depth_scale,
                "frame_number": frames.get_frame_number(),
            },
        )

    def release(self):
        if self.pipeline is not None:
            self.pipeline.stop()
            self.pipeline = None
            self.profile = None

        print("RealSense camera released.")