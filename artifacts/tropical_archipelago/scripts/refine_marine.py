"""Final marine berth and foam refinement. Importing does not alter the scene.

Call apply_refinements() on the assembled scene, then let the caller save it.
The clearance test uses the shaped hull and the actual horizontal deck faces.
"""
import ast
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _hull(points):
    points = sorted(set((round(float(p[0]), 7), round(float(p[1]), 7)) for p in points))
    lower = []
    for p in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def _point_segment(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    den = dx*dx+dy*dy
    t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0.
    q = (a[0]+t*dx, a[1]+t*dy)
    return math.dist(p, q), q


def _overlap(a, b):
    for shape in (a, b):
        for p, q in zip(shape, shape[1:]+shape[:1]):
            nx, ny = -(q[1]-p[1]), q[0]-p[0]
            ap = [x*nx+y*ny for x,y in a]
            bp = [x*nx+y*ny for x,y in b]
            if max(ap) < min(bp)-1e-8 or max(bp) < min(ap)-1e-8:
                return False
    return True


def _distance(a, b):
    if _overlap(a,b):
        return 0.
    return min(_point_segment(p,u,v)[0] for shape,other in ((a,b),(b,a))
               for p in shape for u,v in zip(other,other[1:]+other[:1]))


def _bounds(poly):
    return (min(p[0] for p in poly),min(p[1] for p in poly),max(p[0] for p in poly),max(p[1] for p in poly))


def _box_distance(a,b):
    return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))


def _deck_faces():
    """Keep individual deck top faces: a convex hull around a bent pier is wrong."""
    records=[]
    for ob in bpy.context.scene.objects:
        if ob.type != 'MESH' or ob.get('component_role') != 'walkable_deck_planks':
            continue
        mat=ob.matrix_world
        normalmat=mat.to_3x3().inverted().transposed()
        for face in ob.data.polygons:
            normal=normalmat@face.normal
            if normal.z < .8*normal.length:
                continue
            verts=[mat@ob.data.vertices[i].co for i in face.vertices]
            poly=_hull(verts)
            if len(poly)>=3:
                records.append({'id':ob.name,'poly':poly,'bounds':_bounds(poly),'z':sum(v.z for v in verts)/len(verts)})
    return records


def _boat_hull(ob):
    hull=next(c for c in ob.children if c.type=='MESH' and c.name.endswith('_SculptedHull'))
    return _hull([hull.matrix_world@v.co for v in hull.data.vertices])


def audit_clearances(decks=None):
    decks=decks if decks is not None else _deck_faces()
    records=[]
    boats=sorted((o for o in bpy.context.scene.objects if o.type=='EMPTY' and o.get('asset_type')=='boat'),key=lambda o:o.name)
    for ob in boats:
        poly=_boat_hull(ob);bounds=_bounds(poly)
        nearby=[r for r in decks if _box_distance(bounds,r['bounds'])<25]
        if not nearby:
            continue
        candidates=[(_distance(poly,r['poly']),r) for r in nearby]
        distance,deck=min(candidates,key=lambda p:p[0])
        records.append({'boat':ob.name,'kind':ob['boat_kind'],'deck':deck['id'],
                        'hull_to_deck_xy_m':round(distance,5),'intersects_xy':distance<1e-6,
                        'world_position':list(ob.location),'heading_radians':float(ob.rotation_euler.z)})
    return {'method':'Convex shaped hull footprint against individual actual upward dock/boardwalk deck faces; no convex hull across bent piers.',
            'nearby_search_m':25,'deck_top_faces':len(decks),'near_dock_boats':records,
            'intersections':[r['boat'] for r in records if r['intersects_xy']]}


def _move_yacht(decks):
    import layout
    ob=bpy.data.objects['BOAT_06_yacht']
    before=list(ob.location)
    a,b=[Vector(layout.xy(p)) for p in [[222,880],[179,935]]]
    tangent=(b-a).normalized();normal=Vector((-tangent.y,tangent.x))
    if (Vector(ob.location[:2])-a).dot(normal)<0:
        normal=-normal
    poly=_boat_hull(ob)
    candidates=[r for r in decks if _box_distance(_bounds(poly),r['bounds'])<35]
    clearance=min(_distance(poly,r['poly']) for r in candidates)
    step=0
    # Keep a realistic fender/boarding gap between the shaped hull and quay.
    while clearance<.8 and step<100:
        ob.location.x+=normal.x*.1;ob.location.y+=normal.y*.1;step+=1
        bpy.context.view_layer.update()
        poly=_boat_hull(ob);clearance=min(_distance(poly,r['poly']) for r in candidates)
    if clearance<.8:
        raise RuntimeError('Unable to provide the yacht with the specified clear water berth')
    px=list(layout.pixel(ob.location))
    ob['reference_pixel']=px
    ob['berth_hull_clearance_m']=float(clearance)
    ob['placement_refinement']='Shifted perpendicular to Porto west pier to clear the actual deck geometry.'
    return {'boat':ob.name,'index':6,'before_world':before,'after_world':list(ob.location),
            'reference_pixel':px,'translation_m':math.dist(before,list(ob.location)),
            'hull_clearance_m':clearance,'heading_preserved':True}


def _move_small_conflict(name,decks):
    """Find the shortest local translation giving 0.8 m of clear berth water."""
    import layout
    ob=bpy.data.objects[name];before=list(ob.location);poly=_boat_hull(ob)
    nearby=[r for r in decks if _box_distance(_bounds(poly),r['bounds'])<18]
    base=min(_distance(poly,r['poly']) for r in nearby)
    if base>=.8:return None
    otherhulls=[_boat_hull(o) for o in bpy.context.scene.objects
                if o.get('asset_type')=='boat' and o!=ob and (o.location-ob.location).length<25]
    # Coarse angle/radius search changes position only and remains inside its berth.
    selected=None
    for step in range(1,41):
        radius=step*.2
        choices=[]
        for j in range(48):
            angle=j*math.tau/48;dx,dy=radius*math.cos(angle),radius*math.sin(angle)
            translated=[(p[0]+dx,p[1]+dy) for p in poly];bounds=_bounds(translated)
            possible=True
            for deck in nearby:
                if _box_distance(bounds,deck['bounds'])<.8 and _distance(translated,deck['poly'])<.8:
                    possible=False;break
            if not possible:continue
            if any(_distance(translated,p)<.8 for p in otherhulls):continue
            clearance=min(_distance(translated,r['poly']) for r in nearby)
            choices.append((clearance,dx,dy))
        if choices:
            selected=max(choices);break
    if selected is None:raise RuntimeError('No local clear berth found for '+name)
    _,dx,dy=selected;ob.location.x+=dx;ob.location.y+=dy;bpy.context.view_layer.update()
    px=list(layout.pixel(ob.location));clearance=min(_distance(_boat_hull(ob),r['poly']) for r in nearby)
    ob['reference_pixel']=px;ob['berth_hull_clearance_m']=float(clearance)
    ob['placement_refinement']='Minimum local berth translation to clear the actual deck footprint; heading retained.'
    return {'boat':name,'index':int(name.split('_')[1]),'before_world':before,'after_world':list(ob.location),
            'reference_pixel':px,'translation_m':math.dist(before,list(ob.location)),
            'hull_clearance_m':clearance,'heading_preserved':True}


def _persist_boat(change):
    import layout
    index=change['index'];px=change['reference_pixel']
    layout.BOATS[index][:2]=px
    # Parse only the authoritative BOATS literal; leave unrelated concurrent work intact.
    path=Path(layout.__file__);source=path.read_text(encoding='utf-8')
    tree=ast.parse(source)
    assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BOATS' for t in n.targets))
    entries=ast.literal_eval(assignment.value);entries[index][:2]=px
    lines=source.splitlines(keepends=True)
    replacement='BOATS=[\n '+',\n '.join(repr(row) for row in entries)+']\n'
    lines[assignment.lineno-1:assignment.end_lineno]=[replacement]
    path.write_text(''.join(lines),encoding='utf-8')
    specpath=ROOT/'scene_spec.json'
    if specpath.exists():
        spec=json.loads(specpath.read_text(encoding='utf-8'));spec['boats'][index][:2]=px
        specpath.write_text(json.dumps(spec,indent=2),encoding='utf-8')
    metapath=ROOT/'checkpoints'/'09_metadata.json'
    if metapath.exists():
        meta=json.loads(metapath.read_text(encoding='utf-8'))
        for j,rec in enumerate(meta['boats']):
            rec['id']=f"BOAT_{j:02d}_{rec['kind']}"
            ob=bpy.data.objects.get(rec['id'])
            if ob:
                rec['world_position']=list(ob.location);rec['reference_pixel']=list(layout.pixel(ob.location))
                rec['heading_radians']=float(ob.rotation_euler.z)
        meta['boats'][index]['berth_hull_clearance_m']=change['hull_clearance_m']
        refinements=[r for r in meta.get('placement_refinements',[]) if r['boat']!=change['boat']]
        meta['placement_refinements']=refinements+[change]
        metapath.write_text(json.dumps(meta,indent=2),encoding='utf-8')


def refine_wakes():
    """Separated intermittent foam streaks, preserving each boat's exact heading."""
    from core import material,collection,mesh
    old=[o for o in bpy.context.scene.objects if '_Wake_' in o.name]
    for ob in old:
        bpy.data.objects.remove(ob,do_unlink=True)
    mats=[material('Marine foam '+str(i),color,.76) for i,color in enumerate([(.33,.60,.60),(.50,.72,.70),(.70,.84,.79)])]
    col=collection('09 • Marine wakes')
    count=0
    for i in [0,1,2,3,4,18]:
        ob=next(o for o in bpy.context.scene.objects if o.name.startswith(f'BOAT_{i:02d}_') and o.get('asset_type')=='boat')
        ca,sa=math.cos(ob.rotation_euler.z),math.sin(ob.rotation_euler.z)
        length=25 if i in [0,1,2] else 15
        boatlength=float(ob['length_m']);beam=float(ob['beam_m'])
        for side in [-1,1]:
            for strand in range(3):
                verts=[];faces=[]
                for dash in range(11):
                    t0=(dash+.12*strand)/11;t1=min(1.,t0+(.52+.10*math.sin(dash*2.3+strand))/11)
                    start=len(verts)
                    for k in range(7):
                        u=k/6;t=t0+(t1-t0)*u
                        back=-boatlength*.5-.12-t*length
                        off=side*(beam*.18+strand*.19+t*(3.9+strand*.62)+.035*math.sin(t*25+strand))
                        width=max(.0015,(.035+.055*math.sin(math.pi*t))*(1-strand*.18)*(1-.65*t)*math.sin(math.pi*u))
                        for delta in [-width,width]:
                            verts.append((ob.location.x+back*ca-(off+delta)*sa,ob.location.y+back*sa+(off+delta)*ca,.023+.003*strand))
                        if k:faces.append((start+2*k-2,start+2*k-1,start+2*k+1,start+2*k))
                obj=mesh(f'BOAT_{i:02d}_Wake_{side}_{strand}',verts,faces,mats[2-strand],col)
                obj['asset_type']='boat_wake';obj['boat_id']=ob.name;obj['foam_style']='Separated intermittent tapering stern trails'
                count+=1
    return {'removed_ribbons':len(old),'foam_meshes':count,'moving_boats':6,'crossing_strands':False,'opaque_geometry':'Narrow separated intermittent tapered foam traces, no continuous broad ribbon.'}


def add_berth_ladders(decks,indices=None):
    """Six U-rail quay ladders and suspended rubbing fenders on actual dock edges."""
    from core import collection,material,cylinder,box
    col=collection('09 • Working berth access')
    selected=indices if indices is not None else [5,6,7,8,9,23]
    for ob in list(col.objects):
        if indices is None or any(ob.name.startswith(f'BERTH_{i:02d}_') for i in selected):bpy.data.objects.remove(ob,do_unlink=True)
    steel=material('Quay ladder brushed galvanized steel',(.34,.40,.40),.32,.70)
    rubber=material('Quay hanging rubber fenders',(.026,.036,.035),.89)
    rope=material('Quay fender hanging rope',(.45,.36,.22),.92)
    records=[]
    for index in selected:
        boat=next(o for o in bpy.context.scene.objects if o.name.startswith(f'BOAT_{index:02d}_') and o.get('asset_type')=='boat')
        p=tuple(boat.location[:2]);candidates=[]
        for deck in decks:
            if _box_distance((p[0],p[1],p[0],p[1]),deck['bounds'])>25:continue
            for a,b in zip(deck['poly'],deck['poly'][1:]+deck['poly'][:1]):
                distance,q=_point_segment(p,a,b);candidates.append((distance,q,deck['z']))
        _,q,deckz=min(candidates,key=lambda v:v[0])
        n=Vector((p[0]-q[0],p[1]-q[1],0)).normalized();t=Vector((-n.y,n.x,0));base=Vector((q[0],q[1],deckz))
        prefix=f'BERTH_{index:02d}_'
        def point(side,out,z):return base+t*side+n*out+Vector((0,0,z))
        def pipe(label,a,b,r=.044,mat=steel):
            o=cylinder(prefix+label,a,b,r,mat,col,n=10);o['asset_type']='quay_ladder';o['boat_berth']=boat.name
            return o
        for side in [-.43,.43]:
            path=[point(side,.26,-deckz-.36),point(side,.26,.65)]
            path += [point(side,.01+.25*math.cos(j*math.pi/8),.65+.25*math.sin(j*math.pi/8)) for j in range(1,9)]
            path += [point(side,-.24,.08)]
            for j,(a,b) in enumerate(zip(path,path[1:])):pipe(f'SideRail_{side}_{j}',a,b)
            box(prefix+'RailFootPlate',point(side,-.24,.025),(.22,.22,.05),steel,col)
            for z in [-deckz+.35,-.34]:pipe('WallStandOff',point(side,.26,z),point(side,-.10,z),.035)
        rungz=-deckz-.20
        while rungz<-.10:
            pipe('AntiSlipRung',point(-.43,.26,rungz),point(.43,.26,rungz),.031)
            rungz+=.29
        for side in [-1.18,1.18]:
            pipe('SuspensionRope',point(side,.19,-.06),point(side,.19,-deckz+1.05),.014,rope)
            pipe('HangingRubberFender',point(side,.19,-deckz+.30),point(side,.19,-deckz+1.05),.17,rubber)
        records.append({'boat':boat.name,'deck_edge_world':list(base),'ladder_bottom_z':-.36,'rung_spacing_m':.29,'width_m':.86,'supports':'U rails hook over the actual deck edge; suspended rubbing fenders protect the berth.'})
    return records


def tighten_yacht_berth(persist=True,report_path=None):
    """Bring yacht 06 to a 0.8–1.0 m actual hull gap. Caller owns final save."""
    import layout
    bpy.context.view_layer.update();decks=_deck_faces();ob=bpy.data.objects['BOAT_06_yacht']
    before=list(ob.location);heading=float(ob.rotation_euler.z)
    a,b=[Vector(layout.xy(p)) for p in [[222,880],[179,935]]]
    tangent=(b-a).normalized();normal=Vector((-tangent.y,tangent.x))
    if (Vector(ob.location[:2])-a).dot(normal)<0:normal=-normal
    hull=_boat_hull(ob);nearby=[d for d in decks if _box_distance(_bounds(hull),d['bounds'])<25]
    clearance=min(_distance(hull,d['poly']) for d in nearby);old_clearance=clearance
    for _ in range(160):
        if .8<=clearance<=1.:break
        sign=-1 if clearance>1 else 1
        ob.location.x+=normal.x*.1*sign;ob.location.y+=normal.y*.1*sign
        bpy.context.view_layer.update();hull=_boat_hull(ob);clearance=min(_distance(hull,d['poly']) for d in nearby)
    if not .8<=clearance<=1.:raise RuntimeError('Yacht 06 failed the requested 0.8–1.0 m berth gap')
    px=list(layout.pixel(ob.location));ob['reference_pixel']=px;ob['berth_hull_clearance_m']=float(clearance)
    ob['placement_refinement']='Reference berth refined to a 0.8–1.0 m hull-to-quay gap with original heading.'
    change={'boat':ob.name,'index':6,'before_world':before,'after_world':list(ob.location),'reference_pixel':px,
            'translation_m':math.dist(before,list(ob.location)),'hull_clearance_before_m':old_clearance,'hull_clearance_m':clearance,
            'heading_preserved':heading==float(ob.rotation_euler.z)}
    if persist:_persist_boat(change)
    ladder=add_berth_ladders(decks,[6]);after=audit_clearances(decks)
    report={'source':bpy.data.filepath,'change':change,'berth_access':ladder,'after':after,'source_scene_saved':False}
    path=Path(report_path) if report_path else ROOT/'checkpoints'/'yacht_berth_precision.json'
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    if persist:
        oldpath=ROOT/'marine_clearance_report.json'
        if oldpath.exists():
            previous=json.loads(oldpath.read_text(encoding='utf-8'))
            previous['changes']=[r for r in previous.get('changes',[]) if r['boat']!=ob.name]+[change]
            previous['berth_access']=[r for r in previous.get('berth_access',[]) if r['boat']!=ob.name]+ladder
            previous['after']=after;previous['yacht_berth_precision']=change
            oldpath.write_text(json.dumps(previous,indent=2),encoding='utf-8')
    print('YACHT_BERTH_PRECISION',json.dumps(change),flush=True)
    return report


def apply_refinements(persist=True,report_path=None):
    """No scene save: caller owns final .blend serialization and render settings."""
    bpy.context.view_layer.update()
    decks=_deck_faces();before=audit_clearances(decks)
    changes=[_move_yacht(decks)]
    for name in ['BOAT_05_fishing','BOAT_07_utility','BOAT_23_utility','BOAT_25_fishing','BOAT_27_utility']:
        change=_move_small_conflict(name,decks)
        if change:changes.append(change)
    if persist:
        for change in changes:_persist_boat(change)
    wake=refine_wakes()
    ladders=add_berth_ladders(decks)
    after=audit_clearances(decks)
    report={'source':bpy.data.filepath,'before':before,'changes':changes,'after':after,'wake_refinement':wake,'berth_access':ladders,
            'train_materials':'Preserved following source closeup inspection.'}
    output=Path(report_path) if report_path else ROOT/'marine_clearance_report.json'
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('MARINE_REFINEMENT',json.dumps({'changes':changes,'remaining_intersections':after['intersections'],'wake':wake}),flush=True)
    return report
