"""Local experimental portal features; never publishes or changes HomeKit."""
import asyncio
import copy
import ipaddress
import json
import math
import os
from pathlib import Path
import subprocess
import time
import urllib.request
from portal_settings import atomic_json, revision, TUNING

VERSION='4.3.0'
SOURCE=Path('/var/lib/nanoleaf-hue-sync/source.json')

def channel_settings(value):
    if not isinstance(value,dict) or len(value)>256: raise ValueError('Invalid per-light settings')
    result={}
    limits={'smoothingMs':2000,'saturation':200,'blackThreshold':255,'redGain':200,'greenGain':200,'blueGain':200}
    for key,settings in value.items():
        if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or not 0<=int(key)<=255: raise ValueError('Invalid channel')
        if not isinstance(settings,dict) or set(settings)-set(limits): raise ValueError('Invalid channel fields')
        if any(type(v) is not int or not 0<=v<=limits[k] for k,v in settings.items()): raise ValueError('Invalid channel value')
        result[key]=dict(settings)
    return result

def suggest_mapping(channels, layout, horizontal='x', vertical='z', flip=False, spread=False):
    panels=layout.get('positionData',[])
    if not panels: raise ValueError('Virtual layout unavailable')
    if horizontal not in ('x','y') or vertical not in ('y','z') or horizontal==vertical: raise ValueError('Invalid axes')
    def normalize(v,lo,hi): return (v-lo)/(hi-lo) if hi!=lo else .5
    xmin,xmax=min(p['x'] for p in panels),max(p['x'] for p in panels)
    ymin,ymax=min(p['y'] for p in panels),max(p['y'] for p in panels)
    points=[(p['panelId'],normalize(p['x'],xmin,xmax),normalize(p['y'],ymin,ymax)) for p in panels]
    valid_positions=[ch['position'] for ch in channels if isinstance(ch.get('position'),dict) and all(type(ch['position'].get(k)) in (int,float) and math.isfinite(ch['position'][k]) for k in (horizontal,vertical))]
    bounds={k:(min(p[k] for p in valid_positions),max(p[k] for p in valid_positions)) for k in (horizontal,vertical)} if valid_positions else {}
    mapping={}; missing=[]
    for ch in channels:
        pos=ch.get('position')
        if not isinstance(pos,dict) or any(type(pos.get(k)) not in (int,float) or not math.isfinite(pos[k]) for k in (horizontal,vertical)):
            missing.append(ch['id']);continue
        x=(max(-1,min(1,pos[horizontal]))+1)/2
        y=(max(-1,min(1,pos[vertical]))+1)/2
        if spread:
            x=normalize(pos[horizontal],*bounds[horizontal])
            y=normalize(pos[vertical],*bounds[vertical])
        if flip:x=1-x
        pid=min(points,key=lambda p:(p[1]-x)**2+(p[2]-y)**2)[0]
        mapping[str(ch['id'])]=[pid]
    if not mapping:raise ValueError('Hue channel positions unavailable')
    distinct=len({ids[0] for ids in mapping.values()})
    message=f'Suggested {distinct} panel(s) for {len(mapping)} light(s). '
    message+='Relative projection expands the light positions across the panel layout. ' if spread else 'Absolute projection uses Hue room coordinates. '
    if distinct<len(mapping):message+='Some lights share a panel because their projected positions are close or identical. '
    return {'mapping':mapping,'missingChannels':missing,'message':message+'Review before saving; try another axis or mirror.'}

def diagnose(health,hue,area,now):
    stream=health.get('syncPlus',{});stream=stream if isinstance(stream,dict) else {}
    age=stream.get('lastFrameAge');fresh=type(age) in (int,float) and age<3
    recent=now-hue.get('time',0)<5
    if not health:return {'code':'receiver-unavailable','message':'Virtual receiver unavailable. Check its service.','severity':'error'}
    if health.get('on') is False:return {'code':'off','message':'Virtual device is off. Turn synchronization on to send colors to Hue.','severity':'info'}
    if not fresh:return {'code':'no-sync-data','message':'No recent 4D frames. Check Screen Mirror, Desktop Sync+ selection, source IP and Wi-Fi isolation.','severity':'warning'}
    if not area.get('channels'):return {'code':'no-hue-area','message':'Select a paired Hue Entertainment area with lights.','severity':'warning'}
    if recent and hue.get('mappingError'):return {'code':'mapping-error','message':hue['mappingError'],'severity':'warning'}
    if recent and hue.get('phase')=='busy':return {'code':'hue-busy','message':'Another app is using this Hue area. Stop its stream before retrying.','severity':'warning'}
    if recent and hue.get('phase')=='streaming':return {'code':'streaming','message':'4D frames are arriving and Hue output is active.','severity':'ok'}
    return {'code':'hue-not-streaming','message':'4D frames are arriving, but Hue output is not active. Check Hue pairing and competing streams.','severity':'warning'}

class AdvancedControl:
    def advanced_state(self,result):
        now=time.time();health=self.health_cache
        hue=__import__('control_panel_v2').read_json(self.runtime/'hue-status.json',{})
        test=__import__('control_panel_v2').read_json(self.runtime/'test-mode.json',{})
        stream=health.get('syncPlus',{});stream=stream if isinstance(stream,dict) else {}
        # Receiver telemetry remains available while the virtual switch is off.
        if stream.get('panels'):
            result['panels']=[{'panelId':int(k),'rgb':v} for k,v in stream['panels'].items()]
            result['fresh']=type(stream.get('lastFrameAge')) in (int,float) and stream['lastFrameAge']<3
        result['version']=VERSION
        result['source']=json.loads(SOURCE.read_text()) if SOURCE.exists() else {'ip':__import__('config').CONFIG.get('source_ip','')}
        result['diagnosticReport']=diagnose(health,hue,result['area'],now)
        result['testMode']={'active':now<test.get('expires',0),'secondsRemaining':max(0,math.ceil(test.get('expires',0)-now)),'mode':test.get('mode','none')}
        if result['testMode']['active']:
            result['diagnosticReport']={'code':'testing','severity':'info','message':'Temporary test colors are active. Normal operation resumes automatically.'}
            result['phase']='testing'
            result['diagnostics']['huePhase']=hue.get('phase','waiting') if now-hue.get('time',0)<5 else 'waiting'
        result['setupChecks']=[{'label':'Virtual receiver reachable','ok':bool(health)},
            {'label':'Desktop API client paired','ok':health.get('pairing',{}).get('apiPaired',False)},
            {'label':'4D Sync+ frames arriving','ok':result['fresh']},
            {'label':'Hue area with lights selected','ok':bool(result['area']['channels'])}]
        result['rollbackAvailable']=(self.mapping_path.parent/'updates'/'last-backup.json').exists()
        result['updates']=getattr(self,'release_info',{'phase':'idle'})
        result['maintenance']=__import__('control_panel_v2').read_json(self.runtime/'maintenance-status.json',{'phase':'idle'})
        result['stagedUpdate']=__import__('control_panel_v2').read_json(self.mapping_path.parent/'updates'/'candidate.json',None)
        return result

    def save_channels(self,payload):
        settings=channel_settings(payload.get('channelSettings'))
        if set(settings)-{str(c['id']) for c in self.state()['area']['channels']}:raise ValueError('Unknown channel')
        return self.change(payload,lambda c:c['active'].update(channelSettings=settings))

    def automatic_mapping(self,payload):
        state=self.state()
        auth=json.loads(self.control_auth.read_text())
        with urllib.request.urlopen(self.virtual+'/api/v1/'+auth['token']+'/panelLayout/layout',timeout=3) as response:layout=json.load(response)
        if type(payload.get('spread',False)) is not bool:raise ValueError('Invalid projection')
        return suggest_mapping(state['area']['channels'],layout,payload.get('horizontal','x'),payload.get('vertical','z'),payload.get('flip',False),payload.get('spread',False))

    def test_colors(self,payload):
        if payload.get('operation')=='stop':
            atomic_json(self.runtime/'test-mode.json',{'expires':0});return {'status':'stopped'}
        mode=payload.get('mode');duration=payload.get('seconds',20);channel=payload.get('channel')
        if mode not in ('solid','rainbow','identify') or type(duration) is not int or not 1<=duration<=60:raise ValueError('Invalid test')
        state=self.state();ids={c['id'] for c in state['area']['channels']}
        if not ids or (channel is not None and (type(channel) is not int or channel not in ids)):raise ValueError('Invalid light')
        if mode=='identify' and channel is None:raise ValueError('Select one light to identify')
        rgb=payload.get('rgb',[255,0,0])
        if not isinstance(rgb,list) or len(rgb)!=3 or any(type(v) is not int or not 0<=v<=255 for v in rgb):raise ValueError('Invalid RGB')
        atomic_json(self.runtime/'test-mode.json',{'expires':time.time()+duration,'started':time.time(),'mode':mode,'rgb':rgb,'channel':channel,'area':state['activeSettings']['area']})
        return {'status':'started','seconds':duration}

    def guided_discovery(self,payload):
        result=subprocess.run(['avahi-browse','-rtp','_nanoleafapi._tcp'],capture_output=True,text=True,timeout=15)
        devices=[];network=ipaddress.ip_network(os.environ.get('PANEL_NETWORK',os.environ['PANEL_BIND']+'/24'),strict=False)
        for line in result.stdout.splitlines():
            fields=line.split(';')
            if len(fields)>=10 and fields[0]=='=' and fields[2]=='IPv4' and 'md=NL69' in fields[9]:
                try:
                    if ipaddress.ip_address(fields[7]) not in network:continue
                except ValueError:continue
                item={'name':fields[3],'ip':fields[7]}
                if item not in devices:devices.append(item)
        return {'devices':devices}

    def save_source(self,payload):
        value=self.allowed_bridge(payload.get('ip'))
        if value==self.store.read()['active']['bridge']:raise ValueError('4D and Hue must differ')
        if self.store.read() and payload.get('configRevision')!=revision(self.store.read()):raise FileExistsError('Reload settings first')
        atomic_json(SOURCE,{'ip':value})
        atomic_json(self.runtime/'maintenance-request.json',{'action':'source','time':time.time()})
        return {'status':'queued'}

    def desktop_pairing(self,payload):
        auth=json.loads(self.control_auth.read_text())
        request=urllib.request.Request(self.virtual+'/api/v1/'+auth['token']+'/pairing',data=b'{}',headers={'Content-Type':'application/json'},method='POST')
        with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)

    def check_update(self,payload):
        self.release_info={'phase':'checking'}
        def check():
            try:
                req=urllib.request.Request('https://api.github.com/repos/Cristef/nanoleaf-hue-bridge/releases?per_page=5',headers={'User-Agent':'Nanoleaf-Hue-Bridge'})
                with urllib.request.urlopen(req,timeout=10) as response:items=json.load(response)
                release=next(r for r in items if not r['draft'])
                self.release_info={'phase':'ready','version':release['tag_name'],'url':release['html_url'],'notes':release['body'][:12000],
                    'message':'Use the tagged update.sh installer for a complete release upgrade; local staged bundles are applied separately.'}
            except Exception:self.release_info={'phase':'error','message':'Unable to check GitHub. Try again later.'}
        __import__('threading').Thread(target=check,daemon=True).start()
        return {'status':'checking'}

    def maintenance_action(self,payload):
        action=payload.get('action')
        if action not in ('update','rollback'):raise ValueError('Invalid action')
        current=__import__('control_panel_v2').read_json(self.runtime/'maintenance-status.json',{})
        if current.get('phase') in ('backing-up','installing','rolling-back'):raise FileExistsError('Maintenance in progress')
        if action=='update' and not (self.mapping_path.parent/'updates'/'candidate.json').exists():raise ValueError('No compatible local update staged')
        atomic_json(self.runtime/'maintenance-request.json',{'action':action,'time':time.time()})
        return {'status':'queued'}
