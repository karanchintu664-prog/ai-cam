import unittest
import time
from backend.app.vision.tracker import TrackedObject
from backend.app.vision.behavior_analyzer import BehaviorAnalyzer

class TestSuspicionScoring(unittest.TestCase):
    def setUp(self):
        self.analyzer = BehaviorAnalyzer(alert_threshold=70.0)

    def test_short_duration_casual_use(self):
        tracked = TrackedObject(track_id=1, bbox_norm=[0.5, 0.5, 0.6, 0.7], class_name="cell phone", confidence=0.85)
        # Short duration (0.5s)
        analysis = self.analyzer.analyze_tracked_phone(tracked, "Seat B4")
        self.assertFalse(analysis["is_suspicious"])
        self.assertLess(analysis["suspicion_score"], 70.0)

    def test_long_duration_filming_use(self):
        tracked = TrackedObject(track_id=2, bbox_norm=[0.5, 0.5, 0.6, 0.7], class_name="cell phone", confidence=0.90)
        # Simulate 4.5 seconds duration
        tracked.first_seen = time.time() - 4.5
        analysis = self.analyzer.analyze_tracked_phone(tracked, "Seat C14")
        self.assertTrue(analysis["is_suspicious"])
        self.assertGreaterEqual(analysis["suspicion_score"], 70.0)

    def test_casual_phone_check_below_threshold(self):
        tracked = TrackedObject(track_id=3, bbox_norm=[0.5, 0.5, 0.6, 0.7], class_name="cell phone", confidence=0.85)
        # Simulate 1.8 seconds duration (notification check)
        tracked.first_seen = time.time() - 1.8
        analysis = self.analyzer.analyze_tracked_phone(tracked, "Seat B4")
        self.assertFalse(analysis["is_suspicious"])
        self.assertLess(analysis["suspicion_score"], 70.0)

if __name__ == '__main__':
    unittest.main()
