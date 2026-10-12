import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch
from advanced_portal import channel_settings, diagnose, suggest_mapping
from color_response import ColorResponse
from portal_settings import validate,TUNING
from test_portal import PortalTests,configuration
from test_patterns import commands
from maintenance_worker import validate_bundle

class AdvancedTests(unittest.TestCase):
    def test_optional_overrides_preserve_old_settings_and_profile_roundtrip(self):
        old=configuration();self.assertEqual(validate(old),old)
        new=copy.deepcopy(old);new['active']['channelSettings']={'0':{'saturation':0,'redGain':80}}
        self.assertEqual(validate(new),new)
        new['active']['channelSettings']['0']['redGain']=201
        with self.assertRaises(ValueError):validate(new)

    def test_per_light_saturation_gain_and_independent_smoothing(self):
        processor=ColorResponse();levels={'global':100,'channels':{}}
        result=processor.process([(0,65535,0,0),(1,65535,0,0)],TUNING,levels,0,{'0':{'saturation':0},'1':{'redGain':50}})
        self.assertEqual(result[0],(0,65535,65535,65535));self.assertEqual(result[1],(1,32768,0,0))
        with self.assertRaises(ValueError):channel_settings({'true':{}})

    def test_mapping_uses_positions_and_never_silently_invents_missing_positions(self):
        layout={'positionData':[{'panelId':1,'x':0,'y':0},{'panelId':2,'x':100,'y':100}]}
        channels=[{'id':0,'position':{'x':-1,'z':-1}},{'id':1,'position':{'x':1,'z':1}},{'id':2}]
        result=suggest_mapping(channels,layout)
        self.assertEqual(result['mapping'],{'0':[1],'1':[2]});self.assertEqual(result['missingChannels'],[2])
        self.assertEqual(suggest_mapping([channels[0]],layout,flip=True)['mapping'],{'0':[1]})

    def test_relative_projection_separates_close_lights_and_mirror_swaps(self):
        layout={'positionData':[{'panelId':1,'x':0,'y':0},{'panelId':2,'x':50,'y':0},{'panelId':3,'x':100,'y':0}]}
        channels=[{'id':0,'position':{'x':-.00362,'z':1}},{'id':1,'position':{'x':-.16717,'z':1}}]
        self.assertEqual(suggest_mapping(channels,layout)['mapping'],{'0':[2],'1':[2]})
        self.assertEqual(suggest_mapping(channels,layout,spread=True)['mapping'],{'0':[3],'1':[1]})
        self.assertEqual(suggest_mapping(channels,layout,spread=True,flip=True)['mapping'],{'0':[1],'1':[3]})
        channels[1]['position']=dict(channels[0]['position'])
        result=suggest_mapping(channels,layout,spread=True)
        self.assertEqual(result['mapping'],{'0':[2],'1':[2]})
        self.assertIn('identical',result['message'])

    def test_diagnostics_distinguish_off_no_data_busy_and_mapping(self):
        now=time.time();area={'channels':[{'id':0}]};health={'on':False,'syncPlus':{'lastFrameAge':.1}}
        self.assertEqual(diagnose(health,{},area,now)['code'],'off')
        health['on']=True;health['syncPlus']['lastFrameAge']=10
        self.assertEqual(diagnose(health,{},area,now)['code'],'no-sync-data')
        health['syncPlus']['lastFrameAge']=.1
        self.assertEqual(diagnose(health,{'phase':'busy','time':now},area,now)['code'],'hue-busy')
        self.assertEqual(diagnose(health,{'time':now,'mappingError':'Invalid'},area,now)['code'],'mapping-error')

    def test_test_patterns_expire_and_target_only_selected_light(self):
        test={'mode':'identify','area':'area','channel':1,'started':0,'expires':15}
        self.assertEqual(commands(test,[0,1],1,'area'),[(0,0,0,0),(1,65535,65535,65535)])
        self.assertIsNone(commands(test,[0,1],16,'area'));self.assertIsNone(commands(test,[0,1],1,'other'))

    def test_update_archive_rejects_checksum_symlinks_and_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'update.tar.gz'
            for name in ('web/advanced.js','../private','portal_auth.py'):
                with tarfile.open(path,'w:gz') as tar:
                    item=tarfile.TarInfo(name);item.size=1
                    if name=='portal_auth.py':item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd';item.size=0;tar.addfile(item)
                    else:tar.addfile(item,io.BytesIO(b'x'))
                manifest={'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
                if name=='web/advanced.js':self.assertEqual(validate_bundle(path,manifest),{name:b'x'})
                else:
                    with self.assertRaises(ValueError):validate_bundle(path,manifest)
                with self.assertRaises(ValueError):validate_bundle(path,{'sha256':'wrong'})

class AdvancedControlTests(PortalTests):
    def test_temporary_test_does_not_change_switch_profiles_or_mapping(self):
        before=self.control.store.read()
        self.control.test_colors({'mode':'solid','seconds':1,'rgb':[0,255,0]})
        self.assertEqual(self.control.store.read(),before)
        self.assertFalse(self.control.health_cache['on'])
        self.control.test_colors({'operation':'stop'})
        self.assertEqual(json.loads((self.path/'test-mode.json').read_text())['expires'],0)
    def test_channel_overrides_check_revision_and_unknown_channel(self):
        with self.assertRaises(ValueError):self.control.save_channels(self.payload(channelSettings={'9':{'saturation':0}}))
        self.control.save_channels(self.payload(channelSettings={'0':{'redGain':70}}))
        self.assertEqual(self.control.store.read()['active']['channelSettings']['0']['redGain'],70)
