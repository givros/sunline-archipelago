import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import settlements as S
from layout import xy
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'checkpoints/10_scene.blend'))
out={}
for name,p in [('STILT_NORTHWEST_HOUSE_03',(-189.19822,346.11426,3.2)),('STILT_CORAL_HOUSE_06',(375.2837,-266.27505,3.2)),('VILLA_049',(-312.65,231.24,18.95))]:
 ob=bpy.data.objects[name];out[name]={'location':list(ob.location),'angle':ob.rotation_euler.z,'point_local':list(ob.matrix_world.inverted()@Vector(p)),'children':[x.name for x in ob.children]}
out['sites']=[]
for px in [(179,801),(268,842),(353,842),(215,275),(217,288),(224,276),(907,462)]:
 x,y=xy(px);out['sites'].append({'px':px,'xyz':[x,y,S._support(x,y)],'ground':[S._support(x+u,y+v) for u in [-7,0,7] for v in [-8,0,8]]})
(ROOT/'comparisons/architecture_audit/probe.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out))
