"""Export evaluated Blender scene to uncompressed, full precision runtime buffers.
Run: blender -b Tropical_Archipelago.blend -P scripts/export_runtime.py
"""
import bpy, json, hashlib, os, sys, shutil, math, time
from pathlib import Path
from array import array
from mathutils import Matrix, Vector
import numpy as np

START=time.time()
BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'viewer'/'public'/'assets'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'textures').mkdir(exist_ok=True)
bpy.context.scene.frame_set(1)
dg=bpy.context.evaluated_depsgraph_get()
blob=bytearray(); geometry=[]; objects=[]; materials=[]; matids={}; hashes={}; cache={}
stats={'source_visible_objects':0,'source_evaluated_triangles':0,'exported_objects':0,'unique_triangles':0,'invalid_normals_repaired':0,'unsupported_material_nodes':[]}

def attr(a, size):
    a=np.ascontiguousarray(a,dtype=np.float32)
    if not np.isfinite(a).all(): raise ValueError('Non-finite exported attribute')
    offset=len(blob); blob.extend(a.tobytes()); return {'offset':offset,'count':int(a.size//size),'itemSize':size}

def material_id(mat):
    key=mat.name if mat else '__default'
    if key in matids: return matids[key]
    mid=len(materials);matids[key]=mid
    rec={'id':mid,'name':key,'color':[.6,.6,.6],'roughness':.7,'metalness':0,'opacity':1,'doubleSide':True,'role':'solid'}
    if mat:
        rec['color']=list(mat.diffuse_color[:3]);rec['opacity']=float(mat.diffuse_color[3]);rec['roughness']=float(mat.roughness);rec['metalness']=float(mat.metallic)
        rec['role']=str(mat.get('role',mat.get('semantic_role','solid')))
        if any(k in mat.name.lower() for k in ['ocean','sea_surface']): rec['role']='ocean'
        if mat.use_nodes:
            bs=next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            if bs:
                rec['color']=list(bs.inputs['Base Color'].default_value[:3]);rec['roughness']=float(bs.inputs['Roughness'].default_value);rec['metalness']=float(bs.inputs['Metallic'].default_value);rec['opacity']=float(bs.inputs['Alpha'].default_value)
                for link in bs.inputs['Base Color'].links:
                    if link.from_node.type=='TEX_IMAGE' and link.from_node.image:
                        im=link.from_node.image;src=Path(bpy.path.abspath(im.filepath));dest=OUT/'textures'/f'{mid}_{bpy.path.clean_name(im.name)}'
                        if not dest.suffix: dest=dest.with_suffix('.png')
                        if src.is_file(): shutil.copyfile(src,dest)
                        else:
                            old=im.filepath_raw;im.filepath_raw=str(dest);im.save();im.filepath_raw=old
                        rec['map']='textures/'+dest.name;rec['texture_size']=list(im.size);rec['texture_colorspace']=im.colorspace_settings.name;rec['map_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();rec['texture_bytes']=dest.stat().st_size
                    elif link.from_node.type not in ('VERTEX_COLOR','ATTRIBUTE'):
                        stats['unsupported_material_nodes'].append({'material':key,'node':link.from_node.type,'note':'Base color fallback retained; record source procedural discrepancy'})
            rec['source_nodes']=[n.type for n in mat.node_tree.nodes]
    materials.append(rec);return mid

def matrix(m):return [float(m[r][c]) for c in range(4) for r in range(4)]
def custom(obj):
    d={}
    for k in obj.keys():
        if k=='_RNA_UI':continue
        try:d[k]=obj[k].to_list() if hasattr(obj[k],'to_list') else obj[k];json.dumps(d[k])
        except (TypeError,ValueError):d.pop(k,None)
    return d

def component_boxes(mesh):
    """Disconnected source components keep grouped railings and posts navigable."""
    count=len(mesh.vertices)
    if not count:return []
    parent=list(range(count))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]];x=parent[x]
        return x
    edges=np.empty(len(mesh.edges)*2,dtype=np.int32);mesh.edges.foreach_get('vertices',edges)
    for a,b in edges.reshape(-1,2):
        aa=find(int(a));bb=find(int(b))
        if aa!=bb:parent[bb]=aa
    coords=np.empty(count*3,dtype=np.float32);mesh.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
    groups={}
    for i in range(count):
        root=find(i)
        groups.setdefault(root,[]).append(i)
    result=[]
    for indices in groups.values():
        points=coords[indices].astype(np.float64);center=points.mean(axis=0);relative=points-center
        # Source assemblies bake beam rotations into vertices. Principal axes
        # recover tight oriented collision boxes for those exact components.
        if len(indices)>=3:
            _,axes=np.linalg.eigh(relative.T@relative)
            axes=axes[:,::-1]
            if np.linalg.det(axes)<0:axes[:,-1]*=-1
        else:axes=np.eye(3)
        local=relative@axes;transform=np.eye(4);transform[:3,:3]=axes;transform[:3,3]=center
        result.append({'matrix':transform.T.reshape(-1).tolist(),'bounds':[local.min(axis=0).tolist(),local.max(axis=0).tolist()]})
    return result

roots={o.name:o for o in bpy.context.scene.objects if o.type=='EMPTY' and ((o.name.startswith('TRAIN_CAR_') and 'train_id' in o and 'car_index' in o) or o.get('asset_type') in {'train_bogie','train_drawbar'})}
root_records=[{'id':o.name,'matrix':matrix(o.matrix_world),'properties':custom(o)} for o in roots.values()]
render_visible=set()
def visit_collection(collection,hidden=False):
    hidden=hidden or collection.hide_render
    if not hidden:render_visible.update(o.name for o in collection.objects)
    for child in collection.children:visit_collection(child,hidden)
visit_collection(bpy.context.scene.collection)
for obj in bpy.context.scene.objects:
    if obj.hide_render or obj.type not in {'MESH','CURVE','SURFACE','FONT','META'}:continue
    if obj.name not in render_visible:continue
    stats['source_visible_objects']+=1
    ev=obj.evaluated_get(dg)
    material_key=tuple(material_id(s.material) for s in obj.material_slots)
    ckey=(obj.data.as_pointer(),tuple((m.type,m.name) for m in obj.modifiers),material_key)
    gid=cache.get(ckey) if not obj.modifiers else None
    if gid is None:
        mesh=ev.to_mesh(preserve_all_data_layers=True,depsgraph=dg)
        if not mesh or len(mesh.polygons)==0:
            ev.to_mesh_clear();continue
        mesh.calc_loop_triangles()
        triangles=np.empty(len(mesh.loop_triangles)*3,dtype=np.int32);mesh.loop_triangles.foreach_get('loops',triangles)
        tri_mats=np.empty(len(mesh.loop_triangles),dtype=np.int32);mesh.loop_triangles.foreach_get('material_index',tri_mats)
        order=np.argsort(tri_mats,kind='stable');triangles=triangles.reshape(-1,3)[order].reshape(-1);sorted_mats=tri_mats[order]
        loop_vertices=np.empty(len(mesh.loops),dtype=np.int32);mesh.loops.foreach_get('vertex_index',loop_vertices)
        coords=np.empty(len(mesh.vertices)*3,dtype=np.float32);mesh.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)[loop_vertices[triangles]]
        normals=np.empty(len(mesh.corner_normals)*3,dtype=np.float32);mesh.corner_normals.foreach_get('vector',normals);normals=normals.reshape(-1,3)[triangles]
        zero=np.linalg.norm(normals,axis=1)<1e-7
        if zero.any():
            p=coords.reshape(-1,3,3);fn=np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]);lengths=np.linalg.norm(fn,axis=1);fn/=np.maximum(lengths[:,None],1e-8);fn[lengths<1e-8]=[0,0,1]
            normals[zero]=np.repeat(fn,3,axis=0)[zero];stats['invalid_normals_repaired']+=int(zero.sum())
        uv=None;color=None
        if mesh.uv_layers.active:
            u=np.empty(len(mesh.loops)*2,dtype=np.float32);mesh.uv_layers.active.data.foreach_get('uv',u);uv=u.reshape(-1,2)[triangles]
        ca=mesh.color_attributes.active_color
        if ca:
            c=np.empty(len(ca.data)*4,dtype=np.float32);ca.data.foreach_get('color',c);c=c.reshape(-1,4);color=c[loop_vertices[triangles] if ca.domain=='POINT' else triangles]
        groups=[]
        for mi in np.unique(sorted_mats):
            inds=np.flatnonzero(sorted_mats==mi);groups.append({'start':int(inds[0]*3),'count':int(len(inds)*3),'materialIndex':int(mi)})
        h=hashlib.sha256(coords.tobytes()+normals.tobytes()+(uv.tobytes() if uv is not None else b'')+(color.tobytes() if color is not None else b'')+json.dumps(groups).encode()+str(material_key).encode()).hexdigest()
        gid=hashes.get(h)
        if gid is None:
            gid=len(geometry);hashes[h]=gid
            rec={'id':gid,'hash':h,'position':attr(coords,3),'normal':attr(normals,3),'groups':groups,'materials':list(material_key) or [material_id(None)],'triangles':int(len(coords)//3)}
            if uv is not None:rec['uv']=attr(uv,2)
            if color is not None:rec['color']=attr(color,4)
            geometry.append(rec);stats['unique_triangles']+=rec['triangles']
        if obj.get('collider',False) and not obj.get('walkable',False) and 'collisionOBBs' not in geometry[gid]:geometry[gid]['collisionOBBs']=component_boxes(mesh)
        ev.to_mesh_clear();cache[ckey]=gid
    elif obj.get('collider',False) and not obj.get('walkable',False) and 'collisionOBBs' not in geometry[gid]:
        mesh=ev.to_mesh(preserve_all_data_layers=True,depsgraph=dg)
        geometry[gid]['collisionOBBs']=component_boxes(mesh);ev.to_mesh_clear()
    stats['source_evaluated_triangles']+=geometry[gid]['triangles']
    parent=obj.parent;dynamic=None
    while parent:
        if parent.name in roots:dynamic=parent;break
        parent=parent.parent
    props=custom(obj)
    record={'id':obj.name,'geometry':gid,'matrix':matrix(dynamic.matrix_world.inverted()@obj.matrix_world if dynamic else obj.matrix_world),'properties':props}
    if dynamic:record['dynamic_root']=dynamic.name
    objects.append(record)
    if len(objects)%5000==0: print('Exported',len(objects),'objects',flush=True)

stats['exported_objects']=len(objects);stats['unique_meshes']=len(geometry);stats['material_count']=len(materials);stats['binary_bytes']=len(blob);stats['dynamic_roots']=len(root_records);stats['train_cars']=sum(1 for r in root_records if r['properties'].get('asset_type')=='train_car');stats['train_bogies']=sum(1 for r in root_records if r['properties'].get('asset_type')=='train_bogie')
stats['train_drawbars']=sum(1 for r in root_records if r['properties'].get('asset_type')=='train_drawbar')
stats['texture_files']=[{'path':m['map'],'sha256':m['map_sha256'],'bytes':m['texture_bytes'],'size':m['texture_size']} for m in materials if m.get('map')]
(OUT/'scene.bin').write_bytes(blob)
spec_path=BASE/'scene_spec.json';spec=json.loads(spec_path.read_text(encoding='utf-8-sig')) if spec_path.exists() else {}
suns=[{'name':o.name,'color':list(o.data.color),'energy':float(o.data.energy),'direction':list(o.matrix_world.to_quaternion()@Vector((0,0,1))),'angular_diameter':float(o.data.angle)} for o in bpy.context.scene.objects if o.type=='LIGHT' and o.data.type=='SUN' and not o.hide_render]
payload={'schema':'azure-scene-1','coordinates':'Blender right-handed Z up; viewer root rotates X -90 degrees','source_file':Path(bpy.data.filepath).name,'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'geometries':geometry,'objects':objects,'dynamic_roots':root_records,'materials':materials,'lighting':{'suns':suns},'spec':spec,'stats':stats}
(OUT/'scene.json').write_text(json.dumps(payload,separators=(',',':')),encoding='utf-8')
stats['json_bytes']=(OUT/'scene.json').stat().st_size;stats['elapsed_seconds']=round(time.time()-START,2)
stats['scene_binary_sha256']=hashlib.sha256(blob).hexdigest();stats['source_sha256']=payload['source_sha256'];stats['compression']='none';stats['geometry_reduction']='none';stats['attribute_precision']='Float32, matching Blender evaluated attribute storage'
(BASE/'viewer'/'source_transfer.json').write_text(json.dumps(stats,indent=2),encoding='utf-8')
print(json.dumps(stats,indent=2),flush=True)
