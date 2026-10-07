"""Six source-confirmed local public-circulation repairs; no I/O on import."""
import bpy,bmesh,math,json,heapq
from mathutils import Vector
from pathlib import Path
from core import ROOT
from layout import xy
import architecture as A
import settlements as S
import refine_architecture as R
from shapely.geometry import Polygon,LineString,Point


def _route_records():
    a=json.loads((ROOT/'checkpoints/07_metadata.json').read_text());b=json.loads((ROOT/'checkpoints/refined_routes.json').read_text())
    return {r['id']:r for r in a+b}


def _remove_post_near(name,point,radius=.8):
    ob=bpy.data.objects.get(name)
    if not ob:return 0
    bm=bmesh.new();bm.from_mesh(ob.data);remaining=set(bm.verts);kill=[]
    while remaining:
        seed=remaining.pop();component={seed};stack=[seed]
        while stack:
            v=stack.pop()
            for e in v.link_edges:
                q=e.other_vert(v)
                if q in remaining:remaining.remove(q);component.add(q);stack.append(q)
        world=[ob.matrix_world@v.co for v in component]
        center=sum(world,Vector())/len(world)
        if math.dist(center[:2],point)<radius:kill.extend(component)
    bmesh.ops.delete(bm,geom=kill,context='VERTS');bm.to_mesh(ob.data);bm.free();ob.data.update()
    return len(kill)


def _cut_ground_to_stair(path,width=1.65,blend=3.0):
    """Excavate a narrow road bed under existing stair treads, preserving profile."""
    terrain=bpy.data.objects['REG_NORTH'];segments=list(zip(path,path[1:]));count=0
    for vertex in terrain.data.vertices:
        x,y,z=vertex.co;best=None
        for a,b in segments:
            dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy or 1)))
            xx,yy=a[0]+t*dx,a[1]+t*dy;dist=math.hypot(x-xx,y-yy)
            if best is None or dist<best[0]:best=(dist,a[2]*(1-t)+b[2]*t-.20)
        dist,target=best
        if dist<blend and z>target:
            weight=1 if dist<=width else 1-(dist-width)/(blend-width)
            vertex.co.z=z+(target-z)*weight;count+=1
    terrain.data.update();S._SUPPORT_CACHE.clear();return count


def _around_polygon(start,end,poly):
    # Visibility graph retains the shortest usable side of the existing platform.
    vertices=list(poly.exterior.coords)[:-1];nodes=[tuple(start),tuple(end)]+vertices;inside=poly.buffer(-1e-6)
    graph=[[] for p in nodes]
    for i,a in enumerate(nodes):
        for j in range(i+1,len(nodes)):
            b=nodes[j]
            if LineString([a,b]).intersects(inside):continue
            d=math.dist(a,b);graph[i].append((j,d));graph[j].append((i,d))
    heap=[(0,0,[])];visited=set()
    while heap:
        distance,i,path=heapq.heappop(heap)
        if i in visited:continue
        visited.add(i);path=path+[nodes[i]]
        if i==1:return path
        for j,d in graph[i]:heapq.heappush(heap,(distance+d,j,path))
    raise ValueError('No unobstructed platform perimeter connection')


def apply_navigation_source_fixes():
    if bpy.context.scene.get('navigation_source_fixes_v1'):return {'already_applied':True}
    bpy.context.view_layer.update();records=_route_records();updates=[];changes=[]
    count=_remove_post_near('STILT_NORTHWEST_HOUSE_03__balustrade_posts',(-189.21,347.65),1.1)
    changes.append({'northwest_gate_post_vertices_removed':count})
    # Only the first14m of the north shore interface needs a road-bed cut.
    points=records['STILT_NORTH_SPINE_1']['points'];section=[points[0]];distance=0
    for p in points[1:]:
        distance+=math.dist(section[-1][:2],p[:2]);section.append(p)
        if distance>14:break
    changes.append({'north_stair_ground_vertices_graded':_cut_ground_to_stair(section)})
    # Preserve a real grade connection at Palm Crescent. The old masonry path
    # lifted its edge1.43m above the public boardwalk at their common endpoint.
    name='Palm_Crescent_public_approach';R._delete(name)
    start=records['STILT_WEST_SPINE_1']['points'][0]
    control=[start,(*xy([238,276]),16.15),(*xy([234,274]),16.7),(*xy([234,270]),17.8),(*xy([238,269]),18.95),(*xy([243,271]),18.95)]
    rec=S._boardwalk(name,control,2.3,3.2,True,[start[:2],control[-1][:2]]);updates.append(rec)
    R._clear_plants(LineString([p[:2] for p in control]).buffer(2.0))
    # A confirmed palm trunk intersects the Coral north public centerline.
    removed=[]
    for ob in list(bpy.data.objects):
        if ob.name.startswith('VEG_SOUTHEAST_PALM_0007__'):removed.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
    changes.append({'coral_corridor_palm_removed':removed})
    # House07 faces the former spine alignment. Its branch must first leave the
    # front gate, wrap outside its full deck, and then reach the relocated spine.
    parent=bpy.data.objects['STILT_CORAL_HOUSE_07'];old=records['STILT_CORAL_BRANCH_07'];ep=old['points'][0]
    deck=[parent.matrix_world@v.co for o in parent.children if o.get('component_role')=='individual_deck_planks' for v in o.data.vertices]
    polygon=Polygon([(v.x,v.y) for v in deck]).convex_hull.buffer(1.6,join_style=2)
    forward=parent.rotation_euler.to_matrix()@Vector((0,-1,0));approach=(ep[0]+forward.x*2.1,ep[1]+forward.y*2.1)
    target=S._nearest(approach,[records['STILT_CORAL_SPINE_3']['points']])
    route=[tuple(ep[:2])]+_around_polygon(approach,target,polygon)
    R._delete('STILT_CORAL_BRANCH_07');rec=S._boardwalk('STILT_CORAL_BRANCH_07',route,2.3,3.2,False);updates.append(rec)
    R._cut_rails(rec['points'],2.3,['STILT_CORAL_HOUSE_07','STILT_CORAL_SPINE_3'])
    # This remaining gate is a real oblique entry collision after exact mesh QA.
    branch=records['STILT_NORTH_BRANCH_04']['points'];changes.append({'north_branch04_gate':R._cut_rails(branch,2.7,['STILT_NORTH_SPINE_1'])})
    _remove_post_near('STILT_NORTH_SPINE_1__railing_posts',(55.13,377.31),1.0)
    bpy.context.view_layer.update()
    # New planks must participate in the same surface-ownership rule as all
    # existing decks. The final zero-area pass follows this function.
    R.fix_boardwalk_surface_ownership(['Palm_Crescent_public_approach','STILT_CORAL_BRANCH_07'])
    overrides=json.loads((ROOT/'checkpoints/refined_routes.json').read_text());byid={r['id']:r for r in overrides}
    for rec in updates:byid[rec['id']]=rec
    (ROOT/'checkpoints/refined_routes.json').write_text(json.dumps(list(byid.values()),indent=2))
    report={'changes':changes,'updated_routes':updates};(ROOT/'checkpoints/navigation_source_fixes.json').write_text(json.dumps(report,indent=2))
    bpy.context.scene['navigation_source_fixes_v1']=True
    print('NAVIGATION_SOURCE_FIXES_COMPLETE',json.dumps(changes),flush=True)
    return report


def fix_shore_approach_joins():
    """Reconcile the three source-confirmed upper shore join defects."""
    if bpy.context.scene.get('shore_approach_joins_v2'):return {'already_applied':True}
    records=_route_records();points=records['STILT_NORTH_SPINE_1']['points']
    path=points[:8];ob=bpy.data.objects['Emerald hillside walk'];count=0
    # The timber stair owns its full width. Regrade the intersecting masonry
    # approach beneath it, blending the new road-bed level into the old lane.
    for vertex in ob.data.vertices:
        x,y,z=vertex.co;best=None
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy or 1)))
            distance=math.hypot(x-a[0]-dx*t,y-a[1]-dy*t)
            if best is None or distance<best[0]:best=(distance,a[2]*(1-t)+b[2]*t-.22)
        distance,height=best
        if distance<3.2 and z>height:
            weight=1 if distance<1.8 else (3.2-distance)/1.4
            vertex.co.z=z+(height-z)*weight;count+=1
    ob.data.update()
    # The approach departs east, away from the descending west spine. The
    # earlier southwest switchback crossed it with 2.4m of vertical separation.
    name='Palm_Crescent_public_approach';R._delete(name)
    start=records['STILT_WEST_SPINE_1']['points'][0]
    control=[start,(-308.5,220.58,16.75),(-308.5,223.04,18.95),(-312.65,223.04,18.95)]
    rec=S._boardwalk(name,control,2.3,3.2,True,[start[:2],control[-1][:2]])
    # Retain exact grade corners. Sparse every-ninth-plank samples can cut
    # diagonally across this short switchback in an automated route fixture.
    rec['points']=[list(p) for p in control]
    R._clear_plants(LineString([p[:2] for p in control]).buffer(2))
    bpy.context.view_layer.update()
    # Only interior-crossing guard fragments are clipped; exterior guardrails
    # remain 1.11m from center, outside the 0.93m clear corridor.
    cut=R._cut_rails(rec['points'],1.1,[name],15.0,21.0)
    R.fix_boardwalk_surface_ownership([name])
    overrides=json.loads((ROOT/'checkpoints/refined_routes.json').read_text());byid={r['id']:r for r in overrides};byid[name]=rec
    (ROOT/'checkpoints/refined_routes.json').write_text(json.dumps(list(byid.values()),indent=2))
    result={'emerald_lane_vertices_graded':count,'corner_guards_opened':cut,'updated_route':rec}
    (ROOT/'checkpoints/shore_approach_joins.json').write_text(json.dumps(result,indent=2))
    bpy.context.scene['shore_approach_joins_v2']=True
    print('SHORE_APPROACH_JOINS_FIXED',count,cut,flush=True)
    return result


def fix_palm_entry_gate():
    """Clear the shared shore entry with an explicit physical gate opening."""
    if bpy.context.scene.get('palm_entry_gate_v3'):return {'already_applied':True}
    from mathutils.geometry import closest_point_on_tri
    start=_route_records()['STILT_WEST_SPINE_1']['points'][0]
    x,y,z=start
    # Replace Boolean-connected guards with independent, explicitly trimmed
    # rail segments. This prevents large cap triangulation from crossing gates.
    cut=[]
    for ob in list(bpy.data.objects):
        if ob.name.startswith('Palm_Crescent_public_approach') and ob.get('component_role') in ['railing_handrails','railing_posts']:
            cut.append(ob.name);bpy.data.objects.remove(ob,do_unlink=True)
    name='Palm_Crescent_entry_guards';R._delete(name)
    assembly=A.Assembly(name,0,0,0);palette=A.palette(0)
    controls=[start,(-308.5,220.58,16.75),(-308.5,223.04,18.95),(-312.65,223.04,18.95)]
    path=S._sample_poly(controls,.33)
    public=_route_records()['Palm_Crescent_public_approach']['points']
    corridor=LineString([p[:2] for p in public]).buffer(.94,join_style=2).union(Point(x,y).buffer(1.8))
    spacing=0
    for a,b in zip(path,path[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1];length=math.hypot(dx,dy)
        if length<1e-7:continue
        nx,ny=-dy/length,dx/length;spacing+=length
        for sign in [-1,1]:
            aa=(a[0]+nx*sign*1.11,a[1]+ny*sign*1.11)
            bb=(b[0]+nx*sign*1.11,b[1]+ny*sign*1.11)
            line=LineString([aa,bb]);remaining=line.difference(corridor)
            pieces=[remaining] if remaining.geom_type=='LineString' else [g for g in getattr(remaining,'geoms',[]) if g.geom_type=='LineString']
            for part in pieces:
                if part.length<.02:continue
                first,last=list(part.coords)[0],list(part.coords)[-1]
                t0=line.project(Point(first))/length;t1=line.project(Point(last))/length
                for height in [.53,1.03]:
                    assembly.beam('railing_handrails',palette['woodlight'],(*first,a[2]*(1-t0)+b[2]*t0+height),(*last,a[2]*(1-t1)+b[2]*t1+height),.075,sides=4)
            if spacing>2:
                point=Point(bb)
                if point.distance(corridor)>.08:assembly.box('railing_posts',palette['wooddark'],(*bb,b[2]+.52),(.10,.10,1.04))
        if spacing>2:spacing=0
    S._tag(assembly.finish(1,1,0,(x,y,z)))
    bpy.context.view_layer.update()
    # Independently probe a 1.3m-wide join with the runtime's .32m body radius
    # and1.72m standing height against exact source triangles, not broad boxes.
    def edge_distance(a,b,c,d):
        u=b-a;v=d-c;w=a-c;aa=u.dot(u);bb=u.dot(v);cc=v.dot(v);dd=u.dot(w);ee=v.dot(w);den=aa*cc-bb*bb
        s=max(0,min(1,(bb*ee-cc*dd)/den)) if den>1e-12 else 0
        t=(bb*s+ee)/cc if cc>1e-12 else 0
        if t<0:t=0;s=max(0,min(1,-dd/aa)) if aa>1e-12 else 0
        elif t>1:t=1;s=max(0,min(1,(bb-dd)/aa)) if aa>1e-12 else 0
        return (w+s*u-t*v).length_squared
    triangles=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH' or not ob.get('collider') or ob.get('walkable'):continue
        if not ob.name.startswith(('Palm_Crescent_public_approach','Palm_Crescent_entry_guards','STILT_WEST_SPINE_1')):continue
        if ob.get('component_role') not in ['railing_handrails','railing_posts']:continue
        ob.data.calc_loop_triangles()
        for f in ob.data.loop_triangles:
            pts=[ob.matrix_world@ob.data.vertices[i].co for i in f.vertices]
            if min(p.x for p in pts)>x+1.1 or max(p.x for p in pts)<x-1.1 or min(p.y for p in pts)>y+1.1 or max(p.y for p in pts)<y-1.1:continue
            triangles.append((ob.name,pts))
    blockers=[]
    for dx in [-.65,0,.65]:
        for dy in [-.65,0,.65]:
            a=Vector((x+dx,y+dy,z+.32));b=Vector((x+dx,y+dy,z+1.72-.32))
            for name,(p,q,r) in triangles:
                if max(p.z,q.z,r.z)<z+.12 or min(p.z,q.z,r.z)>z+1.72:continue
                normal=(q-p).cross(r-p)
                if normal.length_squared<1e-20:continue
                hit=any((closest_point_on_tri(v,p,q,r)-v).length_squared<.32**2 for v in [a,b])
                hit=hit or any(edge_distance(a,b,c,d)<.32**2 for c,d in [(p,q),(q,r),(r,p)])
                den=normal.dot(b-a)
                if abs(den)>1e-12:
                    t=normal.dot(p-a)/den
                    if 0<=t<=1:
                        point=a+t*(b-a)
                        hit=hit or (closest_point_on_tri(point,p,q,r)-point).length_squared<1e-12
                if hit:blockers.append({'center_offset':[dx,dy],'object':name})
    result={'cut_components':cut,'tested_capsule_centers':9,'join_width_m':1.3,'body_radius_m':.32,'blockers':blockers}
    (ROOT/'checkpoints/palm_entry_gate_probe.json').write_text(json.dumps(result,indent=2))
    if blockers:raise RuntimeError('Palm entry gate still blocks an exact capsule probe: '+str(blockers))
    bpy.context.scene['palm_entry_gate_v3']=True
    print('PALM_ENTRY_GATE_VERIFIED',json.dumps(result),flush=True)
    return result


def fix_palm_grade_joists():
    """Keep support beams beneath each stair leg, never across a rising corner."""
    if bpy.context.scene.get('palm_grade_joists_v4'):return {'already_applied':True}
    old=bpy.data.objects.get('Palm_Crescent_public_approach__longitudinal_joists')
    if old:bpy.data.objects.remove(old,do_unlink=True)
    name='Palm_Crescent_grade_joists';R._delete(name)
    assembly=A.Assembly(name,0,0,0);palette=A.palette(0)
    start=_route_records()['STILT_WEST_SPINE_1']['points'][0]
    controls=[start,(-308.5,220.58,16.75),(-308.5,223.04,18.95),(-312.65,223.04,18.95)]
    records=[]
    for leg,(pa,pb) in enumerate(zip(controls,controls[1:])):
        dx,dy=pb[0]-pa[0],pb[1]-pa[1];length=math.hypot(dx,dy);nx,ny=-dy/length,dx/length
        for sign in [-1,1]:
            a=(pa[0]+nx*sign*.90,pa[1]+ny*sign*.90,pa[2]-.44)
            b=(pb[0]+nx*sign*.90,pb[1]+ny*sign*.90,pb[2]-.44)
            # The inner landing-edge joist must stop at the stair mouth. Its
            # outer companion and existing transverse bearers support this
            # short landing; a beam across the opening would strike walkers.
            if leg==2 and sign==1:
                t=1.6/length;a=tuple(a[i]*(1-t)+b[i]*t for i in range(3))
            assembly.beam('longitudinal_joists',palette['wooddark'],a,b,.28,.25,sides=4)
            records.append({'a':a,'b':b,'width':.28,'depth':.25})
    rec=assembly.finish(1,1,0,start);S._tag(rec)
    bpy.context.view_layer.update()
    # This location is the last exact controller contact from the source-bound
    # runtime report. A capsule at that pose must be outside every new beam.
    from mathutils.geometry import closest_point_on_tri
    point=(-308.7024,221.7165,17.7125);axis=[Vector((point[0],point[1],point[2]+h)) for h in [.32,1.40]]
    min_distance=1000.
    for ob in rec['objects']:
        ob.data.calc_loop_triangles()
        for f in ob.data.loop_triangles:
            p,q,r=[ob.matrix_world@ob.data.vertices[i].co for i in f.vertices]
            # Triangle-to-capsule axis minimum is bounded conservatively by
            # 33 samples along its 1.08m segment (0.034m spacing).
            for i in range(33):
                test=axis[0].lerp(axis[1],i/32)
                min_distance=min(min_distance,(closest_point_on_tri(test,p,q,r)-test).length)
    result={'replaced':'Palm_Crescent_public_approach__longitudinal_joists','beams':records,'verified_pose_blender':point,'minimum_sampled_axis_clearance_m':min_distance,'body_radius_m':.32,'maximum_probe_spacing_m':1.08/32}
    # A full extra sample spacing margin makes this conservative between probes.
    if min_distance<=.32+1.08/32:raise RuntimeError('Grade joist still intersects controller body clearance')
    (ROOT/'checkpoints/palm_grade_joists.json').write_text(json.dumps(result,indent=2))
    bpy.context.scene['palm_grade_joists_v4']=True
    print('PALM_GRADE_JOISTS_VERIFIED',min_distance,flush=True)
    return result
