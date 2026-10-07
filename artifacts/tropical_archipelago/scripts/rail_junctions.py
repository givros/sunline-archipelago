"""Local physical junction cleanup, preserving the authored rail centerlines.

Call fix_junctions() after tracks/bridges exist and before final export. Exact
mesh Boolean unions remove coplanar rail/deck overlaps. Route-owned walkways and
safety rails yield to the intersecting railway corridor. No scene reset/import
side effects; all Boolean results are applied editable meshes.
"""
import math
import bpy
from mathutils import Vector
from layout import RAILS
from core import collection, material, box
from railway import ribbon, metrics, sample


def _objects(prefix,role):
    return [o for o in list(bpy.data.objects) if o.type=='MESH' and o.name.startswith(prefix+'_'+role)]


def _boolean(base,operand,operation,label):
    backup=base.data.copy();old_count=len(base.data.vertices)
    mod=base.modifiers.new(label,'BOOLEAN');mod.operation=operation;mod.solver='EXACT';mod.object=operand
    mod.use_self=True;modname=mod.name
    try:
        bpy.context.view_layer.objects.active=base
        bpy.ops.object.modifier_apply(modifier=modname)
        if operation=='UNION' and len(base.data.vertices)<max(4,old_count//10):
            damaged=base.data;base.data=backup
            if damaged.users==0:bpy.data.meshes.remove(damaged)
            raise RuntimeError('Rail junction union unexpectedly lost geometry: '+base.name)
    except Exception:
        if modname in base.modifiers:base.modifiers.remove(base.modifiers[modname])
        if base.data is not backup:
            damaged=base.data;base.data=backup
            if damaged.users==0:bpy.data.meshes.remove(damaged)
        raise
    if backup.users==0:bpy.data.meshes.remove(backup)


def _union_group(role):
    objects=[]
    for route in RAILS:objects.extend(_objects(route['id'],role))
    if len(objects)<2:return None
    main=objects[0];before=sum(len(o.data.polygons) for o in objects)
    for operand in objects[1:]:
        print('JUNCTION union',role,operand.name,flush=True)
        _boolean(main,operand,'UNION','Resolve '+role+' intersection')
        bpy.data.objects.remove(operand,do_unlink=True)
    main['junction_union']=True;main['source_routes']='RAIL_MAIN,RAIL_SOUTH,RAIL_SPUR'
    return {'role':role,'input_objects':len(objects),'input_faces':before,'result_faces':len(main.data.polygons),'object':main.name}


def _distance(p,points):
    best=1e9
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(den or 1)))
        best=min(best,math.hypot(p[0]-a[0]-dx*t,p[1]-a[1]-dy*t))
    return best


def fix_junctions():
    """Apply full-detail union/corridor cuts and return a measured repair record."""
    marker=bpy.data.objects.get('Railway_Junction_Validation')
    if marker:return {'already_applied':True}
    bpy.context.view_layer.update()
    col=collection('05 • Railway junction structures')
    tempmat=material('Temporary junction cutter',(.2,.2,.2))
    cutters={}
    for idx,route in enumerate(RAILS):
        # Different widths implement deterministic ownership at coincident starts.
        for role,width in [('wide',11.94),('rail_interior',11.28),('track_clear',7.95)]:
            cut=ribbon('JUNCTION_TEMP_'+route['id']+'_'+role,route['points'],width,4,8,tempmat,col)
            cut.hide_render=True;cut.hide_set(True);cutters[(idx,role)]=cut
    cuts=0;removed_posts=0;removed_sleepers=0
    for idx,route in enumerate(RAILS):
        name=route['id']
        print('JUNCTION corridors',name,flush=True)
        for j,other in enumerate(RAILS):
            if idx==j:continue
            # The main line owns shared boundary segments. On a diverging branch,
            # only the perimeter outside the union of both decks remains railed.
            handcut=cutters[(j,'wide' if j<idx else 'rail_interior')]
            for ob in _objects(name,'Handrail'):
                _boolean(ob,handcut,'DIFFERENCE','Open continuous turnout perimeter');cuts+=1
            walkcut=cutters[(j,'wide' if j<idx else 'track_clear')]
            for ob in _objects(name,'Walkway'):
                _boolean(ob,walkcut,'DIFFERENCE','Clear branch track through walkway');cuts+=1
            for ob in _objects(name,'RailingPost'):
                distance=_distance(ob.location,other['points'])
                if distance<(5.97 if j<idx else 5.64):
                    bpy.data.objects.remove(ob,do_unlink=True);removed_posts+=1
            if j<idx:
                # Duplicated sleepers at the shared start are replaced by the
                # main-line sleepers already physically underneath both routes.
                for ob in _objects(name,'Sleeper'):
                    if _distance(ob.location,other['points'])<3.48:
                        bpy.data.objects.remove(ob,do_unlink=True);removed_sleepers+=1
    for cut in cutters.values():bpy.data.objects.remove(cut,do_unlink=True)
    # Union actual volumetric geometry, not offsets that hide z fighting.
    unions=[]
    for role in ['StructuralDeck','Ballast','RailFoot','RailWeb','RailHead']:
        record=_union_group(role)
        if record:unions.append(record)
    # Open boundary ends are trimmed exactly, so no railing crosses a track.
    # Long timber turnout bearers make load transfer legible within each fan.
    wood=material('Turnout hardwood bearers',(.14,.105,.067),.86)
    for route in RAILS[1:]:
        pts=route['points'];main=RAILS[0]['points'];arc=metrics(pts)
        for d in [i*1.6 for i in range(1,70) if i*1.6<arc[-1]]:
            p,ang=sample(pts,d)
            distance=_distance(p,main)
            if 3.1<distance<7.2:
                # At fan intersections these extend across the widened bearing
                # zone while preserving rail top and gauge datums.
                ob=box(route['id']+'_TurnoutBearer',(p.x,p.y,p.z-.255),(.22,7.5,.17),wood,col,ang)
                ob['junction_component']='extended load-bearing sleeper'
    marker=bpy.data.objects.new('Railway_Junction_Validation',None);col.objects.link(marker)
    marker['applied']=True;marker['removed_interior_posts']=removed_posts
    marker['method']='Exact volumetric union; corridor subtraction; deterministic perimeter ownership'
    return {'unions':unions,'corridor_boolean_cuts':cuts,'removed_interior_posts':removed_posts,'removed_duplicate_sleepers':removed_sleepers,'rail_centerlines_preserved':True,'modifiers_applied':True}
