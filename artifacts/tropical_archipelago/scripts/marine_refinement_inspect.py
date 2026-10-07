"""Independent unsaved scene check of the marine refinement."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from refine_marine import apply_refinements
from core import camera
OUT=HERE.parent/'renders'/'marine_validation'
report=apply_refinements(persist=False,report_path=OUT/'refinement_trial.json')
s=bpy.context.scene;s.frame_set(1);s.render.engine='CYCLES';s.cycles.samples=20;s.cycles.use_denoising=True;s.render.resolution_percentage=100;s.render.resolution_x=1500;s.render.resolution_y=1100
for name,index,offset,target,scale in [('moored_yacht_refined',6,(15,-20,11),(0,0,1.1),28),('speedboat_wake_refined',2,(14,-22,17),(-8,0,1),44)]:
    o=next(o for o in s.objects if o.name.startswith(f'BOAT_{index:02d}_') and o.get('asset_type')=='boat')
    a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
    s.camera=camera('INSPECT_'+name,p+f*offset[0]+n*offset[1]+Vector((0,0,offset[2])),p+f*target[0]+n*target[1]+Vector((0,0,target[2])),scale)
    s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
