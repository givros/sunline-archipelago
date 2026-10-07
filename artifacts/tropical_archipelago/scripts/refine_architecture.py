"""Targeted, editable architectural corrections after full-scene inspection.

Call refine_architecture() in an already loaded final scene. No loading, saving,
rendering or clearing occurs at import. Changes are idempotent and the returned
route records replace same-id stage-seven records for navigation verification.
"""
import bpy, math, json, bmesh
from pathlib import Path
from mathutils import Vector
import architecture as A
import settlements as S
from layout import xy, pixel, catmull, STILT_DISTRICTS
from core import ROOT, box, mesh, collection
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
from shapely.geometry.polygon import orient
from shapely import constrained_delaunay_triangles


def fix_parish_spires():
    """Align square hip-roof eaves with square belfries; preserve all heights."""
    corrected=[]
    for name in ['Porto_Sol_Parish','San_Aurelio_Parish']:
        parent=bpy.data.objects.get(name)
        if not parent or parent.get('spire_square_eaves_v1'):continue
        for ob in parent.children:
            if ob.get('component_role')!='tower_hipped_spire':continue
            for vertex in ob.data.vertices:
                dx,dy=vertex.co.x-3.8,vertex.co.y+8.5
                vertex.co.x=3.8+(dx-dy)*math.sqrt(.5)*(3.65/3.15)
                vertex.co.y=-8.5+(dx+dy)*math.sqrt(.5)*(3.65/3.15)
            bm=bmesh.new();bm.from_mesh(ob.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-6)
            bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=1e-7);bm.to_mesh(ob.data);bm.free()
            ob.data.update();ob['roof_eaves']='Square hip roof aligned with square bell tower; 0.16m local cornice overhang'
            corrected.append(ob.name)
        parent['spire_square_eaves_v1']=True
    print('PARISH_SPIRES_ALIGNED',corrected,flush=True)
    return corrected


def fix_boardwalk_surface_ownership(target_prefixes=None):
    """Clip overlapping physical planks at equal-height joins into sole owners.

    Every surviving clipped plank remains a closed solid at its original height.
    Previously emitted planks own intersections, so public walking surfaces stay
    continuous without duplicated caps, blanket offsets or hidden objects.
    """
    if not target_prefixes and bpy.context.scene.get('boardwalk_surface_ownership_v1'):return {'already_applied':True}
    grid={};polygons=[];changed=[];total_area=0.;removed=0
    def keys(poly,z):
        a,b,c,d=poly.bounds;zz=round(z,4)
        for i in range(math.floor(a/4),math.floor(c/4)+1):
            for j in range(math.floor(b/4),math.floor(d/4)+1):yield (zz,i,j)
    def register(poly,z):
        idx=len(polygons);polygons.append(poly)
        for k in keys(poly,z):grid.setdefault(k,[]).append(idx)
    # House and pavilion platforms own their planks before public connectors.
    owners=[o for o in bpy.data.objects if o.type=='MESH' and o.get('component_role')=='individual_deck_planks']
    if target_prefixes:
        owners.extend(o for o in bpy.data.objects if o.type=='MESH' and o.get('component_role')=='walkable_deck_planks' and not any(o.name.startswith(p) for p in target_prefixes))
    for ob in owners:
        mw=ob.matrix_world
        for face in ob.data.polygons:
            if face.normal.z<.9:continue
            pts=[mw@ob.data.vertices[i].co for i in face.vertices]
            if max(v.z for v in pts)-min(v.z for v in pts)>1e-5:continue
            poly=Polygon([(v.x,v.y) for v in pts])
            if poly.area>1e-8:register(poly,pts[0].z)
    targets=sorted([o for o in bpy.data.objects if o.type=='MESH' and o.get('component_role')=='walkable_deck_planks' and (not target_prefixes or any(o.name.startswith(p) for p in target_prefixes))],key=lambda o:(0 if '_SPINE_' in o.name else 1,o.name))
    for ob in targets:
        mw=ob.matrix_world;inverse=mw.inverted();verts=[];faces=[];materials=[];object_changed=False
        # Each source top quad belongs to one independent rectangular plank.
        caps=[f for f in ob.data.polygons if f.normal.z>.9]
        for face in caps:
            pts=[mw@ob.data.vertices[i].co for i in face.vertices];z=sum(v.z for v in pts)/len(pts)
            poly=Polygon([(v.x,v.y) for v in pts]);ids=set()
            for key in keys(poly,z):ids.update(grid.get(key,()))
            candidates=[polygons[i] for i in ids if polygons[i].intersection(poly).area>1e-8]
            remainder=poly.difference(unary_union(candidates)) if candidates else poly
            overlap=poly.area-remainder.area
            if overlap>1e-8:object_changed=True;total_area+=overlap
            register(poly,z)
            if remainder.is_empty:removed+=1;continue
            pieces=[remainder] if remainder.geom_type=='Polygon' else [p for p in remainder.geoms if p.geom_type=='Polygon']
            for piece in pieces:
                if piece.area<1e-8:continue
                piece=orient(piece,sign=1)
                # Separate cap triangles allow concave and holed plank remnants
                # without relying on ambiguous ngon triangulation.
                for tri in constrained_delaunay_triangles(piece).geoms:
                    if tri.area<1e-9:continue
                    q=list(orient(tri,sign=1).exterior.coords)[:3];off=len(verts)
                    verts.extend([tuple(inverse@Vector((x,y,zz))) for zz in [z-.18,z] for x,y in q])
                    faces.extend([(off+2,off+1,off),(off+3,off+4,off+5)]);materials.extend([face.material_index]*2)
                for ring in [piece.exterior]+list(piece.interiors):
                    points=list(ring.coords)
                    for aa,bb in zip(points,points[1:]):
                        if math.dist(aa,bb)<1e-7:continue
                        off=len(verts);verts.extend([tuple(inverse@Vector(p)) for p in [(aa[0],aa[1],z-.18),(bb[0],bb[1],z-.18),(bb[0],bb[1],z),(aa[0],aa[1],z)]])
                        faces.append((off,off+1,off+2,off+3));materials.append(face.material_index)
        if object_changed:
            old=ob.data;new=bpy.data.meshes.new(ob.name+'_owned_plank_solids');new.from_pydata(verts,[],faces)
            for mat in old.materials:new.materials.append(mat)
            for face,matid in zip(new.polygons,materials):face.material_index=matid
            new.update();ob.data=new;ob['surface_ownership']='Exact equal-height plank intersection clipping; continuous prior-owner surface';changed.append(ob.name)
            if old.users==0:bpy.data.meshes.remove(old)
    report={'changed_meshes':changed,'overlapping_top_area_removed_m2':total_area,'fully_owned_duplicate_planks_removed':removed,'heights_changed':False,'routes_changed':False}
    bpy.context.scene['boardwalk_surface_ownership_v1']=True
    (ROOT/'checkpoints'/('boardwalk_surface_ownership_local.json' if target_prefixes else 'boardwalk_surface_ownership.json')).write_text(json.dumps(report,indent=2))
    print('BOARDWALK_SURFACE_OWNERSHIP',len(changed),round(total_area,5),removed,flush=True)
    return report


def _delete(name):
    col=bpy.data.collections.get(name)
    if col:
        for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
        bpy.data.collections.remove(col)
    else:
        ob=bpy.data.objects.get(name)
        if ob:bpy.data.objects.remove(ob,do_unlink=True)


def _tower(name,rise):
    parent=bpy.data.objects.get(name)
    if not parent or parent.get('tower_refined'):return
    upper={'belfry_corner_piers','belfry_open_span_lintels','hanging_bell','bell_lip','bell_hanger','tower_hipped_spire','tower_cross'}
    for ob in parent.children:
        if ob.type!='MESH':continue
        role=ob.get('component_role','')
        if role=='tower_body':
            for v in ob.data.vertices:v.co.z*=((16+rise)/16)
        elif role=='tower_cornices':
            for v in ob.data.vertices:
                if v.co.z>12:v.co.z+=rise
                elif v.co.z>7:v.co.z+=rise*.5
        elif role.startswith('clock_'):
            for v in ob.data.vertices:v.co.z+=rise
        elif role in upper:
            for v in ob.data.vertices:v.co.z+=rise
        ob.data.update()
    parent['tower_refined']=True;parent['tower_added_local_height']=rise


def _clear_plants(polygon):
    """Clear complete plant instances only where their trunks occupy a new parcel."""
    doomed=set()
    for ob in bpy.data.objects:
        if ob.get('asset_family') in ['broadleaf','palm','fern','shrub','rock']:
            if polygon.contains(Point(ob.location.x,ob.location.y)):doomed.add(ob.name.split('__')[0])
    names=[ob.name for ob in bpy.data.objects if ob.name.split('__')[0] in doomed]
    for name in names:bpy.data.objects.remove(bpy.data.objects[name],do_unlink=True)
    return len(doomed)


def _extruded_cut(name,polygon,z0,z1):
    polygons=[polygon] if polygon.geom_type=='Polygon' else list(polygon.geoms)
    vs=[];fs=[]
    for poly in polygons:
        pts=list(poly.exterior.coords)[:-1];off=len(vs);n=len(pts)
        vs.extend([(x,y,z0) for x,y in pts]+[(x,y,z1) for x,y in pts])
        fs.append(tuple(off+i for i in range(n-1,-1,-1)));fs.append(tuple(off+n+i for i in range(n)))
        fs.extend([(off+i,off+(i+1)%n,off+(i+1)%n+n,off+i+n) for i in range(n)])
    return mesh(name,vs,fs,None)


def _cut_rails(path,width,prefixes,z0=3.10,z1=5.0):
    poly=LineString([p[:2] for p in path]).buffer(width/2+.38,cap_style=2,join_style=2)
    cutter=_extruded_cut('TEMP_public_gate_cutter',poly,z0,z1)
    fixed=[]
    for ob in list(bpy.data.objects):
        if ob.type!='MESH' or not any(ob.name.startswith(p) for p in prefixes):continue
        if ob.get('component_role') not in ['balustrade_posts','balustrade_rails','railing_posts','railing_handrails']:continue
        corners=[ob.matrix_world@Vector(q) for q in ob.bound_box]
        bounds=Polygon([(min(v.x for v in corners),min(v.y for v in corners)),(max(v.x for v in corners),min(v.y for v in corners)),(max(v.x for v in corners),max(v.y for v in corners)),(min(v.x for v in corners),max(v.y for v in corners))])
        if not poly.intersects(bounds):continue
        bpy.context.view_layer.objects.active=ob
        mod=ob.modifiers.new('Physical public entry gap','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
        bpy.ops.object.modifier_apply(modifier=mod.name)
        ob['public_entry_gap']='Mesh cut through handrails and posts; original collider retained'
        fixed.append(ob.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return fixed


def _grade(points,minlevel=3.2,maxgrade=.70):
    path=S._sample_poly(points,.30)
    h=[max(minlevel,S._support(*p[:2])+.11) for p in path]
    # Small terrain spikes cannot become discontinuous drops in a public stair.
    for i in range(1,len(path)):h[i]=max(h[i],h[i-1]-math.dist(path[i][:2],path[i-1][:2])*maxgrade)
    for i in range(len(path)-2,-1,-1):h[i]=max(h[i],h[i+1]-math.dist(path[i][:2],path[i+1][:2])*maxgrade)
    return [(p[0],p[1],z) for p,z in zip(path,h)]


def _rebuild_spine(name,pixelpoints,width=2.7,gaps=(),grade=False):
    _delete(name)
    points=catmull([xy(p) for p in pixelpoints],.6)
    if grade:points=_grade(points)
    _clear_plants(LineString([p[:2] for p in points]).buffer(width/2+1.2))
    gaps=list(gaps);district=name.split('_SPINE_')[0]
    for house in bpy.data.objects:
        if house.type=='EMPTY' and house.name.startswith(district+'_HOUSE_'):
            gaps.append(S._nearest(house.location,[points]))
    result=S._boardwalk(name,points,width,3.2,True,gaps,shore=not grade)
    result['refinement']='Locally rerouted continuous supported public boardwalk'
    return result


def _replace_branch(district,i,paths):
    parent=bpy.data.objects[f'{district}_HOUSE_{i:02d}']
    deckobs=[o for o in parent.children if o.get('component_role')=='individual_deck_planks']
    depth=max(abs(v.co.y) for o in deckobs for v in o.data.vertices)
    ep=parent.matrix_world@Vector((0,-depth,3.2))
    target=S._nearest(ep,paths);z=max(3.2,S._support(*target)+.08)
    name=f'{district}_BRANCH_{i:02d}';_delete(name)
    return S._boardwalk(name,[tuple(ep),(*target,z)],2.3,3.2,False)


def _public_routes():
    result=[];metadata=json.loads((ROOT/'checkpoints/07_metadata.json').read_text())
    original={r['id']:r for r in metadata}
    nw=original['STILT_NORTHWEST_SPINE_2']['points']
    _cut_rails(nw,2.7,['STILT_NORTHWEST_HOUSE_03'])
    # The western shore origin was inside a villa. Start beyond its veranda,
    # follow the existing approach, then join the original crescent shoreline.
    west=[[242,274],[232,281],[215,281],[200,287],[189,294],[200,305],[237,316],[275,307],[296,289]]
    westgaps=[xy(p) for p in [[200,305],[237,316],[275,307],[296,289]]]+[(*xy([239,298]),5)]
    result.append(_rebuild_spine('STILT_WEST_SPINE_1',west,gaps=westgaps,grade=True))
    _delete('STILT_WEST_shore_path')
    # Existing Villa_049 front landing connects to the new shore approach.
    result.append(S._terrain_path('Palm_Crescent_public_approach',[[242,274],[243,271]],2.8))
    # The old Coral centerline crossed house06 after its deck railing. The new
    # line follows the west-facing veranda side with meaningful setback.
    coral=[[1291,808],[1304,838],[1282,857],[1274,879],[1255,903],[1269,922],[1232,951]]
    cgaps=[xy(p) for p in [[1291,808],[1304,838],[1282,857],[1274,879],[1255,903],[1269,922],[1232,951]]]
    rec=_rebuild_spine('STILT_CORAL_SPINE_3',coral,gaps=cgaps);result.append(rec)
    cpaths=[rec['points'],original['STILT_CORAL_SPINE_1']['points'],original['STILT_CORAL_SPINE_2']['points']]
    for i in [5,6,7,8,9]:result.append(_replace_branch('STILT_CORAL',i,cpaths))
    _cut_rails(rec['points'],2.7,['STILT_CORAL_HOUSE_'])
    # Make the steep northern approach a monotonic supported stair/ramp above
    # the surface, without the old terrain-induced 1.5m instantaneous drop.
    north=[[690,82],[719,70],[752,62],[785,67],[817,92],[849,106],[875,101]]
    nrec=_rebuild_spine('STILT_NORTH_SPINE_1',north,gaps=[xy(p) for p in north],grade=True);result.append(nrec)
    for i in [4,5,6]:result.append(_replace_branch('STILT_NORTH',i,[nrec['points']]))
    # The rail pier occupies the original lagoon approach; a short two-bend
    # boardwalk passes on its southern side before rejoining the lagoon hub.
    lagoon=[[1039,500],[1017,493],[1003,497],[982,486],[960,469],[907,462]]
    lrec=_rebuild_spine('STILT_LAGOON_SPINE_1',lagoon,3.2,[(*xy([907,462]),19.0)],grade=True)
    hx,hy=xy([907,462]);lrec['points']=[p for p in lrec['points'] if math.dist(p[:2],(hx,hy))>3.3]+[[hx+3.0,hy,3.25]]
    result.append(lrec)
    # Fixture route avoids the retained central table on the generously sized deck.
    center=xy([907,462]);old=original['STILT_LAGOON_SPINE_2']
    points=old['points'];tail=next(i for i,p in enumerate(points) if math.dist(p[:2],center)>4.2)
    detour=[(center[0]+3.0,center[1],3.25),(center[0]+3.0,center[1]+3.5,3.25)]+points[tail:]
    result.append(dict(old,points=detour,refinement='Public traversal detours around retained central table'))
    return result


def _rotunda():
    name='Lagoon_Circle_Pavilion';_delete(name);x,y=xy([907,462]);radius=17.6
    rec=A.pavilion(name,x,y,0,radius)
    canopy={'pavilion_columns','pavilion_rafters','pavilion_roof','pavilion_roof_ribs'}
    for ob in rec['objects']:
        if ob.get('component_role') in canopy:
            for v in ob.data.vertices:v.co.x*=.64;v.co.y*=.64
            ob.data.update()
    S._tag(rec,'STILT_LAGOON')
    a=A.Assembly('Lagoon_Rotunda_Substructure',x,y,0);p=A.palette(0)
    # Three bearing rings support a wide public deck; no unsupported disk.
    for radius2,n in [(4.7,8),(10,16),(16.3,24)]:
        for j in range(n):
            t=math.tau*j/n;xx,yy=math.cos(t)*radius2,math.sin(t)*radius2
            a.cylinder('additional_bearing_piles',p['wooddark'],(xx,yy,.45),.24,5.3,10)
    for j in range(24):
        t=math.tau*j/24;dx,dy=math.cos(t),math.sin(t)
        a.beam('radial_load_beams',p['wooddark'],(dx*1,dy*1,2.72),(dx*17.2,dy*17.2,2.72),.34,sides=4)
    S._tag(a.finish(35.2,35.2,3.2,(0,-17.6,3.2)),'STILT_LAGOON')
    circle=Point(x,y).buffer(17.4,quad_segs=24)
    cutter=_extruded_cut('TEMP_rotunda_rail_cut',circle,3.1,5.0)
    for ob in list(bpy.data.objects):
        if ob.type=='MESH' and ob.name.startswith('STILT_LAGOON_SPINE_') and ob.get('component_role') in ['railing_posts','railing_handrails']:
            bpy.context.view_layer.objects.active=ob;mod=ob.modifiers.new('Rotunda public connection','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter;bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)
    return S._tag(rec,'STILT_LAGOON')


def _market():
    x,y=xy([290,696]);a=A.Assembly('Porto_Shaded_Market',x,y,5.045);p=A.palette(0)
    for k,(X,Y) in enumerate([(-18,-7),(18,7),(-12,11),(14,-11)]):
        for sx in [-1,1]:
            for sy in [-1,1]:a.box('timber_stall_posts',p['wooddark'],(X+sx*2.5,Y+sy*1.2,1.5),(.14,.14,3.0))
        for j in range(10):
            x0=X-2.8+j*.56;x1=x0+.56;mat=p['fabric'] if j%2 else p['redfabric']
            a.mesh('ridge_canvas_canopies',mat,[(x0,Y-1.5,2.95),(x1,Y-1.5,2.95),(x1,Y,3.35),(x0,Y,3.35),(x0,Y+1.5,2.95),(x1,Y+1.5,2.95)],[(0,1,2,3),(3,2,5,4)])
            a.box('canvas_valances',mat,((x0+x1)/2,Y-1.5,2.81),(.56,.04,.28))
        a.box('market_timber_counter',p['woodlight'],(X,Y+.45,.97),(4.9,.8,.18))
        for sx in [-1,1]:a.box('counter_legs',p['wooddark'],(X+sx*2,Y+.45,.46),(.14,.65,.92))
        for j in range(6):
            a.box('produce_crates',p['wood'],(X-2+j*.8,Y+.45,1.14),(.68,.66,.17))
            for m in range(6):a.cylinder('handmade_goods',p['terracotta'] if k%2 else p['leaf'],(X-2.2+j*.8+(m%3)*.18,Y+.25+(m//3)*.25,1.35),.075,.29,8,.11)
    return S._tag(a.finish(44,29,0,(0,-15,0)),'REG_MAIN')


def _harbor_frontages():
    out=[]
    sites=[('Porto_Fishmonger',[179,801],.10,0,1.22,[184,788]),('Porto_Boathouse',[268,842],.10,3,1.20,[282,817]),('Porto_Ferry_House',[353,842],-.12,1,1.20,[384,844])]
    for name,pix,angle,var,scale,targetpix in sites:
        X,Y=xy(pix);cs,sn=math.cos(angle),math.sin(angle);w=(7.6+(var%3)*.65)*scale;d=(10.2+(var%2)*1.2)*scale
        samples=[S._support(X+u*cs-v*sn,Y+u*sn+v*cs) for u in [-w/2,0,w/2] for v in [-d/2,0,d/2]]
        z=max(2.4,max(samples))-.05;rec=A.house(name,X,Y,z,angle,'shop',var,scale);S._foundation(rec,z)
        poly=Polygon(rec['footprint']).buffer(2.7);_clear_plants(poly)
        out.append(S._tag(rec,'REG_MAIN'));ep=rec['entrance'];front=(math.sin(angle),-math.cos(angle));approach=(ep[0]+front[0]*3.2,ep[1]+front[1]*3.2);target=xy(targetpix)
        # Public service entrances link around the side of their own building.
        side=(X+w*.75*cs,Y+w*.75*sn);corner=(side[0]+front[0]*(d/2+4),side[1]+front[1]*(d/2+4))
        route=[ep[:2],approach,corner,side,target]
        _clear_plants(LineString(route).buffer(2.4))
        out.append(S._terrain_path(name+'_arrival_path',route,2.2,pixels=False,start_z=ep[2]))
    return out


def refine_architecture():
    if bpy.context.scene.get('architecture_refinement_v1'):return {'already_applied':True}
    bpy.context.view_layer.update();S._SUPPORT_CACHE.clear()
    _tower('Porto_Sol_Parish',8.0);_tower('San_Aurelio_Parish',2.4)
    routes=_public_routes();assets=[_rotunda(),_market()]+_harbor_frontages()
    church_approach=[[376,692],[375,678],[368,671]]
    _clear_plants(LineString([xy(p) for p in church_approach]).buffer(6.0))
    routes.append(S._terrain_path('Porto_Parish_Forecourt',church_approach,3.2))
    bpy.context.view_layer.update()
    report={'routes':routes,'assets':assets,'changes':['Raised Porto bell tower 7.2m without changing nave footprint','Raised San Aurelio bell stage 2.1m','Expanded central supported public rotunda to35.2m diameter with retained table','Added four shaded market stalls and three complete harbor shop buildings','Corrected actual public walkway and house gate intersections']}
    bpy.context.scene['architecture_refinement_v1']=True
    (ROOT/'checkpoints/architecture_refinements.json').write_text(json.dumps(report,indent=2))
    (ROOT/'checkpoints/refined_routes.json').write_text(json.dumps(routes,indent=2))
    print('ARCHITECTURE_REFINEMENT_COMPLETE',len(assets),len(routes),flush=True)
    return report
