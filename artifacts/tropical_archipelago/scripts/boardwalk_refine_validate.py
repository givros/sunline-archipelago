import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
from refine_architecture import fix_boardwalk_surface_ownership,fix_parish_spires
from core import camera,render
fix_parish_spires();report=fix_boardwalk_surface_ownership()
parent=bpy.data.objects['STILT_LAGOON_HOUSE_06'];base=parent.location.copy();s=parent.scale.x
for view,offset,aim in [('aerial',Vector((0,-34,44)),Vector((0,0,4))),('rear',Vector((-22,29,14)),Vector((0,0,5)))]:
 if view!='aerial':offset=parent.rotation_euler.to_matrix()@offset
 target=base+aim*s;loc=target+(offset-aim)*s*3
 cam=camera('OWNERSHIP_'+view,loc,target,ortho=31*s)
 render(cam,'boardwalk_owned_'+view,700,525,16)
print('BOARDWALK_OWNERSHIP_RENDER_VALIDATED',flush=True)
