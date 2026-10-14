import copy,json,unittest
from unittest.mock import patch
from test_portal import PortalTests
from tv_mapping import positions,project
from portal_settings import active,revision
from portal_discovery import service_arguments
class TVMappingTests(unittest.TestCase):
 def setUp(self):
  self.fixture=PortalTests();self.fixture.setUp();self.control=self.fixture.control
  self.layout={'positionData':[{'panelId':1,'x':0,'y':0},{'panelId':2,'x':10,'y':0},{'panelId':3,'x':0,'y':10}]}
 def tearDown(self):self.fixture.tearDown()
 def test_projection_uses_horizontal_and_vertical_positions(self):
  self.assertEqual(project({'0':{'x':-1,'y':1},'1':{'x':1,'y':-1}},self.layout,{0,1}),{'0':[3],'1':[2]})
 def test_rejects_invalid_positions_and_unplaced_channels(self):
  for value in ({'0':{'x':True,'y':0}},{'0':{'x':float('nan'),'y':0}},{'0':{'x':2,'y':0}},{'../x':{'x':0,'y':0}}):
   with self.assertRaises(ValueError):positions(value)
  with self.assertRaises(ValueError):project({},self.layout,{0})
 def test_preview_never_changes_configuration_and_save_is_atomic(self):
  before=self.control.store.read();data={'positions':{'0':{'x':-1,'y':-1}},'configRevision':revision(before)}
  with patch.object(self.control,'tv_layout',return_value=self.layout):
   self.control.preview_tv(data);self.assertEqual(self.control.store.read(),before)
   self.control.save_tv(data)
   after=self.control.store.read();self.assertEqual(after['active']['tvPositions'],data['positions'])
   self.assertEqual(after['active']['brightness'],before['active']['brightness'])
   with self.assertRaises(FileExistsError):self.control.save_tv(data)
   self.assertEqual(self.control.store.read(),after)
 def test_positions_roundtrip_profiles_and_clear_on_area_change(self):
  value=self.control.store.read();value['active']['tvPositions']={'0':{'x':.5,'y':0}};active(value['active'])
  from portal_settings import atomic_json
  atomic_json(self.control.store.path,value)
  self.control.profile({'operation':'save','name':'TV','configRevision':revision(value)})
  self.assertEqual(self.control.store.read()['profiles']['TV']['tvPositions'],{'0':{'x':.5,'y':0}})
 def test_discovery_only_advertises_id_and_api_version(self):
  identity=self.control.automation.ensure_identity();args=service_arguments('10.23.45.20',8080,identity)
  self.assertIn('_nanoleaf-hue._tcp',args);self.assertEqual(args[-2:],['id='+identity,'api=1'])
  self.assertNotIn('token',' '.join(args))
 def test_automation_diagnostics_exclude_identifiers_and_profile_names(self):
  result=self.control.automation.diagnostic_data();self.assertNotIn('id',result);self.assertNotIn('profile',result);self.assertNotIn('profiles',result);self.assertNotIn('csrf',result)
