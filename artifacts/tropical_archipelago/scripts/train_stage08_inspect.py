"""Read-only train inspection; produces independent renders and audit evidence."""
import bpy,sys,json,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from core import camera
from train_motion import phase_for_distance
ROOT=HERE.parent;OUT=ROOT/'renders'/'train_validation';OUT.mkdir(parents=True,exist_ok=True)
scene=bpy.context.scene
manifest=json.loads((ROOT/'checkpoints'/'08_metadata.json').read_text())
nodes=[o for o in scene.objects if o.get('asset_type') in ('train_car','train_bogie','train_drawbar')]
scene.frame_set(1)
initial={o.name:[c for row in o.matrix_world for c in row] for o in nodes}
scene.frame_set(manifest['frame_end'])
loop=max(abs(c-initial[o.name][i]) for o in nodes for i,c in enumerate(c for row in o.matrix_world for c in row))
scene.frame_set(1)
report={'source':bpy.data.filepath,'counts':{role:sum(o.get('asset_type')==role for o in nodes) for role in ('train_car','train_bogie','train_drawbar')},'max_world_loop_error':loop,'invalid_drivers':[(o.name,f.data_path) for o in nodes if o.animation_data for f in o.animation_data.drivers if not f.driver.is_valid],'bogie_mesh_counts':{o.name:len(o.children) for o in nodes if o.get('asset_type')=='train_bogie'},'operational_validation':manifest['dimensional_validation'],'frame1':[]}
for o in nodes:
    if o.get('asset_type')=='train_car':report['frame1'].append({'name':o.name,'role':o.get('role'),'position':list(o.location),'yaw':o.rotation_euler.z})
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.cycles.use_denoising=True
scene.render.resolution_x=1600;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
def shot(name,car_name,forward_shift,side_shift,z,look_back,ortho):
    car=bpy.data.objects[car_name];a=car.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=car.matrix_world.translation
    scene.camera=camera('INSPECT_'+name,p+f*forward_shift+n*side_shift+Vector((0,0,z)),p-f*look_back+Vector((0,0,1.5)),ortho)
    scene.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
shot('upper_train_front','TRAIN_CAR_0_0',19,-32,16,6,44)
shot('lower_train_consist','TRAIN_CAR_1_4',30,-120,74,0,191)
train=manifest['trains'][0];motion=train['motion'];target=280
phase=phase_for_distance(target,motion);elapsed=((phase-train['phase_seconds'])%motion['physical_period_seconds'])*train['duration_seconds']/motion['physical_period_seconds'];frame=elapsed*24+1
scene.frame_set(int(frame),subframe=frame-int(frame))
report['curve_inspection_frame']=frame
shot('articulated_curve_train','TRAIN_CAR_0_0',13,-27,11,7,40)
car=bpy.data.objects['TRAIN_CAR_0_0'];a=car.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=car.matrix_world.translation
scene.camera=camera('INSPECT_Bogie',p-f*4+n*-10+Vector((0,0,3)),p-f*5.8+Vector((0,0,.7)),12)
scene.render.resolution_x=1500;scene.render.resolution_y=1000;scene.render.filepath=str(OUT/'bogie_drawbar_detail.png');bpy.ops.render.render(write_still=True)
scene.frame_set(1)
(OUT/'stage08_readonly_audit.json').write_text(json.dumps(report,indent=2))
print('READONLY_STAGE08_AUDIT',json.dumps({k:v for k,v in report.items() if k not in ('frame1','bogie_mesh_counts')}),flush=True)
