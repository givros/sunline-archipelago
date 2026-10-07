"""Source/runtime-identical metric shuttle law for the Sunline rail consists.

Only train assembly roots are animated. No mesh data is changed. Route normals
match railway.ribbon's centered tangent rule, so offset tracks use their actual
source geometry. Public animate_trains() leaves Blender at frame 1.
"""
import bisect
import json
import math
import bpy
from mathutils import Vector, Matrix
from layout import RAILS

FPS=24
KEYFRAME_STEP=6
CAR_PITCH=19.0
RAMP_SECONDS=5.0
DWELL_SECONDS=2.0
END_MARGIN=15.0


class Route:
    def __init__(self,record):
        self.id=record['id'];self.points=[Vector(p) for p in record['points']];self.arc=[0.0];self.normals=[];self.lanes={}
        for a,b in zip(self.points,self.points[1:]):self.arc.append(self.arc[-1]+(b-a).length)
        self.length=self.arc[-1]
        for i in range(len(self.points)):
            tangent=self.points[min(i+1,len(self.points)-1)]-self.points[max(0,i-1)];tangent.z=0;tangent.normalize();self.normals.append(Vector((-tangent.y,tangent.x,0)))

    def lane(self,offset=0):
        if offset not in self.lanes:
            points=[p+n*offset for p,n in zip(self.points,self.normals)];arc=[0.0]
            for a,b in zip(points,points[1:]):arc.append(arc[-1]+(b-a).length)
            self.lanes[offset]=(points,arc)
        return self.lanes[offset]

    def lane_distance(self,centerline_distance,offset=0):
        _,arc=self.lane(offset);d=min(self.length,max(0.0,centerline_distance));i=min(len(self.points)-2,max(0,bisect.bisect_right(self.arc,d)-1));t=(d-self.arc[i])/(self.arc[i+1]-self.arc[i]);return arc[i]+t*(arc[i+1]-arc[i])

    def sample(self,distance,offset=0):
        points,arc=self.lane(offset);distance=min(arc[-1],max(0.0,distance));i=min(len(points)-2,max(0,bisect.bisect_right(arc,distance)-1));den=arc[i+1]-arc[i];t=(distance-arc[i])/den if den else 0.0
        return points[i].lerp(points[i+1],t)

    def pose(self,distance,offset=0,rear=False):
        # The rear mesh assembly is rotated pi locally; its asymmetric bogie
        # centers are consequently +5.8/-5.5 rather than -5.8/+5.5.
        back,front=(-5.5,5.8) if rear else (-5.8,5.5)
        center=distance+(back+front)*.5;half=(front-back)*.5
        # Arc span is slightly longer than a rigid wheelbase on a bend. Solve
        # its support span so both actual bolster centers stay on the rails.
        low=half;high=half*1.04
        while (self.sample(center+high,offset)-self.sample(center-high,offset)).length<11.3 and high<20:high*=1.08
        for _ in range(22):
            mid=(low+high)*.5
            if (self.sample(center+mid,offset)-self.sample(center-mid,offset)).length<11.3:low=mid
            else:high=mid
        half=(low+high)*.5
        rear_s=center-half;front_s=center+half
        a=self.sample(rear_s,offset);b=self.sample(front_s,offset);direction=(b-a).normalized()
        correction=-(back+front)*.5
        origin=(a+b)*.5+direction*correction
        yaw=math.atan2(direction.y,direction.x)
        return origin,yaw,{'rear_bogie_target':a,'front_bogie_target':b,'rear_bogie_distance':rear_s,'front_bogie_distance':front_s,'rear_bogie_x':back,'front_bogie_x':front,'direction':direction,'chord_length':(b-a).length}

    def bogie_pose(self,distance,offset=0):
        pos=self.sample(distance,offset);direction=(self.sample(distance+.88,offset)-self.sample(distance-.88,offset)).normalized()
        return pos,math.atan2(direction.y,direction.x),direction


def shuttle_parameters(route_length,car_count,speed=7.5):
    low=END_MARGIN+(car_count-1)*CAR_PITCH;high=route_length-END_MARGIN;stroke=high-low
    if stroke<=10:raise ValueError('The train cannot fit safely on this route')
    ramp=min(RAMP_SECONDS,stroke/speed*.25)
    cruise=max(0.0,stroke/speed-ramp)
    travel=2*ramp+cruise
    period=2*(travel+DWELL_SECONDS)
    return {'minimum_head_distance':low,'maximum_head_distance':high,'stroke':stroke,'cruise_speed':float(speed),'ramp_seconds':ramp,'cruise_seconds':cruise,'travel_seconds':travel,'dwell_seconds':DWELL_SECONDS,'physical_period_seconds':period,'car_pitch':CAR_PITCH,'endpoint_margin':END_MARGIN}


def outward_distance(t,motion):
    """Integral of cosine-eased speed: acceleration, cruise, deceleration."""
    r=motion['ramp_seconds'];c=motion['cruise_seconds'];v=motion['cruise_speed'];D=motion['stroke']
    if t<=0:return 0.0
    if t<r:return v*.5*(t-r/math.pi*math.sin(math.pi*t/r))
    if t<r+c:return v*r*.5+v*(t-r)
    if t<2*r+c:
        q=t-r-c
        return D-v*r*.5+v*.5*(q+r/math.pi*math.sin(math.pi*q/r))
    return D


def phase_for_distance(distance,motion,direction=1):
    """Stable monotone inverse puts frame 1 at the authored initial distance."""
    d=min(motion['stroke'],max(0,distance-motion['minimum_head_distance']));lo=0.;hi=motion['travel_seconds']
    for _ in range(56):
        mid=(lo+hi)*.5
        if outward_distance(mid,motion)<d:lo=mid
        else:hi=mid
    phase=(lo+hi)*.5
    if direction<0:phase=motion['travel_seconds']+motion['dwell_seconds']+(motion['travel_seconds']-phase)
    return phase


def shuttle_head(elapsed_seconds,phase,motion,timeline_duration=None):
    # Integer frame count closes the loop exactly. Apply the same tiny rescale in
    # the runtime when physical period differs from representable 24fps duration.
    scale=motion['physical_period_seconds']/(timeline_duration or motion['physical_period_seconds'])
    t=(elapsed_seconds*scale+phase)%motion['physical_period_seconds'];travel=motion['travel_seconds'];dwell=motion['dwell_seconds'];low=motion['minimum_head_distance'];high=motion['maximum_head_distance']
    if t<travel:return low+outward_distance(t,motion)
    if t<travel+dwell:return high
    if t<2*travel+dwell:return high-outward_distance(t-travel-dwell,motion)
    return low


def _unwrap(angle,previous):
    while angle-previous>math.pi:angle-=math.tau
    while angle-previous<-math.pi:angle+=math.tau
    return angle


def _fcurves(action):
    if hasattr(action,'fcurves'):
        try:return list(action.fcurves)
        except AttributeError:pass
    curves=[]
    for layer in getattr(action,'layers',[]):
        for strip in layer.strips:
            for bag in getattr(strip,'channelbags',[]):curves.extend(bag.fcurves)
    return curves


def _articulate_bogies(car):
    """Create transform pivots and preserve every component's original matrix."""
    existing={str(o.get('bogie_role')):o for o in car.children if o.get('asset_type')=='train_bogie'}
    if len(existing)==2:return existing
    body=next((o for o in car.children if o.type=='EMPTY' and o.name.endswith('_BodyAssembly')),None)
    if body is None:raise RuntimeError('No editable body assembly found for '+car.name)
    bpy.context.view_layer.update()
    roles=('_BogieFrame','_Axle','_RailWheel','_WheelFlange','_WheelHub','_Suspension','_BogieOuterBeam')
    candidates=[o for o in body.children if o.type=='MESH' and any(r in o.name for r in roles)]
    pivots={};max_error=0.0;world_before={o.name:o.matrix_world.copy() for o in candidates}
    originals={o.name:(body.matrix_local@o.matrix_local, o.location.x<0) for o in candidates}
    for body_x in (-5.8,5.5):
        p=body.matrix_local@Vector((body_x,0,0));role='rear' if p.x<0 else 'front'
        name='TRAIN_BOGIE_'+str(car['train_id']).replace('SUNLINE_','')+'_'+str(car['car_index'])+'_'+role.upper()
        pivot_local=Matrix.Translation(p)
        pivot=bpy.data.objects.new(name,None);car.users_collection[0].objects.link(pivot);pivot.parent=car;pivot.matrix_basis=pivot_local;pivot.empty_display_type='ARROWS';pivot.empty_display_size=.6
        pivot['asset_type']='train_bogie';pivot['dynamic_owner']=name;pivot['motion_parent_car']=car.name;pivot['bogie_role']=role;pivot['car_index']=int(car['car_index']);pivot['train_id']=str(car['train_id']);pivot['route_id']=str(car['route_id']);pivot['track_offset']=float(car.get('track_offset',0));pivot['body_longitudinal_m']=float(p.x);pivot['wheelbase_m']=1.76
        for ob in candidates:
            relative,negative=originals[ob.name]
            if negative!=(body_x<0):continue
            local=pivot_local.inverted()@relative
            ob.parent=pivot;ob.matrix_parent_inverse=Matrix.Identity(4);ob.matrix_basis=local
        pivots[role]=pivot
    bpy.context.view_layer.update()
    for ob in candidates:
        before=world_before[ob.name];after=ob.matrix_world
        max_error=max(max_error,max(abs(before[i][j]-after[i][j]) for i in range(4) for j in range(4)))
    car['bogie_reparent_max_matrix_error']=max_error
    return pivots


def _drawbar_mesh():
    name='TRAIN_DrawbarSharedMesh'
    if name in bpy.data.meshes:return bpy.data.meshes[name]
    verts=[];faces=[];material_ids=[]
    def sleeve(x0,x1,radius,material_index):
        off=len(verts);n=12
        verts.extend([(x,radius*math.cos(math.tau*k/n),radius*math.sin(math.tau*k/n)) for x in (x0,x1) for k in range(n)])
        fs=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(k,(k+1)%n,(k+1)%n+n,k+n) for k in range(n)]
        faces.extend([tuple(off+k for k in f) for f in fs]);material_ids.extend([material_index]*len(fs))
    sleeve(-.5,.5,.095,0)
    sleeve(-.49,-.34,.14,1)
    sleeve(.34,.49,.14,1)
    sleeve(-.10,.10,.125,0)
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    for name,color in (('VEH_Underframe steel',(.07,.105,.12,1)),('VEH_Brushed marine steel',(.38,.49,.53,1))):
        mat=bpy.data.materials.get(name)
        if mat is None:mat=bpy.data.materials.new(name);mat.diffuse_color=color
        mesh.materials.append(mat)
    for polygon,index in zip(mesh.polygons,material_ids):polygon.material_index=index;polygon.use_smooth=len(polygon.vertices)==4
    return mesh


def _anchor(car,name,location):
    ob=bpy.data.objects.get(name)
    if ob is None:ob=bpy.data.objects.new(name,None);car.users_collection[0].objects.link(ob)
    ob.parent=car;ob.matrix_basis=Matrix.Translation(Vector(location));ob.empty_display_type='PLAIN_AXES';ob.empty_display_size=.12;ob['component_role']='coupling_attachment';return ob


def _world_driver(ob,path,index,expression,a,b):
    fc=ob.driver_add(path,index);driver=fc.driver;driver.type='SCRIPTED';driver.expression=expression
    for prefix,target in (('a',a),('b',b)):
        for axis in 'xyz':
            v=driver.variables.new();v.name=prefix+axis;v.type='TRANSFORMS';v.targets[0].id=target;v.targets[0].transform_type='LOC_'+axis.upper();v.targets[0].transform_space='WORLD_SPACE'


def _create_drawbars(groups):
    links=[];mesh=_drawbar_mesh()
    for train_id,cars in sorted(groups.items()):
        cars=sorted(cars,key=lambda o:int(o['car_index']))
        for j,(a,b) in enumerate(zip(cars,cars[1:])):
            name='TRAIN_DRAWBAR_'+train_id.replace('SUNLINE_','')+'_'+str(j)
            root=bpy.data.objects.get(name)
            if root is None:root=bpy.data.objects.new(name,None);a.users_collection[0].objects.link(root)
            root.animation_data_clear();root.empty_display_type='PLAIN_AXES';root.empty_display_size=.12;root.rotation_mode='XYZ'
            root['asset_type']='train_drawbar';root['dynamic_owner']=name;root['train_id']=train_id;root['link_index']=j;root['car_a']=a.name;root['car_b']=b.name;root['anchor_a_local']=[-9.27,0,.94];root['anchor_b_local']=[9.27,0,.94];root['motion_type']='live_coupling_anchors'
            if not root.children:
                ob=bpy.data.objects.new(name+'__TelescopicSteelLink',mesh);a.users_collection[0].objects.link(ob);ob.parent=root;ob['component_role']='telescopic_drawbar'
            aa=_anchor(a,name+'_AnchorA',(-9.27,0,.94));bb=_anchor(b,name+'_AnchorB',(9.27,0,.94))
            for i,axis in enumerate('xyz'):_world_driver(root,'location',i,'(a'+axis+'+b'+axis+')/2',aa,bb)
            _world_driver(root,'rotation_euler',2,'atan2(by-ay,bx-ax)',aa,bb)
            _world_driver(root,'scale',0,'sqrt((bx-ax)**2+(by-ay)**2+(bz-az)**2)',aa,bb)
            root.scale.y=1;root.scale.z=1
            links.append({'root':root,'a':aa,'b':bb,'id':name,'car_a':a.name,'car_b':b.name})
    return links


def _audit_pose(route,distance,offset,rear):
    origin,yaw,info=route.pose(distance,offset,rear);direction=info['direction']
    errors=[];wheel_errors=[]
    for role in ('rear','front'):
        local_x=info[role+'_bogie_x'];target=info[role+'_bogie_target'];bogie_distance=info[role+'_bogie_distance'];_,_,bogie_dir=route.bogie_pose(bogie_distance,offset);side=Vector((-bogie_dir.y,bogie_dir.x,0))
        errors.append((origin+direction*local_x-target).length)
        for axle_delta in (-.88,.88):
            for sign in (-1,1):
                actual=target+bogie_dir*axle_delta+side*(sign*.7175)
                # Restrict nearest rail test to the expected local arc interval.
                best=1e9
                for j in range(17):
                    d=bogie_distance+axle_delta-.40+j*.05
                    # Rail normals are sampled at the center track's corresponding
                    # segment parameter, rather than comparing unrelated lane arcs.
                    lp,la=route.lane(offset);i=min(len(lp)-2,max(0,bisect.bisect_right(la,d)-1));t=(d-la[i])/(la[i+1]-la[i]);base=route.points[i].lerp(route.points[i+1],t);normal=route.normals[i].lerp(route.normals[i+1],t);rail_point=base+normal*(offset+sign*.7175)
                    best=min(best,(actual-rail_point).length)
                wheel_errors.append(best)
    return max(errors),max(wheel_errors)


def animate_trains():
    routes={r['id']:Route(r) for r in RAILS}
    roots=[o for o in bpy.context.scene.objects if o.type=='EMPTY' and o.get('asset_type')=='train_car' and 'train_id' in o and 'car_index' in o]
    if not roots:raise RuntimeError('No TRAIN_CAR roots with route metadata exist; build stage 8 first')
    groups={}
    for ob in roots:groups.setdefault(str(ob['train_id']),[]).append(ob)
    records=[];scene=bpy.context.scene;scene.render.fps=FPS;scene.render.fps_base=1.;maximum_frame=1
    pivot_map={car.name:_articulate_bogies(car) for car in roots}
    plans=[]
    for train_id,cars in sorted(groups.items()):
        cars.sort(key=lambda o:int(o['car_index']));head=cars[0];route=routes[str(head['route_id'])];speed=float(head.get('speed',7.5));offset=float(head.get('track_offset',0));lane_length=route.lane(offset)[1][-1];motion=shuttle_parameters(lane_length,len(cars),speed);first=route.lane_distance(float(head['distance_on_route']),offset);phase=phase_for_distance(first,motion,1);plans.append((train_id,cars,route,speed,motion,first,phase,lane_length))
    common_frames=round(max(p[4]['physical_period_seconds'] for p in plans)*FPS);common_duration=common_frames/FPS
    audit={'max_bogie_center_to_track_m':0.,'max_wheel_tread_to_nearest_rail_m':0.,'max_neighbor_coupler_center_gap_m':0.,'max_arc_pitch_error_m':0.,'max_bogie_reparent_matrix_error':max(float(o.get('bogie_reparent_max_matrix_error',0)) for o in roots),'samples':0,'notes':['Both bogies independently swivel; rigid body uses an exact11.3m solved support chord.','Rear asset bogie positions are mirrored; source and runtime use the mirrored support chord.']}
    for train_id,cars,route,speed,motion,first,phase,lane_length in plans:
        frames=common_frames;duration=common_duration;endframe=frames+1;maximum_frame=max(maximum_frame,endframe)
        keys=list(range(1,endframe,KEYFRAME_STEP))
        if not keys or keys[-1]!=endframe:keys.append(endframe)
        previous={o.name:float(o.rotation_euler.z) for o in cars};car_records=[]
        for ob in cars:
            ob.animation_data_clear();ob.rotation_mode='XYZ'
            ob['motion_type']='cosine_ramp_shuttle';ob['motion_phase_seconds']=phase;ob['motion_duration_seconds']=duration;ob['motion_physical_period_seconds']=motion['physical_period_seconds'];ob['motion_head_min']=motion['minimum_head_distance'];ob['motion_head_max']=motion['maximum_head_distance'];ob['motion_ramp_seconds']=motion['ramp_seconds'];ob['motion_dwell_seconds']=motion['dwell_seconds'];ob['motion_car_pitch']=CAR_PITCH;ob['motion_fps']=FPS;ob['motion_keyframe_step']=KEYFRAME_STEP;ob['motion_rear_bogie_mirror']=str(ob.get('role',''))=='rear';ob['motion_distance_space']='offset_track_arc';ob['motion_initial_head_distance']=first;ob['motion_lane_length']=lane_length
            for pivot in pivot_map[ob.name].values():
                pivot.animation_data_clear();pivot.rotation_mode='XYZ';previous[pivot.name]=float(pivot.rotation_euler.z)
            car_records.append({'id':ob.name,'car_index':int(ob['car_index']),'track_offset':float(ob.get('track_offset',0)),'rear_bogie_mirror':str(ob.get('role',''))=='rear','authored_centerline_distance':float(ob['distance_on_route']),'initial_lane_distance':first-int(ob['car_index'])*CAR_PITCH,'bogies':{role:p.name for role,p in pivot_map[ob.name].items()}})
        for frame in keys:
            elapsed=(frame-1)/FPS;dhead=shuttle_head(elapsed,phase,motion,duration)
            for ob in cars:
                d=dhead-int(ob['car_index'])*CAR_PITCH;offset=float(ob.get('track_offset',0));rear=str(ob.get('role',''))=='rear';position,yaw,info=route.pose(d,offset,rear)
                yaw=_unwrap(yaw,previous[ob.name]);previous[ob.name]=yaw;ob.location=position;ob.rotation_euler=(0,0,yaw);ob.keyframe_insert(data_path='location',frame=frame,group='Rail motion');ob.keyframe_insert(data_path='rotation_euler',index=2,frame=frame,group='Rail motion')
                cs=math.cos(yaw);sn=math.sin(yaw)
                for role,pivot in pivot_map[ob.name].items():
                    support=info[role+'_bogie_distance'];pos,angle,_=route.bogie_pose(support,offset);delta=pos-position
                    pivot.location=(delta.x*cs+delta.y*sn,-delta.x*sn+delta.y*cs,delta.z)
                    angle=_unwrap(angle-yaw,previous[pivot.name]);previous[pivot.name]=angle;pivot.rotation_euler=(0,0,angle)
                    pivot.keyframe_insert(data_path='location',frame=frame,group='Bogie articulation');pivot.keyframe_insert(data_path='rotation_euler',index=2,frame=frame,group='Bogie articulation')
        for ob in cars:
            for node in [ob]+list(pivot_map[ob.name].values()):
                for fc in _fcurves(node.animation_data.action):
                    for key in fc.keyframe_points:key.interpolation='LINEAR'
                node.animation_data.action.name=node.name+'__ShuttleMotion'
        # Sample every 4m across the usable line; isolate true rigid chassis error.
        stations=max(32,int(motion['stroke']/4))
        for j in range(stations+1):
            dhead=motion['minimum_head_distance']+motion['stroke']*j/stations;poses=[]
            distances=[dhead-int(o['car_index'])*CAR_PITCH for o in cars]
            audit['max_arc_pitch_error_m']=max(audit['max_arc_pitch_error_m'],max(abs(a-b-CAR_PITCH) for a,b in zip(distances,distances[1:])))
            for ob in cars:
                d=dhead-int(ob['car_index'])*CAR_PITCH;offset=float(ob.get('track_offset',0));rear=str(ob.get('role',''))=='rear'
                bogie,wheel=_audit_pose(route,d,offset,rear);audit['max_bogie_center_to_track_m']=max(audit['max_bogie_center_to_track_m'],bogie);audit['max_wheel_tread_to_nearest_rail_m']=max(audit['max_wheel_tread_to_nearest_rail_m'],wheel);audit['samples']+=1
                pos,yaw,_=route.pose(d,offset,rear);poses.append((pos,Vector((math.cos(yaw),math.sin(yaw),0))))
            for a,b in zip(poses,poses[1:]):
                ca=a[0]-a[1]*9.27;cb=b[0]+b[1]*9.27;audit['max_neighbor_coupler_center_gap_m']=max(audit['max_neighbor_coupler_center_gap_m'],(ca-cb).length)
        records.append({'id':train_id,'route_id':route.id,'route_centerline_length_m':route.length,'route_lane_length_m':lane_length,'distance_space':'offset_track_arc','initial_head_distance':first,'phase_seconds':phase,'motion':motion,'duration_seconds':duration,'frame_start':1,'frame_end':endframe,'keyframe_step':KEYFRAME_STEP,'keyframes_per_car':len(keys),'cars':car_records,'effective_peak_speed_m_s':speed*motion['physical_period_seconds']/duration})
    links=_create_drawbars(groups)
    audit['max_drawbar_endpoint_contact_error_m']=0.0
    for i in range(20):
        frame=1+(maximum_frame-1)*i/19;whole=int(frame);scene.frame_set(whole,subframe=frame-whole);bpy.context.view_layer.update()
        for link in links:
            root=link['root'];a=root.matrix_world@Vector((-.5,0,0));b=root.matrix_world@Vector((.5,0,0));audit['max_drawbar_endpoint_contact_error_m']=max(audit['max_drawbar_endpoint_contact_error_m'],(a-link['a'].matrix_world.translation).length,(b-link['b'].matrix_world.translation).length)
    scene.frame_start=1;scene.frame_end=maximum_frame;scene.frame_set(1)
    for k,v in list(audit.items()):
        if isinstance(v,float):audit[k]=round(v,6)
    audit['wheel_contact_tolerance_m']=.075
    audit['bogie_center_tolerance_m']=.005
    audit['operational_contact_pass']=audit['max_bogie_center_to_track_m']<=.005 and audit['max_wheel_tread_to_nearest_rail_m']<=.075 and audit['max_drawbar_endpoint_contact_error_m']<=.001
    manifest={'system':'Sunline operational coastal train shuttles','status':'implemented in Blender source keyframes','fps':FPS,'frame_start':1,'frame_end':maximum_frame,'duration_seconds':(maximum_frame-1)/FPS,'loop_boundary':'Last frame duplicates frame 1 exactly; playback loops frames 1 through end-1.','rail_gauge_m':1.435,'car_pitch_m':CAR_PITCH,'geometry_unchanged':True,'keyframe_interpolation':'LINEAR every 6 frames, plus exact endpoint','track_sampling':'Centerline arc distance; linearly interpolate vertex positions offset by central-difference vertex normals, identical to source rail ribbon.','body_pose':'Sample rear/front bogie supports at d-5.8,d+5.5. Origin is chord midpoint +0.15 along normalized chord. Rear-car mesh is mirrored: use d-5.5,d+5.8 and midpoint -0.15 along chord. Heading always follows increasing route distance, including reversing motion.','motion_mapping':'For stroke D, cruise speed v, ramp r: c=D/v-r; travel=2r+c. Forward distance: 0.5*v*(t-r/pi*sin(pi*t/r)) for t<r; v*r/2+v*(t-r) for r<=t<r+c; D-v*r/2+0.5*v*(q+r/pi*sin(pi*q/r)) for q=t-r-c in [0,r]. Travel forward, dwell 2s, travel backward, dwell 2s. Add initial phase, wrap modulo physical period; rescale runtime seconds by physical period / timeline duration.','runtime_matching':'Use the same route normals, motion formula, phase and rear-bogie mirror. For exact Blender subframe equality evaluate analytic poses at the surrounding 6-frame keyframes, unwrap yaw, then interpolate position/yaw linearly.','trains':records,'dimensional_validation':audit}
    manifest['dynamic_root_count']=len(roots)*3+len(links)
    manifest['bogie_pivot_count']=len(roots)*2
    manifest['drawbar_count']=len(links)
    manifest['drawbars']=[{k:v for k,v in link.items() if k not in ('root','a','b')} for link in links]
    manifest['drawbar_motion']='Live source transform drivers use car-local coupling anchors A=[−9.27,0,.94], B=[9.27,0,.94]. World position=(A+B)/2, yaw=atan2(B.y−A.y,B.x−A.x), X scale=distance(A,B), Y/Z scale=1. Shared mesh endpoints are local X±0.5. Runtime derives the same anchors from current interpolated car matrices; endpoints remain continuously connected at subframes.'
    manifest['geometry_unchanged']=f"Original vehicle meshes unchanged; {len(links)} separate detailed articulated drawbar link meshes added using one shared geometry."
    manifest['track_sampling']='First offset every route vertex by its central-difference normal times track_offset. Compute cumulative arc lengths of those offset vertices. All motion distances and19m car pitches use this actual track arc. Convert authored centerline head distance by its segment interpolation into the offset arc for frame1.'
    manifest['body_pose']='Use back/front local bogie positions −5.8/+5.5 (rear car −5.5/+5.8). Set centerArc=d+(back+front)/2. Solve halfSpan by22 bisections, starting low=5.65/high=5.65*1.04 and growing high by1.08 until the chord between sample(centerArc±halfSpan) is11.3m. Origin is chord midpoint−normalizedChord*(back+front)/2; body yaw follows normalizedChord.'
    manifest['bogie_pose']='For each rear/front support distance, position=offset track sample(supportDistance); yaw=atan2 of sample(supportDistance+.88)−sample(supportDistance−.88). Source pivots are children of car root with these world poses transformed into parent local coordinates. Runtime may export/animate all30 nodes as independent world roots while retaining pivot-local mesh matrices.'
    manifest['runtime_matching']='Evaluate the same motion law and solved car/bogie poses. For exact Blender subframe equality, interpolate surrounding6-frame car world position/yaw AND bogie parent-local position/yaw separately, then compose car and pivot matrices. All trains use the shared maximum rounded timeline duration; each physical cycle is rescaled by its own physical_period_seconds/common duration.'
    print('TRAIN_ANIMATION_COMPLETE',json.dumps({'trains':len(records),'cars':len(roots),'bogies':len(roots)*2,'drawbars':len(links),'duration_seconds':manifest['duration_seconds'],'frame_end':maximum_frame,'validation':audit}),flush=True)
    return manifest
