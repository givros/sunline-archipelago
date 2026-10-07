"""Read-only matching-angle hero evidence; saves only rendered images."""
import bpy,sys,math,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core import camera,material,mesh
OUT=ROOT/'comparisons/architecture_audit';OUT.mkdir(parents=True,exist_ok=True)
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
scene.frame_set(1);scene.render.resolution_x=700;scene.render.resolution_y=525;scene.render.resolution_percentage=100;scene.cycles.samples=12
original_hidden={c.name:c.hide_render for c in bpy.context.scene.collection.children}
for family,asset in [('villa','VILLA_002'),('stilt','STILT_LAGOON_HOUSE_06')]:
 parent=bpy.data.objects[asset];base=parent.location.copy();s=parent.scale.x
 angles=[('aerial',Vector((0,-34,44)),Vector((0,0,4))),('front',Vector((22,-31,15)),Vector((0,0,5))),('rear',Vector((-22,29,14)),Vector((0,0,5)))]
 for view,offset,aim in angles:
  if view!='aerial':offset=parent.rotation_euler.to_matrix()@offset
  target=base+aim*s
  cam=camera('EVIDENCE_'+family+'_'+view,target+(offset-aim)*s*3,target,ortho=31*s)
  scene.camera=cam
  for isolated in [False,True]:
   for c in bpy.context.scene.collection.children:
    value=(c.name!=asset) if isolated else original_hidden.get(c.name,False)
    if c.hide_render!=value:c.hide_render=value
   floor=None
   if isolated:
    z=base.z-.05 if family=='villa' else -.15
    floor=mesh('Temporary neutral asset context',[(base.x-60,base.y-60,z),(base.x+60,base.y-60,z),(base.x+60,base.y+60,z),(base.x-60,base.y+60,z)],[(0,1,2,3)],material('Evidence base',(.26,.35,.34) if family=='stilt' else (.48,.49,.43),.88))
   scene.render.filepath=str(OUT/f'{family}_{view}_{"isolated" if isolated else "integrated"}.png')
   bpy.ops.render.render(write_still=True)
   if floor:bpy.data.objects.remove(floor,do_unlink=True)
for c in bpy.context.scene.collection.children:
 if c.name in original_hidden:c.hide_render=original_hidden[c.name]
print('ARCHITECTURE_HERO_EVIDENCE_COMPLETE',flush=True)
