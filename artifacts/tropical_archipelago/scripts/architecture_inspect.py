import bpy, sys, math, json
from mathutils import Vector
sys.path.insert(0,r'E:/Dev/cosy-island-archipelago/artifacts/tropical_archipelago/scripts')
import architecture as A
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
assets=[A.house('VILLA',-18,0,0,variant=0),A.house('COTTAGE',0,0,0,kind='cottage',variant=2),A.house('STILT',19,0,-3.2,kind='stilt',variant=1),A.church('CHURCH',-3,26,0),A.pavilion('PAVILION',21,25,-3.2)]
A.dock_props('HARBOR',-18,-12,0)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.02));floor=bpy.context.object;floor.name='Inspection floor';floor.data.materials.append(A.material('Inspection',(0.24,.29,.27)))
world=bpy.data.worlds.new('Inspection Sky');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.6,.75,.85,1);world.node_tree.nodes['Background'].inputs[1].default_value=.6
ld=bpy.data.lights.new('Sun','SUN');lo=bpy.data.objects.new('Sun',ld);bpy.context.collection.objects.link(lo);lo.rotation_euler=(.45,-.55,-.4);ld.energy=3
camdata=bpy.data.cameras.new('InspectionCamera');cam=bpy.data.objects.new('InspectionCamera',camdata);bpy.context.collection.objects.link(cam);cam.location=(63,-76,56);target=Vector((0,8,5));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=84;bpy.context.scene.camera=cam
scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=20;scene.render.resolution_x=1400;scene.render.resolution_y=1050;scene.render.resolution_percentage=100;scene.view_settings.view_transform='AgX'
scene.render.filepath=r'E:/Dev/cosy-island-archipelago/artifacts/tropical_archipelago/renders/architecture_inspection.png'
bpy.ops.wm.save_as_mainfile(filepath=r'E:/Dev/cosy-island-archipelago/artifacts/tropical_archipelago/checkpoints/architecture_assets.blend')
bpy.ops.render.render(write_still=True)
print('ASSET_CHECK',json.dumps([{'name':s['parent'].name,'components':len(s['objects']),'floor_z':s['floor_z'],'entrance':s['entrance']} for s in assets]))
