import unittest
import numpy as np
from backend.app.vision.detector import ObjectDetectionEngine

class TestDetector(unittest.TestCase):
    def setUp(self):
        self.detector = ObjectDetectionEngine()

    def test_detector_empty_frame(self):
        detections = self.detector.detect(None)
        self.assertEqual(detections, [])

    def test_detector_blank_frame(self):
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = self.detector.detect(blank_frame)
        self.assertIsInstance(detections, list)

if __name__ == '__main__':
    unittest.main()
