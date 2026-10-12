import json
from pathlib import Path
import tempfile
import unittest
from brightness import validate, scale, BrightnessFile


class BrightnessTests(unittest.TestCase):
    def test_global_and_individual_factors_preserve_other_channels(self):
        commands = [(0, 65535, 20000, 0), (1, 40000, 10000, 20000)]
        self.assertEqual(scale(commands, {'global': 50, 'channels': {'0': 50}}),
                         [(0, 16384, 5000, 0), (1, 20000, 5000, 10000)])
        self.assertEqual(scale(commands, {'global': 100, 'channels': {}}), commands)
        self.assertEqual(scale(commands, {'global': 0, 'channels': {}}),
                         [(0, 0, 0, 0), (1, 0, 0, 0)])

    def test_invalid_values_and_unknown_channels_rejected(self):
        for value in [True, -1, 101, 12.5, '50']:
            with self.assertRaises(ValueError):
                validate({'global': value, 'channels': {}})
        with self.assertRaises(ValueError):
            validate({'global': 100, 'channels': {'2': 50}}, {0, 1})

    def test_invalid_update_retains_last_valid_brightness(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'brightness.json'
            loaded = BrightnessFile(path, [0])
            self.assertEqual(loaded.reload()['global'], 100)
            path.write_text(json.dumps({'global': 40, 'channels': {'0': 70}}))
            self.assertEqual(loaded.reload()['global'], 40)
            path.write_text('{broken')
            self.assertEqual(loaded.reload()['channels'], {'0': 70})
            self.assertIsNotNone(loaded.error)


if __name__ == '__main__':
    unittest.main()
