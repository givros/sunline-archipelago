import bpy,math,random
from mathutils import Vector
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
_cube={};_cyl={}
def material(name,color,roughness=.65,metallic=0):
 if name in bpy.data.materials:return bpy.data.materials[name]
 m=bpy.data.materials.new(name);m.diffuse_color=(*color[:3],color[3] if len(color)>3 else 1);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=m.diffuse_color;p.inputs['Roughness'].default_value=roughness;p.inputs['Metallic'].default_value=metallic
 return m
def collection(name):
 c=bpy.data.collections.get(name)
 if not c:c=bpy.data.collections.new(name);bpy.context.scene.collection.children.link(c)
 return c
def link(obj,col=None):
 (col or bpy.context.scene.collection).objects.link(obj);return obj
def mesh(name,verts,faces,mat,col=None,smooth=False):
 me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update();ob=link(bpy.data.objects.new(name,me),col)
 if mat:me.materials.append(mat)
 if smooth:
  for p in me.polygons:p.use_smooth=True
 return ob
def box(name,loc,dims,mat,col=None,angle=0):
 key=mat.name
 if key not in _cube:
  me=bpy.data.meshes.new('Shared cube '+key);me.from_pydata([(-.5,-.5,-.5),(.5,-.5,-.5),(.5,.5,-.5),(-.5,.5,-.5),(-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5)],[],[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]);me.materials.append(mat);_cube[key]=me
 ob=link(bpy.data.objects.new(name,_cube[key]),col);ob.location=loc;ob.scale=dims;ob.rotation_euler.z=angle;return ob
def beam(name,a,b,width,mat,col=None,depth=None):
 mid=(Vector(a)+Vector(b))*.5;v=Vector(b)-Vector(a);ob=box(name,mid,(width,depth or width,v.length),mat,col);ob.rotation_euler=v.to_track_quat('Z','Y').to_euler();return ob
def cylinder(name,a,b,r,mat,col=None,n=10):
 key=(mat.name,n)
 if key not in _cyl:
  vs=[(math.cos(i*2*math.pi/n),math.sin(i*2*math.pi/n),z) for z in [-.5,.5] for i in range(n)];fs=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
  me=bpy.data.meshes.new('Shared cylinder '+str(key));me.from_pydata(vs,[],fs);me.materials.append(mat);_cyl[key]=me
 v=Vector(b)-Vector(a);ob=link(bpy.data.objects.new(name,_cyl[key]),col);ob.location=(Vector(a)+Vector(b))*.5;ob.scale=(r,r,v.length);ob.rotation_euler=v.to_track_quat('Z','Y').to_euler();return ob
def instance(name,me,loc,scale=(1,1,1),angle=0,col=None):
 ob=link(bpy.data.objects.new(name,me),col);ob.location=loc;ob.scale=scale;ob.rotation_euler.z=angle;return ob
def camera(name,loc,target,ortho=None,lens=40):
 data=bpy.data.cameras.new(name);ob=link(bpy.data.objects.new(name,data));ob.location=loc;ob.rotation_euler=(Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler();data.lens=lens;data.clip_end=6000;data.clip_start=.08
 if ortho:data.type='ORTHO';data.ortho_scale=ortho
 return ob
def light_scene():
 w=bpy.data.worlds.new('Tropical maritime sky');w.use_nodes=True;w.node_tree.nodes['Background'].inputs[0].default_value=(.58,.78,1,1);w.node_tree.nodes['Background'].inputs[1].default_value=.45;bpy.context.scene.world=w
 ld=bpy.data.lights.new('Late morning tropical sun','SUN');ld.energy=2.4;ld.angle=.12;ob=link(bpy.data.objects.new('Late morning tropical sun',ld));ob.rotation_euler=(math.radians(28),math.radians(-22),math.radians(-32))
 s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=32;s.cycles.use_denoising=True
 try:
  p=bpy.context.preferences.addons['cycles'].preferences;p.compute_device_type='OPTIX';p.get_devices()
  for d in p.devices:d.use=d.type=='OPTIX'
  s.cycles.device='GPU'
 except Exception:pass
 s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast';s.view_settings.exposure=.1
 s.render.image_settings.file_format='PNG';s.render.resolution_percentage=100;s.render.film_transparent=False
def render(camera_obj,name,w=1448,h=1086,samples=32):
 s=bpy.context.scene;s.camera=camera_obj;s.render.resolution_x=w;s.render.resolution_y=h;s.cycles.samples=samples;s.render.filepath=str(ROOT/'renders'/f'{name}.png');bpy.ops.render.render(write_still=True)
