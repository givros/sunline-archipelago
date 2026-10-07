"""Read-only fresh-process final source audit; never saves the Blender scene."""
import bpy,collections,hashlib,json,math,re,sys
from pathlib import Path
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from layout import ROOT,ISLANDS,RAILS,STILT_DISTRICTS,BOATS,DOCKS
from refresh_region_graph import enrich_graph

def sha256(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):result.update(block)
    return result.hexdigest()

def write_json(path,value):Path(path).write_text(json.dumps(value,indent=2),encoding='utf-8')

def visible_names(collection,hidden=False):
    hidden=hidden or collection.hide_render
    names=set() if hidden else {o.name for o in collection.objects}
    for child in collection.children:names.update(visible_names(child,hidden))
    return names

def fcurves(action):
    if hasattr(action,'fcurves'):
        try:return list(action.fcurves)
        except Exception:pass
    return [fc for layer in getattr(action,'layers',[]) for strip in layer.strips for bag in getattr(strip,'channelbags',[]) for fc in bag.fcurves]

def geometry_audit(meshobs):
    unique={o.data.name:o.data for o in meshobs};totals=collections.Counter();issues=[];prototypes=[]
    for name,me in unique.items():
        me.calc_loop_triangles()
        coords=np.empty(len(me.vertices)*3,dtype=np.float32);me.vertices.foreach_get('co',coords);coords=coords.reshape(-1,3)
        normals=np.empty(len(me.corner_normals)*3,dtype=np.float32);me.corner_normals.foreach_get('vector',normals);normals=normals.reshape(-1,3)
        faces=np.empty(len(me.polygons)*3,dtype=np.float32);me.polygons.foreach_get('normal',faces);faces=faces.reshape(-1,3)
        invalid_positions=int((~np.isfinite(coords).all(axis=1)).sum())
        invalid_normals=int(((~np.isfinite(normals).all(axis=1))|(np.linalg.norm(normals,axis=1)<1e-7)).sum())
        invalid_face_normals=int(((~np.isfinite(faces).all(axis=1))|(np.linalg.norm(faces,axis=1)<1e-7)).sum())
        indices=np.empty(len(me.loop_triangles)*3,dtype=np.int32);me.loop_triangles.foreach_get('vertices',indices)
        tris=coords[indices.reshape(-1,3)].astype(np.float64)
        area2=np.linalg.norm(np.cross(tris[:,1]-tris[:,0],tris[:,2]-tris[:,0]),axis=1)
        values={'invalid_positions':invalid_positions,'invalid_corner_normals':invalid_normals,'invalid_face_normals':invalid_face_normals,
                'degenerate_triangles':int((area2==0).sum()),'near_zero_positive_triangles':int(((area2>0)&(area2<1e-12)).sum())}
        totals.update(values);totals['unique_vertices']+=len(coords);totals['unique_triangles']+=len(tris)
        if any(values.values()):issues.append({'mesh':name,**values})
        if me.users>4:prototypes.append({'id':name,'vertices':len(coords),'triangles':len(tris),'linked_users':me.users})
    totals['visible_instanced_triangles']=sum(len(o.data.loop_triangles) for o in meshobs)
    return unique,dict(totals),issues,prototypes

def dependency_audit():
    images=[];external=[];missing=[]
    for im in bpy.data.images:
        if im.type in {'RENDER_RESULT','COMPOSITING'} or not im.users:continue
        packed=list(getattr(im,'packed_files',[]))
        packs=[item.packed_file for item in packed] if packed else ([im.packed_file] if im.packed_file else [])
        path=Path(bpy.path.abspath(im.filepath,library=im.library)) if im.filepath else None
        exists=bool(path and path.is_file());embedded=bool(packs);generated=im.source in {'GENERATED','VIEWER'}
        rec={'name':im.name,'source':im.source,'size':list(im.size),'packed':embedded,'packed_bytes':sum(p.size for p in packs),
             'packed_sha256':[hashlib.sha256(bytes(p.data)).hexdigest() for p in packs],'path':im.filepath,'external_file_exists':exists,'available':embedded or generated or exists}
        if exists:
            rec['external_sha256']=sha256(path)
            if embedded:rec['external_matches_packed']=rec['external_sha256'] in rec['packed_sha256']
        images.append(rec)
        if not rec['available'] or min(im.size)<=0:missing.append('image:'+im.name)
    groups=[('library',bpy.data.libraries),('font',bpy.data.fonts),('sound',bpy.data.sounds),('movieclip',bpy.data.movieclips),('volume',bpy.data.volumes)]
    for kind,data in groups:
        for item in data:
            value=getattr(item,'filepath','')
            if not value or value.startswith('<builtin') or (kind!='library' and not item.users):continue
            path=Path(bpy.path.abspath(value,library=getattr(item,'library',None)))
            packed=bool(getattr(item,'packed_file',None));exists=path.is_file()
            rec={'type':kind,'name':item.name,'path':value,'packed':packed,'available':packed or exists}
            if exists:rec['sha256']=sha256(path)
            external.append(rec)
            if not rec['available']:missing.append(kind+':'+item.name)
    return {'images':images,'other_dependencies':external,'missing':missing,
            'all_used_file_images_packed':all(r['packed'] for r in images if r['source']=='FILE'),
            'external_textures_match_packed':all(r.get('external_matches_packed',True) for r in images)}

def route_inventory(scene):
    routes=[];cache={}
    def surface_objects(prefix,role):
        return [o for o in scene.objects if o.type=='MESH' and (o.name.startswith(prefix+'_'+role) or
                (o.get('junction_union') and prefix in str(o.get('source_routes','')).split(',') and '_'+role in o.name))]
    def bvh(ob):
        if ob.name not in cache:
            me=ob.data;me.calc_loop_triangles()
            cache[ob.name]=BVHTree.FromPolygons([ob.matrix_world@v.co for v in me.vertices],
                                             [tuple(t.vertices) for t in me.loop_triangles],all_triangles=True)
        return cache[ob.name]
    def coverage(objects,point,z):
        for ob in objects:
            hit,_,_,_=bvh(ob).ray_cast(Vector((point.x,point.y,z+1)),Vector((0,0,-1)),2)
            if hit is not None and abs(hit.z-z)<.002:return abs(hit.z-z)
        return None
    for route in RAILS:
        prefix=route['id'];decks=surface_objects(prefix,'StructuralDeck');rails=surface_objects(prefix,'RailHead')
        points=[Vector(p) for p in route['points']]
        normals=[]
        for i,p in enumerate(points):
            direction=points[min(i+1,len(points)-1)]-points[max(0,i-1)];direction.z=0;direction.normalize()
            normals.append(Vector((-direction.y,direction.x,0)))
        deck_hits=0;rail_hits=0;rail_total=0;max_height_error=0;misses=[]
        for i,(a,b) in enumerate(zip(points,points[1:])):
            center=(a+b)*.5
            hit=coverage(decks,center,center.z-.7)
            if hit is not None:deck_hits+=1;max_height_error=max(max_height_error,hit)
            elif len(misses)<8:misses.append({'surface':'structural_deck','segment':i,'world':list(center)})
            for offset in [-2.1-.7175,-2.1+.7175,2.1-.7175,2.1+.7175]:
                q=center+(normals[i]+normals[i+1])*(offset*.5);rail_total+=1
                hit=coverage(rails,q,center.z)
                if hit is not None:rail_hits+=1;max_height_error=max(max_height_error,hit)
                elif len(misses)<8:misses.append({'surface':'rail_head','segment':i,'offset':offset,'world':list(q)})
        piers=[o for o in scene.objects if re.fullmatch(re.escape(prefix)+r'_Pier_\d+',o.name)]
        arches=[o for o in scene.objects if re.fullmatch(re.escape(prefix)+r'_Arch_\d+',o.name)]
        routes.append({'id':prefix,'length_m':round(sum((a-b).length for a,b in zip(points,points[1:])),4),'sample_count':len(points),
                       'length_source':'Authored route, verified against final source mesh by downward casts at every segment midpoint and all four rail offsets.',
                       'structural_deck_meshes':[o.name for o in decks],'rail_head_meshes':[o.name for o in rails],
                       'deck_coverage_hits':deck_hits,'deck_coverage_samples':len(points)-1,'rail_coverage_hits':rail_hits,'rail_coverage_samples':rail_total,
                       'max_vertical_surface_error_m':max_height_error,'miss_examples':misses,'rail_piers':len(piers),'arched_spans':len(arches),
                       'sampled_surface_coverage_pass':deck_hits==len(points)-1 and rail_hits==rail_total and rail_total>0})
    return routes

def dynamic_audit(scene):
    dynamic=[o for o in scene.objects if o.type=='EMPTY' and o.get('asset_type') in {'train_car','train_bogie','train_drawbar'}]
    counts=collections.Counter(o['asset_type'] for o in dynamic);trains={};errors=[];drivers=[];key_range=[]
    for car in (o for o in dynamic if o['asset_type']=='train_car'):
        if 'train_id' not in car or 'car_index' not in car:errors.append('Missing train identity: '+car.name);continue
        trains.setdefault(str(car['train_id']),[]).append(int(car['car_index']))
        bogies=[o for o in dynamic if o['asset_type']=='train_bogie' and o.get('motion_parent_car')==car.name]
        if len(bogies)!=2:errors.append('Expected two bogies: '+car.name)
    for name,indices in trains.items():
        if sorted(indices)!=list(range(len(indices))):errors.append('Nonconsecutive carriage index: '+name)
    if counts['train_drawbar']!=sum(max(0,len(indices)-1) for indices in trains.values()):errors.append('Drawbar count does not match consists')
    for o in dynamic:
        data=o.animation_data
        if o['asset_type']!='train_drawbar':
            curves=fcurves(data.action) if data and data.action else []
            if not curves:errors.append('Missing motion keys: '+o.name)
            for fc in curves:
                key_range.extend(float(k.co.x) for k in fc.keyframe_points)
                if any(not all(math.isfinite(float(v)) for v in k.co) for k in fc.keyframe_points):errors.append('Nonfinite motion keys: '+o.name)
        elif not data or not data.drivers:errors.append('Missing drawbar attachment drivers: '+o.name)
        if data:
            for curve in data.drivers:
                drivers.append(curve.driver.is_valid)
                if not curve.driver.is_valid:errors.append('Invalid driver: '+o.name+'.'+curve.data_path)
    scene.frame_set(scene.frame_start);bpy.context.view_layer.update();first={o.name:o.matrix_world.copy() for o in dynamic}
    scene.frame_set(scene.frame_end);bpy.context.view_layer.update()
    loop=max((abs(o.matrix_world[r][c]-first[o.name][r][c]) for o in dynamic for r in range(4) for c in range(4)),default=0)
    scene.frame_set(1);bpy.context.view_layer.update()
    if loop>1e-4:errors.append('Source loop endpoint transform mismatch')
    if not trains:errors.append('No operating train consists')
    return {'counts':dict(counts),'root_count':len(dynamic),'consists':{k:len(v) for k,v in trains.items()},'keyframe_range':[min(key_range),max(key_range)] if key_range else [],
            'driver_count':len(drivers),'invalid_driver_count':drivers.count(False),'max_loop_matrix_error':loop,'errors':errors,'pass':not errors}

def reconcile_vegetation(meshobs,source_hash):
    """Refresh sidecar inventory from surviving linked instances, not target counts."""
    path=ROOT/'vegetation_registry.json'
    registry=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'placements':[],'counts':{},'regions':[]}
    registry.setdefault('original_generation_counts',dict(registry.get('counts',{})))
    registry.setdefault('original_generation_placement_count',len(registry.get('placements',[])))
    old={r['id']:r for r in registry.get('placements',[])};actual={}
    for ob in meshobs:
        if ob.get('prototype_id'):
            identity=ob.name.split('__',1)[0]
            if identity not in actual or ob.get('component_role')=='trunk_collider':actual[identity]=ob
    counts=collections.Counter();regions=collections.defaultdict(collections.Counter);placements=[]
    for identity,ob in sorted(actual.items()):
        record=dict(old.get(identity,{}));family=str(ob.get('asset_family','unknown'));region=str(ob.get('region_id','unknown'))
        record.update({'id':identity,'region':region,'family':family,'prototype':str(ob['prototype_id']),
                       'position':[round(float(v),3) for v in ob.matrix_world.translation],
                       'scale':round(float(ob.scale.x),4),'rotation_z':round(float(ob.rotation_euler.z),7),
                       'soil_datum':float(ob.get('soil_contact_local_z',0))})
        if identity not in old:record['placement_source']='Actual source planting outside the original general scatter registry'
        placements.append(record);counts[family]+=1;regions[region][family]+=1
    families=sorted(set(registry.get('counts',{}))|set(counts))
    registry['counts']={k:counts[k] for k in families};registry['placements']=placements
    oldregions={r['id']:r for r in registry.get('regions',[])};newregions=[]
    for region in sorted(set(oldregions)|set(regions)):
        rec=dict(oldregions.get(region,{'id':region}));rec.setdefault('original_generation_counts',dict(rec.get('counts',{})))
        rec['counts']={family:regions[region][family] for family in families};newregions.append(rec)
    registry['regions']=newregions
    previous=registry.get('reconciliation',{})
    removed=(set(previous.get('removed_instance_ids',[]))|(set(old)-set(actual)))-set(actual)
    added=(set(previous.get('additional_source_instance_ids',[]))|(set(actual)-set(old)))&set(actual)
    registry['source_sha256']=source_hash
    registry['grounding_scope_note']='The grounding statistics and generation targets are historical measurements from build_vegetation(). They are preserved unchanged and are not a new grounding test. Current placements and counts were reconciled against surviving source instances after footprint and navigation clearance removals.'
    registry['reconciliation']={'source_sha256':source_hash,'surviving_instance_count':len(actual),
                                'removed_instance_ids':sorted(removed),'additional_source_instance_ids':sorted(added),
                                'identity_method':"Object name before '__' on current visible prototype_id mesh objects; lower trunk component preferred for the planting transform."}
    write_json(path,registry)
    return {'surviving_instances':len(actual),'counts':registry['counts'],'removed_instances':len(removed),
            'additional_source_instances':len(added),'original_grounding_statistics_preserved':True,'source_sha256':source_hash}

def audit_source(source=None):
    source=Path(source) if source else ROOT/'Tropical_Archipelago.blend'
    before_hash=sha256(source);before_stat=source.stat()
    bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;scene.frame_set(1);bpy.context.view_layer.update()
    names=visible_names(scene.collection);meshobs=[o for o in scene.objects if o.type=='MESH' and not o.hide_render and o.name in names]
    unique,geometry,issues,prototypes=geometry_audit(meshobs)
    bad_transforms=[o.name for o in scene.objects if any(not math.isfinite(float(v)) for row in o.matrix_world for v in row)]
    singular=[o.name for o in meshobs if abs(o.matrix_world.to_3x3().determinant())<1e-12]
    vegetation=collections.defaultdict(set);plant_regions=collections.defaultdict(lambda:collections.defaultdict(set))
    for o in meshobs:
        if o.get('prototype_id'):
            identity=o.name.split('__',1)[0];family=str(o.get('asset_family','unknown'))
            vegetation[family].add(identity);plant_regions[str(o.get('region_id','unknown'))][family].add(identity)
    buildings=[o for o in scene.objects if o.type=='EMPTY' and o.get('building_kind')]
    boats=[o for o in scene.objects if o.type=='EMPTY' and o.get('asset_type')=='boat']
    boatkinds=collections.Counter(str(o.get('boat_kind')) for o in boats);buildingkinds=collections.Counter(str(o.get('building_kind')) for o in buildings)
    routes=route_inventory(scene);motion=dynamic_audit(scene);deps=dependency_audit();assets=[]
    for o in scene.objects:
        if o.type=='EMPTY' and (o.get('asset_family') or o.get('asset_type')):
            assets.append({'id':o.name,'type':o.get('asset_type',o.get('asset_family','assembly')),'kind':o.get('building_kind',o.get('boat_kind',o.get('landmark_kind',''))),
                           'location':list(o.matrix_world.translation),'components':len(o.children_recursive),'editable':True})
    inventory={'islands':sum(bool(scene.objects.get(i['id'])) for i in ISLANDS),'buildings':len(buildings),'building_kinds':dict(buildingkinds),
               'church_landmarks':sum(o.get('landmark_kind')=='coastal_church' for o in scene.objects),'boats':len(boats),'boat_kinds':dict(boatkinds),
               'vegetation_instances':{k:len(v) for k,v in vegetation.items()},'vegetation_by_region':{r:{k:len(v) for k,v in d.items()} for r,d in plant_regions.items()},
               'rail_routes':len(routes),'dock_assemblies':sum(bool(scene.objects.get(d['id'])) for d in DOCKS),
               'dock_loading_aprons':sum(o.type=='EMPTY' and o.name.endswith('_loading_apron') for o in scene.objects),
               'quay_ladder_berths':len({o.get('boat_berth') for o in scene.objects if o.get('asset_type')=='quay_ladder'}),
               'wake_meshes':sum(o.type=='MESH' and o.get('asset_type')=='boat_wake' for o in scene.objects),
               'stilt_districts':{d['id']:sum(o.get('building_kind')=='stilt' and o.name.startswith(d['id']+'_HOUSE_') for o in buildings) for d in STILT_DISTRICTS}}
    modifiers=[{'id':o.name,'types':[m.type for m in o.modifiers]} for o in meshobs if o.modifiers]
    unsupported=[o.name for o in scene.objects if not o.hide_render and o.name in names and o.type in {'CURVE','SURFACE','FONT','META','VOLUME'}]
    after_hash=sha256(source);after_stat=source.stat();unchanged=before_hash==after_hash and before_stat.st_mtime_ns==after_stat.st_mtime_ns
    vegetation_sync=reconcile_vegetation(meshobs,after_hash)
    required={'all_reference_islands':inventory['islands']==len(ISLANDS),'all_authored_boats':len(boats)==len(BOATS),
              'all_stilt_houses':all(inventory['stilt_districts'][d['id']]==len(d['houses']) for d in STILT_DISTRICTS),
              'all_rail_routes':all(r['sampled_surface_coverage_pass'] for r in routes),'train_motion':motion['pass'],
              'all_file_images_packed':deps['all_used_file_images_packed'],'dependencies_available':not deps['missing'],
              'external_textures_match_packed':deps['external_textures_match_packed'],
              'finite_transforms':not bad_transforms and not singular,'finite_geometry':geometry['invalid_positions']==0,
              'valid_normals':geometry['invalid_corner_normals']==0 and geometry['invalid_face_normals']==0,
              'nondegenerate_triangles':geometry['degenerate_triangles']==0,'mesh_only_evaluated_geometry':not modifiers and not unsupported,'source_file_unchanged':unchanged}
    report={'schema':'sunline-source-audit-2','fresh_process_reopen':True,'blend_file':str(source),'source_sha256':after_hash,'source_bytes':after_stat.st_size,
            'source_file_unchanged_during_audit':unchanged,'blender_version':bpy.app.version_string,'inventory':inventory,
            'mesh_object_count':len(meshobs),'unique_mesh_count':len(unique),'materials_used':len({s.material.name for o in meshobs for s in o.material_slots if s.material}),
            'geometry':geometry,'geometry_issue_mesh_count':len(issues),'geometry_issue_examples':issues[:30],'vegetation_registry_reconciliation':vegetation_sync,
            'invalid_transform_examples':bad_transforms[:10],'singular_transform_examples':singular[:10],
            'dependencies':deps,'routes':routes,'dynamic':motion,'frame_start':scene.frame_start,'frame_end':scene.frame_end,'fps':scene.render.fps,
            'cameras':[o.name for o in scene.objects if o.type=='CAMERA'],'remaining_modifiers':modifiers,'nonmesh_renderable_objects':unsupported,
            'checks':required,'source_validity_pass':all(required.values())}
    registry={'source_sha256':after_hash,'provenance':[{'source':'Original procedural geometry created for this project','license':'Original project assets','scope':'Terrain, structures, rolling stock, vessels, vegetation and props'},
              {'source':'references/primary_layout.png','scope':'User-provided primary layout reference; not a backdrop or substitute for geometry'}],
              'assets':assets,'inventory':inventory,'visible_mesh_objects':len(meshobs),'unique_meshes':len(unique),'instanced_triangles':geometry['visible_instanced_triangles'],
              'shared_meshes':prototypes,'geometry_issues':issues}
    write_json(ROOT/'asset_registry.json',registry)
    connections=[('REG_NORTHWEST','REG_NORTH','Northpoint viaduct'),('REG_NORTH','REG_NORTHEAST','Emerald Strait viaduct'),('REG_NORTHEAST','REG_CENTRAL_PALMS','East lagoon viaduct'),('REG_CENTRAL_PALMS','REG_MAIN','Porto Sol viaduct'),('REG_MAIN','REG_SOUTHEAST','Coral Key branch')]
    graph={'source_sha256':after_hash,'regions':[{'id':i['id'],'name':i['name'],'reference_center':i['center']} for i in ISLANDS],
           'connections':[{'from':a,'to':b,'name':n,'modes':['rail','pedestrian_walkway']} for a,b,n in connections],
           'lagoon_access':STILT_DISTRICTS,'water_access':'All ten islands have coastal swimming access. Boardwalks link stilt districts. Boats are static marine infrastructure, not drivable vehicles.',
           'routes':routes,'connectivity_scope':'Authored region network with measured source rail geometry; player traversal is verified separately in runtime.'}
    enrich_graph(graph)
    write_json(ROOT/'region_graph.json',graph);write_json(ROOT/'checkpoints'/'final_source_audit.json',report)
    print('FINAL_SOURCE_AUDIT',json.dumps({'source_validity_pass':report['source_validity_pass'],'source_sha256':after_hash,
          'inventory':{k:v for k,v in inventory.items() if k!='vegetation_by_region'},'geometry':geometry,'dynamic':motion['counts'],
          'failed_checks':[k for k,v in required.items() if not v],'missing_dependencies':deps['missing']}),flush=True)
    return report

if __name__=='__main__':audit_source()
