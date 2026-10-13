"""Versioned automation API; revocable bearer tokens never authorize portal administration."""
import copy
import hashlib
import hmac
import ipaddress
import json
import secrets
import threading
import time
import uuid
from pathlib import Path
from portal_settings import atomic_json, revision

class AutomationAPI:
    def __init__(self, control):
        self.control=control
        self.path=control.mapping_path.with_name('automation-access.json')
        self.lock=threading.RLock()
        self.failures={}
    def record(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {'id':str(uuid.uuid4()),'tokens':[]}
    def manage(self, payload):
        with self.lock:
            data=self.record(); operation=payload.get('operation','list')
            if operation=='create':
                label=payload.get('label','Home Assistant')
                if not isinstance(label,str) or not 1<=len(label.strip())<=64:raise ValueError('Invalid label')
                if len(data['tokens'])>=16:raise ValueError('Token limit reached')
                secret='nhb_'+secrets.token_urlsafe(32)
                item={'id':secrets.token_hex(8),'label':label.strip(),'created':int(time.time()),'hash':hashlib.sha256(secret.encode()).hexdigest()}
                data['tokens'].append(item);atomic_json(self.path,data)
                return {'token':secret,'id':item['id']}
            if operation=='revoke':
                data['tokens']=[v for v in data['tokens'] if v['id']!=payload.get('id')];atomic_json(self.path,data)
            elif operation!='list':raise ValueError('Invalid operation')
            return {'tokens':[{k:v for k,v in item.items() if k!='hash'} for item in data['tokens']]}
    def authorize(self, handler):
        address=ipaddress.ip_address(handler.client_address[0])
        if not (address.is_private or address.is_loopback) or address.is_multicast:raise PermissionError()
        if handler.headers.get('Origin') is not None:raise PermissionError()
        header=handler.headers.get('Authorization','')
        with self.lock:
            now=time.monotonic();self.failures={k:v for k,v in self.failures.items() if now-v[0]<60}
            key=str(address);entry=self.failures.get(key,(now,0))
            if entry[1]>=10 or len(self.failures)>=256:raise TimeoutError()
            valid=False
            if header.startswith('Bearer nhb_') and len(header)<=128:
                digest=hashlib.sha256(header[7:].encode()).hexdigest()
                valid=any(hmac.compare_digest(digest,item['hash']) for item in self.record()['tokens'])
            if not valid:
                self.failures[key]=(entry[0],entry[1]+1);raise PermissionError()
            self.failures.pop(key,None)
    def state(self):
        c=self.control;state=c.state();config=c.store.read();stream=config['active'];diag=state['diagnostics']
        with self.lock:
            identity=self.record()
            if not self.path.exists():atomic_json(self.path,identity)
        names=list(config['profiles']);matching=[name for name,value in config['profiles'].items() if value==stream]
        reachable=bool(diag.get('virtualReachable'))
        status='unavailable' if not reachable else 'off' if state.get('on') is False else 'streaming' if diag.get('huePhase')=='streaming' else 'error' if diag.get('huePhase') in ('error','busy','failed') else 'waiting'
        return {'apiVersion':1,'id':identity['id'],'name':'Nanoleaf Hue Bridge','version':state['version'],
            'enabled':state.get('on'),'reachable':reachable,'status':status,'syncFramesFresh':bool(state.get('fresh')),
            'brightness':stream['brightness']['global'],'profiles':names,'profile':matching[0] if matching else None,
            'frameAge':diag.get('frameAge'),'capabilities':['sync','brightness','profile'],'revision':revision(config)}
    def command(self,payload):
        if set(payload)!={'command','value'}:raise ValueError('Invalid command')
        c=self.control;command=payload['command'];value=payload['value']
        with c.lock:
            config=c.store.read()
            if command=='sync':c.switch(value)
            elif command=='brightness':
                if type(value) is not int or not 0<=value<=100:raise ValueError('Invalid brightness')
                levels=copy.deepcopy(config['active']['brightness']);levels['global']=value
                c.save_brightness({'configRevision':revision(config),'revision':c.revision(config['active']['brightness']),'brightness':levels})
            elif command=='profile':c.profile({'configRevision':revision(config),'operation':'apply','name':value})
            else:raise ValueError('Unsupported command')
        return self.state()
    def handle(self,handler):
        try:
            self.authorize(handler)
            if handler.command=='GET' and handler.path=='/api/integration/v1/state':return handler.respond(200,self.state())
            if handler.command!='POST' or handler.path!='/api/integration/v1/command':return handler.respond(404,{'error':'Resource not found'})
            if handler.headers.get('Transfer-Encoding') or handler.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError()
            length=int(handler.headers.get('Content-Length','0'))
            if not 0<length<=4096:raise ValueError()
            payload=json.loads(handler.rfile.read(length))
            if not isinstance(payload,dict):raise ValueError()
            return handler.respond(200,self.command(payload))
        except PermissionError:return handler.respond(401,{'error':'Invalid API token'})
        except TimeoutError:return handler.respond(429,{'error':'Too many authentication attempts'})
        except (ValueError,TypeError,KeyError):return handler.respond(400,{'error':'Invalid automation command'})
        except FileExistsError:return handler.respond(409,{'error':'Configuration changed; retry'})
        except Exception:return handler.respond(503,{'error':'Bridge operation unavailable'})
