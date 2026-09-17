import unittest
from backend.app.database import init_db
from backend.app.vision.seat_mapper import SeatMapper

class TestSeatMapper(unittest.TestCase):
    def setUp(self):
        init_db()
        self.seat_mapper = SeatMapper()

    def test_seat_mapping(self):
        # Seat A1 normalized coords approx: [0.05, 0.15, 0.115, 0.29]
        seat = self.seat_mapper.map_bbox_to_seat([0.06, 0.16, 0.10, 0.28])
        self.assertIsNotNone(seat)
        self.assertEqual(seat['seat_id'], 'A1')

    def test_format_seat_label(self):
        seat = {"seat_id": "C14"}
        label = self.seat_mapper.format_seat_label(seat)
        self.assertEqual(label, "Seat C14")

if __name__ == '__main__':
    unittest.main()
