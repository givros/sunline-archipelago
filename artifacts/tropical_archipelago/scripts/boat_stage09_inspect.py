"""Read-only marine inspection of the assembled archipelago."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from core import camera
from layout import xy
ROOT=HERE.parent;OUT=ROOT/'renders'/'marine_validation';OUT.mkdir(parents=True,exist_ok=True)
s=bpy.context.scene;s.frame_set(1);boats=[o for o in s.objects if o.type=='EMPTY' and o.get('asset_type')=='boat']
report={'source':bpy.data.filepath,'count':len(boats),'boats':[],'wakes':[]}
bpy.context.view_layer.update()
for o in boats:
    p=[c.matrix_world@v.co for c in o.children if c.type=='MESH' for v in c.data.vertices]
    report['boats'].append({'id':o.name,'kind':o['boat_kind'],'length_m':float(o['length_m']),'beam_m':float(o['beam_m']),'component_count':len(o.children),'waterline':float(o['waterline']),'min_z':min(q.z for q in p),'max_z':max(q.z for q in p),'finite_geometry':all(math.isfinite(c) for q in p for c in q)})
for o in s.objects:
    if '_Wake_' in o.name:report['wakes'].append({'id':o.name,'vertices':len(o.data.vertices),'faces':len(o.data.polygons)})
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.render.resolution_percentage=100;s.render.resolution_x=1500;s.render.resolution_y=1100
def shot(name,pos,target,scale):
    s.camera=camera('INSPECT_'+name,pos,target,scale);s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
x,y=xy((209,894));shot('porto_working_harbor',(x+39,y-52,48),(x,y,1),94)
o=bpy.data.objects['BOAT_06_yacht'];a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
shot('moored_yacht_detail',p+f*15-n*20+Vector((0,0,11)),p+Vector((0,0,1.1)),28)
o=bpy.data.objects['BOAT_08_fishing'];a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
shot('fishing_harbor_detail',p+f*10-n*14+Vector((0,0,8)),p+Vector((0,0,1)),21)
o=bpy.data.objects['BOAT_13_sail'];a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
shot('lagoon_sailboat_detail',p+f*18-n*25+Vector((0,0,13)),p+Vector((0,0,6)),31)
o=bpy.data.objects['BOAT_02_speed'];a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
shot('speedboat_wake_detail',p+f*14-n*22+Vector((0,0,17)),p-f*8+Vector((0,0,1)),44)
(OUT/'stage09_readonly_audit.json').write_text(json.dumps(report,indent=2))
print('READONLY_MARINE_AUDIT',json.dumps({'boats':len(boats),'wake_meshes':len(report['wakes']),'families':sorted(set(o['boat_kind'] for o in boats)),'finite':all(r['finite_geometry'] for r in report['boats'])}),flush=True)
