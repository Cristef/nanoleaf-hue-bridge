import json
from pathlib import Path
import tempfile
import unittest

from panel_mapping import channel_colors, MappingFile, validate_mapping


class PanelMappingTests(unittest.TestCase):
    def test_group_means_and_legacy_single_panel(self):
        panels = [{'panelId': 1, 'rgb': [0, 40, 100]},
                  {'panelId': 2, 'rgb': [100, 80, 200]},
                  {'panelId': 3, 'rgb': [200, 120, 0]}]
        self.assertEqual(channel_colors(panels, [0, 1, 2], {'0': [1, 2], '1': 3}),
                         [(0, 50*257, 60*257, 150*257),
                          (1, 200*257, 120*257, 0),
                          (2, 100*257, 80*257, 100*257)])

    def test_validation_rejects_unknown_duplicate_boolean_empty_groups(self):
        for mapping in [{'9': [1]}, {'0': [9]}, {'0': [1, 1]}, {'0': [True]},
                        {'0': []}, {'00': [1]}, {'0': '1'}, []]:
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                validate_mapping(mapping, {0}, {1})

    def test_reload_keeps_last_valid_mapping_and_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'mapping.json'
            mapping = MappingFile(path, [0])
            self.assertEqual(mapping.reload(), {})
            path.write_text(json.dumps({'0': [1, 2]}))
            self.assertEqual(mapping.reload(), {'0': [1, 2]})
            path.write_text('{invalid')
            self.assertEqual(mapping.reload(), {'0': [1, 2]})
            self.assertIsNotNone(mapping.error)
            path.write_text('{}')
            self.assertEqual(mapping.reload(), {})
            self.assertIsNone(mapping.error)


if __name__ == '__main__':
    unittest.main()
