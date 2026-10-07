import bpy, os, sys, math, json
from mathutils import Vector
HERE=os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,HERE)
import vehicles as v
OUT=os.path.join(os.path.dirname(HERE),'renders','vehicle_details')
os.makedirs(OUT,exist_ok=True)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
p=v.palette()
water=v.material('Preview water',(.035,.38,.48),.34,.1)
v._box('Water',(0,0,-1.25),(300,200,.8),water,None)
infos=[]
for i,kind in enumerate(('fishing','sail','speed','yacht','taxi','utility')):
    root,meta=v.boat('Preview_'+kind,(i%3-1)*24,(i//3-.5)*25,0,.17,kind,i)
    infos.append(meta)
scene=bpy.context.scene
scene.render.engine='BLENDER_EEVEE'
scene.render.resolution_x=1600;scene.render.resolution_y=1100;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(.4,.5,.65)
world=scene.world;world.use_nodes=True
world.node_tree.nodes['Background'].inputs[0].default_value=(.46,.61,.74,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.5
sun=bpy.data.lights.new('PreviewSun','SUN');sun.energy=2.8;sun.angle=.06
ob=bpy.data.objects.new('PreviewSun',sun);bpy.context.collection.objects.link(ob);ob.rotation_euler=(.45,-.35,-.48)
cam_data=bpy.data.cameras.new('PreviewCamera');cam=bpy.data.objects.new('PreviewCamera',cam_data);bpy.context.collection.objects.link(cam)
scene.camera=cam
def camera(pos,target,ortho):
    cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam_data.type='ORTHO';cam_data.ortho_scale=ortho
scene.view_settings.view_transform='AgX'
camera((53,-78,76),(0,0,2),87)
scene.render.filepath=os.path.join(OUT,'marine_fleet.png')
bpy.ops.render.render(write_still=True)
# A closer fishing / speed / sail inspection at walking distance.
camera((-18,-27,13),(-24,-12.5,1.8),22)
scene.render.resolution_x=1400;scene.render.resolution_y=1000
scene.render.filepath=os.path.join(OUT,'fishing_detail.png')
bpy.ops.render.render(write_still=True)
for ob in list(bpy.data.objects):
    if ob.name.startswith('Preview_'):
        bpy.data.objects.remove(ob,do_unlink=True)
# Rail modules retain the track datum when independently aligned by the scene builder.
for i,role in enumerate(('rear','middle','front')):
    root,meta=v.train_car('PreviewTrain_'+role,(i-1)*19,0,0,0,role,i%2)
    infos.append(meta)
for y in (-.7175,.7175):
    v._box('Rail',(0,y,-.10),(70,.08,.20),p['steel'],None)
for i in range(-54,55):
    v._box('Sleeper',(i*.6,0,-.3),(.23,2.7,.23),p['wood'],None)
v._box('TrackBed',(0,0,-.59),(70,4,.4),p['darksteel'],None)
camera((48,-51,28),(0,0,1.7),73)
scene.render.resolution_x=1700;scene.render.resolution_y=800
scene.render.filepath=os.path.join(OUT,'train_three_cars.png')
bpy.ops.render.render(write_still=True)
camera((22,-13,8),(19,0,2.0),23)
scene.render.resolution_x=1400;scene.render.resolution_y=950
scene.render.filepath=os.path.join(OUT,'train_front_detail.png')
bpy.ops.render.render(write_still=True)
with open(os.path.join(OUT,'vehicle_validation.json'),'w') as f:json.dump(infos,f,indent=2)
print('VEHICLE_VALIDATION_COMPLETE',json.dumps(infos))
