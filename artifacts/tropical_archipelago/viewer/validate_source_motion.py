"""Independent Blender subframe witnesses for runtime train transform equality."""
import bpy, json, hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parent
scene=bpy.context.scene
roots=[o for o in scene.objects if o.type=='EMPTY' and o.get('asset_type') in {'train_car','train_bogie','train_drawbar'}]
duration=(scene.frame_end-1)/scene.render.fps
times=[0,.125,.25,12,75,160,duration-.01,duration,duration+.125]
for car in (o for o in roots if o.get('asset_type')=='train_car' and o.get('car_index')==0):
    period=float(car['motion_physical_period_seconds']);phase=float(car['motion_phase_seconds']);dwell=float(car['motion_dwell_seconds'])
    travel=(float(car['motion_head_max'])-float(car['motion_head_min']))/float(car['speed'])+float(car['motion_ramp_seconds'])
    for boundary in [travel,travel+dwell,2*travel+dwell,period]:
        time=((boundary-phase)%period)*duration/period
        times.extend([(time-.125)%duration,time,(time+.125)%duration])
times=sorted(set(round(t,9) for t in times))
samples=[]
for time in times:
    f=1+(time%duration)*scene.render.fps;whole=int(f)
    scene.frame_set(whole,subframe=f-whole);bpy.context.view_layer.update()
    transforms=[]
    for o in roots:
        m=o.matrix_world
        p,q,s=m.decompose()
        transforms.append({'id':o.name,'position':list(p),'yaw':q.to_euler('XYZ').z,'scale':list(s)})
    samples.append({'time':time,'cars':transforms})
record={'source_file':Path(bpy.data.filepath).name,'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'duration':duration,'roots':len(roots),'samples':samples}
target=BASE/'output'/'playwright'/'train-source-samples.json'
target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(record,indent=2))
scene.frame_set(1)
print('SOURCE_MOTION_WITNESSES',len(roots),len(samples),str(target),flush=True)
