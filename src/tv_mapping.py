"""TV-relative light positions and assignment to the current virtual panel layout."""
import math

def positions(value):
    if not isinstance(value,dict) or len(value)>256:raise ValueError('Invalid TV positions')
    result={}
    for key,point in value.items():
        if not isinstance(key,str) or not key.isdigit() or str(int(key))!=key or not 0<=int(key)<=255:raise ValueError('Invalid channel')
        if not isinstance(point,dict) or set(point)!={'x','y'}:raise ValueError('Invalid position')
        if any(type(v) not in (int,float) or not math.isfinite(v) or not -1<=v<=1 for v in point.values()):raise ValueError('Invalid coordinates')
        result[key]={'x':point['x'],'y':point['y']}
    return result

def project(value,layout,channels):
    value=positions(value)
    if set(value)!={str(c) for c in channels}:raise ValueError('Place every light in this area')
    panels=layout.get('positionData',[])
    panels=[p for p in panels if type(p.get('panelId')) is int and p['panelId']>0 and all(type(p.get(k)) in (int,float) and math.isfinite(p[k]) for k in ('x','y')) and p.get('shapeType')!=12]
    if not panels:raise ValueError('Virtual panel layout unavailable')
    lo={k:min(p[k] for p in panels) for k in ('x','y')};hi={k:max(p[k] for p in panels) for k in ('x','y')}
    points=[(p['panelId'],{k:2*(p[k]-lo[k])/(hi[k]-lo[k])-1 if hi[k]!=lo[k] else 0 for k in ('x','y')}) for p in panels]
    return {key:[min(points,key=lambda p:((p[1]['x']-point['x'])**2+(p[1]['y']-point['y'])**2,p[0]))[0]] for key,point in value.items()}

class TVMapping:
    def tv_layout(self):
        import json,urllib.request
        auth=json.loads(self.control_auth.read_text())
        with urllib.request.urlopen(self.virtual+'/api/v1/'+auth['token']+'/panelLayout/layout',timeout=3) as response:return json.load(response)
    def preview_tv(self,payload):
        stream=self.store.read()['active'];channels=self.channels_for(stream)
        mapping=project(payload.get('positions'),self.tv_layout(),channels)
        return {'mapping':mapping,'positions':positions(payload['positions'])}
    def save_tv(self,payload):
        preview=self.preview_tv(payload)
        def modify(config):
            config['active']['mapping']=preview['mapping'];config['active']['tvPositions']=preview['positions']
            config['active']=self.validate_available(config['active'])
        result=self.change(payload,modify)
        result.update(preview);result['revision']=self.revision(preview['mapping'])
        return result
