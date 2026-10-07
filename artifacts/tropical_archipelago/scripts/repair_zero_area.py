"""Targeted zero-area face repair; callable only, and never saves a scene.

Preserves every original vertex and every positive-area source triangle. Only
polygons whose source triangulation contains an exactly collapsed triangle are
split. Corner/face attributes and optional custom normals follow original loops.
"""
import bpy,json,collections,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
_FIELDS={'FLOAT':('value',1,np.float32),'INT':('value',1,np.int32),'INT8':('value',1,np.int32),
         'BOOLEAN':('value',1,np.bool_),'FLOAT_VECTOR':('vector',3,np.float32),
         'FLOAT2':('vector',2,np.float32),'FLOAT_COLOR':('color',4,np.float32),
         'BYTE_COLOR':('color',4,np.float32)}

def _triangle_data(me):
    me.calc_loop_triangles()
    coords=np.empty(len(me.vertices)*3,np.float32);me.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
    index=np.empty(len(me.loop_triangles)*3,np.int32);me.loop_triangles.foreach_get('vertices',index);index=index.reshape(-1,3)
    p=coords[index].astype(np.float64);area2=np.linalg.norm(np.cross(p[:,1]-p[:,0],p[:,2]-p[:,0]),axis=1)
    return coords,index,area2

def _positive_signature(indices,areas,material_ids):
    # Rotation of a triangle's starting vertex is irrelevant; winding is retained.
    return collections.Counter((min(tuple(int(x) for x in t),tuple(int(x) for x in np.roll(t,1)),tuple(int(x) for x in np.roll(t,2))),int(mat))
                               for t,a,mat in zip(indices,areas,material_ids) if a>0)

def _prepare(me):
    coords,oldtri,area2=_triangle_data(me)
    zero=np.flatnonzero(area2==0)
    if not len(zero):return None
    if me.shape_keys:raise RuntimeError('Targeted repair does not alter a mesh with shape keys: '+me.name)
    affected={me.loop_triangles[int(i)].polygon_index for i in zero};byface=collections.defaultdict(list)
    for i,t in enumerate(me.loop_triangles):byface[t.polygon_index].append((i,t))
    faces=[];face_map=[];loop_map=[]
    for p in me.polygons:
        if p.index not in affected:
            faces.append(tuple(p.vertices));face_map.append(p.index);loop_map.extend(p.loop_indices)
        else:
            for index,t in byface[p.index]:
                if area2[index]==0:continue
                faces.append(tuple(t.vertices));face_map.append(p.index);loop_map.extend(t.loops)
    face_map=np.asarray(face_map,np.int32);loop_map=np.asarray(loop_map,np.int32)
    oldedge={tuple(sorted(e.vertices)):e.index for e in me.edges}
    attributes=[]
    for a in me.attributes:
        if a.name in {'position','.edge_verts','.corner_vert','.corner_edge','material_index'}:continue
        if a.data_type not in _FIELDS:raise RuntimeError('Unmapped attribute type '+a.data_type+' on '+me.name+':'+a.name)
        field,size,dtype=_FIELDS[a.data_type];values=np.empty(len(a.data)*size,dtype);a.data.foreach_get(field,values)
        attributes.append((a.name,a.domain,a.data_type,field,size,values.reshape(-1,size)))
    custom=None
    if me.has_custom_normals:
        custom=np.empty(len(me.corner_normals)*3,np.float32);me.corner_normals.foreach_get('vector',custom);custom=custom.reshape(-1,3)[loop_map]
    uv_names=[(u.name,bool(u.active_render)) for u in me.uv_layers]
    active_uv=me.uv_layers.active.name if me.uv_layers.active else None
    active_color=me.color_attributes.active_color.name if me.color_attributes.active_color else None
    new=me.copy();new.name=me.name+'__ZeroAreaRepair';new.clear_geometry();new.from_pydata(coords.tolist(),[],faces);new.update()
    edge_map=np.asarray([oldedge.get(tuple(sorted(e.vertices)),-1) for e in new.edges],np.int32)
    maps={'POINT':np.arange(len(coords)),'CORNER':loop_map,'FACE':face_map,'EDGE':edge_map}
    for name,domain,kind,field,size,values in attributes:
        mapping=maps[domain];mapped=np.zeros((len(mapping),size),values.dtype);found=mapping>=0;mapped[found]=values[mapping[found]]
        target=new.attributes.get(name)
        if target and (target.data_type!=kind or target.domain!=domain):new.attributes.remove(target);target=None
        if target is None:target=new.attributes.new(name=name,type=kind,domain=domain)
        target.data.foreach_set(field,mapped.ravel())
    for p,oldindex in zip(new.polygons,face_map):
        original=me.polygons[int(oldindex)];p.material_index=original.material_index;p.use_smooth=original.use_smooth
    for e,index in zip(new.edges,edge_map):
        if index>=0:e.use_seam=me.edges[int(index)].use_seam
    for name,active in uv_names:
        layer=new.uv_layers.get(name)
        if layer:layer.active_render=active
    if active_uv and new.uv_layers.get(active_uv):new.uv_layers.active=new.uv_layers[active_uv]
    if active_color and new.color_attributes.get(active_color):new.color_attributes.active_color=new.color_attributes[active_color]
    if custom is not None:new.normals_split_custom_set(custom.tolist())
    new.update()
    newcoords,newtri,newareas=_triangle_data(new)
    oldmats=[t.material_index for t in me.loop_triangles];newmats=[t.material_index for t in new.loop_triangles]
    same_positions=np.array_equal(coords,newcoords)
    same_positive=_positive_signature(oldtri,area2,oldmats)==_positive_signature(newtri,newareas,newmats)
    if not same_positions or not same_positive or np.any(newareas==0):
        bpy.data.meshes.remove(new)
        raise RuntimeError('Zero-area cleanup failed geometry preservation for '+me.name)
    attribute_error=0.
    for name,domain,kind,field,size,values in attributes:
        if domain=='EDGE':continue
        arr=np.empty(len(new.attributes[name].data)*size,values.dtype);new.attributes[name].data.foreach_get(field,arr)
        diff=np.abs(arr.reshape(-1,size).astype(np.float64)-values[maps[domain]].astype(np.float64))
        attribute_error=max(attribute_error,float(diff.max()) if diff.size else 0.)
    normal_error=0.
    if custom is not None:
        current=np.empty(len(new.corner_normals)*3,np.float32);new.corner_normals.foreach_get('vector',current)
        normal_error=float(np.abs(current.reshape(-1,3)-custom).max())
    if attribute_error>1e-6 or normal_error>1e-5:
        bpy.data.meshes.remove(new);raise RuntimeError('Attribute preservation failed for '+me.name)
    record={'mesh':me.name,'affected_polygons':len(affected),'removed_exact_zero_triangles':len(zero),
            'positive_triangles_before':int((area2>0).sum()),'positive_triangles_after':int((newareas>0).sum()),
            'positive_area_before_m2':float(area2.sum()*.5),'positive_area_after_m2':float(newareas.sum()*.5),
            'vertices_unchanged':same_positions,'positive_triangle_material_multiset_unchanged':same_positive,
            'max_attribute_error':attribute_error,'custom_normals_present':custom is not None,'max_custom_normal_error':normal_error,
            'uv_layers_preserved':[name for name,_ in uv_names],'near_zero_positive_triangles_retained':int(((newareas>0)&(newareas<1e-12)).sum())}
    return new,record

def repair_zero_area(report_path=None,refresh_targets=False):
    """Use the latest preaudit, or scan currently used meshes; caller owns save."""
    if refresh_targets:
        used={o.data.name:o.data for o in bpy.context.scene.objects if o.type=='MESH'}
        names=[name for name,me in used.items() if np.any(_triangle_data(me)[2]==0)]
        discovery={'mode':'Fresh scan of every unique mesh used by the current scene','meshes_scanned':len(used)}
    else:
        pre=json.loads((ROOT/'checkpoints'/'source_geometry_preaudit.json').read_text(encoding='utf-8'))
        names=[r['mesh'] for r in pre['issue_meshes'] if r['degenerate_triangles']]
        discovery={'mode':'Named meshes from the latest source geometry preaudit'}
    prepared=[]
    for name in names:
        old=bpy.data.meshes.get(name)
        if old is None:raise RuntimeError('Preaudit target mesh missing: '+name)
        result=_prepare(old)
        if result:prepared.append((old,*result))
    # Scene objects change only after every prepared replacement passes preservation.
    for old,new,record in prepared:
        original_name=old.name
        for ob in bpy.data.objects:
            if ob.type=='MESH' and ob.data==old:ob.data=new
        bpy.data.meshes.remove(old);new.name=original_name
    bpy.context.view_layer.update()
    records=[r for _,_,r in prepared]
    report={'method':'Only affected polygons are triangulated; exactly zero-area triangles are omitted. All positive triangles and vertex coordinates are preserved.',
            'target_discovery':discovery,'identified_target_meshes':len(names),
            'meshes_repaired':len(records),'triangles_removed':sum(r['removed_exact_zero_triangles'] for r in records),
            'source_scene_saved':False,'records':records}
    path=Path(report_path) if report_path else ROOT/'checkpoints'/'zero_area_repair.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ZERO_AREA_REPAIR',json.dumps({k:v for k,v in report.items() if k!='records'}),flush=True)
    return report
