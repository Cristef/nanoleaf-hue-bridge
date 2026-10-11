import unittest
from hue_sync import channel_colors


class MappingTests(unittest.TestCase):
    def test_mean_and_explicit_panel_mapping(self):
        panels = [{'panelId': 1, 'rgb': [255, 0, 20]},
                  {'panelId': 2, 'rgb': [0, 100, 40]}]
        self.assertEqual(channel_colors(panels, [0, 3], {'3': 2}),
                         [(0, 128*257, 50*257, 30*257), (3, 0, 100*257, 40*257)])

    def test_missing_mapped_panel_and_empty_frames_fail(self):
        with self.assertRaises(ValueError):
            channel_colors([], [1])
        with self.assertRaises(ValueError):
            channel_colors([{'panelId': 1, 'rgb': [0, 0, 0]}], [0], {'0': 2})


if __name__ == '__main__':
    unittest.main()
