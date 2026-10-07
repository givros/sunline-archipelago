import bpy,sys,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
import settlements as S
out=[]
for district,pos in [('STILT_NORTH',(-18.7771757816,379.95535725346)),('STILT_NORTH',(-18.62,380.04)),('STILT_WEST',(-313.3,220.58)),('STILT_WEST',(-313.239,220.8106))]:
 hits=[]
 for ob in bpy.data.objects:
  if ob.type!='MESH' or not ob.get('walkable'):continue
  if not(ob.name.startswith(district) or ob.name.startswith('REG_') or ob.name.startswith('Palm_Crescent_public')):continue
  inv=ob.matrix_world.inverted();p=inv@Vector((*pos,150));ray=inv.to_3x3()@Vector((0,0,-1));hit,v,n,i=ob.ray_cast(p,ray)
  if hit:hits.append([ob.name,(ob.matrix_world@v).z])
 out.append({'district':district,'point':pos,'terrain':S._support(*pos),'hits':hits})
print(json.dumps(out,indent=2));(ROOT/'comparisons/architecture_audit/navigation_surface_probe.json').write_text(json.dumps(out,indent=2))
