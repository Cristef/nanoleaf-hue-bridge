"""Tests use documentation-only addresses and never access physical devices."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='test-config-', dir=root / 'tests') as folder:
    config = Path(folder) / 'config.json'
    config.write_text((root / 'config.example.json').read_text())
    os.environ['NH_CONFIG'] = str(config)
    sys.path.insert(0, str(root / 'src'))
    suite = unittest.defaultTestLoader.discover(str(root / 'tests'), pattern='test_*.py')
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
