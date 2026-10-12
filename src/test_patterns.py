"""Bounded temporary Hue patterns, independent of 4D frames."""
import colorsys
def commands(test,ids,now,area):
    if not isinstance(test,dict) or test.get('area')!=area or not 0<test.get('expires',0)-now<=60:return None
    if test.get('mode') not in ('solid','rainbow','identify'):return None
    selected=test.get('channel')
    rgb=test.get('rgb',[255,0,0])
    if test['mode']=='rainbow':rgb=[round(c*255) for c in colorsys.hsv_to_rgb(((now-test['started'])/6)%1,1,1)]
    if test['mode']=='identify':rgb=[255,255,255]
    return [(ch,*(v*257 for v in (rgb if selected is None or ch==selected else [0,0,0]))) for ch in ids]
