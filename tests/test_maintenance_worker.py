import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import maintenance_worker as worker

class WorkerTests(unittest.TestCase):
    def exercise(self,fail):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);root=path/'code';root.mkdir();state=path/'state';state.mkdir();runtime=path/'run';runtime.mkdir();updates=state/'updates';updates.mkdir()
            (root/'portal_control.py').write_text('old code');(state/'portal-settings.json').write_text('old settings')
            archive=updates/'candidate.tar.gz'
            with tarfile.open(archive,'w:gz') as tar:
                item=tarfile.TarInfo('portal_control.py');item.size=8;tar.addfile(item,io.BytesIO(b'new code'))
            (updates/'candidate.json').write_text(json.dumps({'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'version':'test'}))
            with patch.object(worker,'ROOT',root),patch.object(worker,'STATE',state),patch.object(worker,'RUNTIME',runtime),patch.object(worker,'run'),patch.object(worker,'restart',side_effect=[RuntimeError('synthetic failure'),None] if fail else [None]):
                worker.apply_update()
                if fail:
                    self.assertEqual((root/'portal_control.py').read_text(),'old code');self.assertEqual(json.loads((runtime/'maintenance-status.json').read_text())['phase'],'recovered')
                else:
                    self.assertEqual((root/'portal_control.py').read_text(),'new code');self.assertTrue((updates/'last-backup.json').exists());self.assertFalse((updates/'candidate.json').exists())
            self.assertEqual((state/'portal-settings.json').read_text(),'old settings')
    def test_verified_update_backs_up_and_preserves_settings(self):self.exercise(False)
    def test_failed_update_restores_previous_code_and_settings(self):self.exercise(True)
