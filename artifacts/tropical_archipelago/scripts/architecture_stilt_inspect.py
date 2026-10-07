import bpy, sys, math, json
from mathutils import Vector
sys.path.insert(0,r'E:/Dev/cosy-island-archipelago/artifacts/tropical_archipelago/scripts')
import architecture as A
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
r=A.house('Stilt_detail',0,0,0,angle=.18,kind='stilt',variant=3)
bpy.ops.mesh.primitive_plane_add(size=90,location=(0,0,0));bpy.context.object.data.materials.append(A.material('LagoonInspection',(.07,.54,.53),.25))
world=bpy.data.worlds.new('Inspection Sky');bpy.context.scene.world=world;world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.65,.8,.9,1);world.node_tree.nodes['Background'].inputs[1].default_value=.7
ld=bpy.data.lights.new('Sun','SUN');lo=bpy.data.objects.new('Sun',ld);bpy.context.collection.objects.link(lo);lo.rotation_euler=(.35,-.7,-.4);ld.energy=3.2
camdata=bpy.data.cameras.new('Camera');cam=bpy.data.objects.new('Camera',camdata);bpy.context.collection.objects.link(cam);cam.location=(21,-25,13);cam.rotation_euler=(Vector((0,0,3.7))-cam.location).to_track_quat('-Z','Y').to_euler();camdata.type='ORTHO';camdata.ortho_scale=21;bpy.context.scene.camera=cam
s=bpy.context.scene;s.render.engine='CYCLES';s.cycles.samples=24;s.render.resolution_x=1200;s.render.resolution_y=1000;s.render.resolution_percentage=100;s.view_settings.view_transform='AgX';s.render.filepath=r'E:/Dev/cosy-island-archipelago/artifacts/tropical_archipelago/renders/architecture_stilt_detail.png';bpy.ops.render.render(write_still=True)
# Actual source bounds and mesh validity: finite coordinates, valid polygons, all mesh components.
bpy.context.view_layer.update();coords=[o.matrix_world@v.co for o in r['objects'] for v in o.data.vertices];print('VALIDATION',json.dumps({'component_count':len(r['objects']),'vertex_count':len(coords),'actual_bounds':[[min(v[i] for v in coords) for i in range(3)],[max(v[i] for v in coords) for i in range(3)]],'floor_z':r['floor_z'],'finite_geometry':all(math.isfinite(v[i]) for v in coords for i in range(3)),'solid_polygon':r['obstacles'][0]['polygon']}))
