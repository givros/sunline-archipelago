"""Editable tropical marine fleet and coastal passenger train assemblies.

All geometry is real mesh geometry. Blender coordinates: Z up, local +X forward.
Public factories return (assembly_empty, dimensional_metadata).
"""
import bpy
import math
from mathutils import Vector

_mesh_cache = {}
_materials = {}


def material(name, color, roughness=.45, metallic=0):
    key = 'VEH_' + name
    mat = bpy.data.materials.get(key)
    if mat is None:
        mat = bpy.data.materials.new(key)
        mat.diffuse_color = (*color, 1)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get('Principled BSDF')
        bsdf.inputs['Base Color'].default_value = (*color, 1)
        bsdf.inputs['Roughness'].default_value = roughness
        bsdf.inputs['Metallic'].default_value = metallic
    return mat


def palette():
    return {
        'ivory': material('Ivory enamel', (.90,.90,.82), .27),
        'white': material('Porcelain white', (.95,.97,.97), .23),
        'blue': material('Ocean blue enamel', (.018,.11,.35), .27, .15),
        'teal': material('Patina turquoise', (.04,.37,.41), .38),
        'red': material('Fishing terracotta', (.53,.105,.065), .4),
        'yellow': material('Marine ochre', (.93,.61,.13), .4),
        'black': material('Rubber graphite', (.022,.028,.034), .72),
        'steel': material('Brushed marine steel', (.38,.49,.53), .28, .8),
        'darksteel': material('Underframe steel', (.07,.105,.12), .5, .55),
        'glass': material('Marine window glass', (.018,.092,.133), .13, .48),
        'wood': material('Weathered teak', (.43,.245,.11), .74),
        'woodlight': material('Fresh deck teak', (.64,.39,.19), .62),
        'rope': material('Natural hemp rope', (.55,.46,.30), .95),
        'sail': material('Ivory sailcloth', (.93,.90,.76), .82),
        'light': material('Headlamp lens', (.98,.91,.64), .13),
        'seat': material('Indigo canvas', (.09,.23,.32), .9),
        'fender': material('Fender rubber', (.63,.67,.63), .86),
    }


def _mesh(name, vertices, faces, mat, parent=None, key=None, smooth=False):
    full_key = (key, mat.name, smooth) if key else None
    data = _mesh_cache.get(full_key) if full_key else None
    if data is None:
        data = bpy.data.meshes.new(name + '_Mesh')
        data.from_pydata(vertices, [], faces)
        data.materials.append(mat)
        data.update()
        if smooth:
            for polygon in data.polygons:
                polygon.use_smooth = True
        if full_key:
            _mesh_cache[full_key] = data
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    if parent:
        obj.parent = parent
    obj['asset_component'] = name
    return obj


def _box(name, center, size, mat, parent, rotation=0):
    verts = [(x,y,z) for z in (-.5,.5) for y in (-.5,.5) for x in (-.5,.5)]
    faces = [(0,2,3,1),(4,5,7,6),(0,1,5,4),(2,6,7,3),(0,4,6,2),(1,3,7,5)]
    obj = _mesh(name, verts, faces, mat, parent, key='unit_box')
    obj.location = center
    obj.scale = size
    obj.rotation_euler.z = rotation
    return obj


def _tube(name, start, end, radius, mat, parent, sides=10, radius_end=None):
    top = radius if radius_end is None else radius_end
    key = ('tube', sides, round(top/radius,6))
    verts = [(math.cos(i*math.tau/sides), math.sin(i*math.tau/sides), -.5) for i in range(sides)]
    verts += [(math.cos(i*math.tau/sides)*top/radius, math.sin(i*math.tau/sides)*top/radius, .5) for i in range(sides)]
    faces = [tuple(range(sides-1,-1,-1)), tuple(range(sides,sides*2))]
    faces += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    obj = _mesh(name, verts, faces, mat, parent, key=key, smooth=True)
    direction = Vector(end)-Vector(start)
    obj.location = (Vector(start)+Vector(end))*.5
    obj.scale = (radius,radius,direction.length)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = direction.to_track_quat('Z','Y')
    return obj


def _line(name, points, radius, mat, root, sides=8):
    for i in range(len(points)-1):
        _tube(name+f'_{i:02d}',points[i],points[i+1],radius,mat,root,sides)


def _root(name, x,y,z,angle):
    root = bpy.data.objects.new(name,None)
    bpy.context.collection.objects.link(root)
    root.empty_display_type='PLAIN_AXES'
    root.empty_display_size=1
    root.location=(x,y,z)
    root.rotation_euler.z=angle
    root['asset_role']='vehicle_assembly'
    return root


def _hull(root, length, beam, draft, side, p):
    # Twelve cross sections retain the shaped stern, full working midbody and fine bow.
    stations=[(-.50,.68),(-.46,.88),(-.35,.97),(-.2,1),(0,1),(.16,.94),(.29,.78),(.39,.53),(.47,.22),(.51,.012)]
    verts=[]
    profile=[(-1,1),(-.97,.42),(-.74,-.4),(-.38,-.85),(0,-1),(.38,-.85),(.74,-.4),(.97,.42),(1,1)]
    for sx,width in stations:
        rise=.08 + max(0,sx)*.44
        for py,pz in profile:
            zz=.58*pz if pz>=0 else draft*pz
            verts.append((sx*length,py*width*beam*.5,zz+rise))
    faces=[]
    stride=len(profile)
    for s in range(len(stations)-1):
        for j in range(stride-1):
            faces.append((s*stride+j,s*stride+j+1,(s+1)*stride+j+1,(s+1)*stride+j))
    faces += [tuple(range(stride-1,-1,-1)), tuple(range((len(stations)-1)*stride,len(stations)*stride))]
    _mesh(root.name+'_SculptedHull',verts,faces,side,root,key=('hull',length,beam,draft),smooth=True)
    outline=[]
    for sx,width in stations:
        outline.append((sx*length,-width*beam*.5,.69+max(0,sx)*.44))
    outline += [(sx*length,width*beam*.5,.69+max(0,sx)*.44) for sx,width in reversed(stations)]
    _mesh(root.name+'_TeakDeck',outline,[tuple(range(len(outline)))],p['woodlight'],root,key=('deck',length,beam))
    _line(root.name+'_Gunwale',outline+[outline[0]],.074,p['ivory'],root,10)
    # Narrow waterline stripe follows the actual hull sides instead of a rectangular wrap.
    for sign in (-1,1):
        pts=[(sx*length,sign*width*beam*.493,.19+max(0,sx)*.44) for sx,width in stations]
        _line(root.name+'_WaterlineStripe',pts,.038,p['ivory'],root)
    # Plank joints are inset deck lines, deliberately kept thin at human scale.
    for sx in (-.43,-.37,-.31,-.25,-.19,-.13,-.07,-.01,.05,.11,.17,.23,.29,.35,.41):
        nearest=min(stations,key=lambda s:abs(s[0]-sx))[1]
        _box(root.name+'_DeckPlankJoint',(length*sx,0,.695+max(0,sx)*.44),(.016,beam*nearest*.87,.009),p['wood'],root)
    return stations


def _cabin(root,p,center,size,roofcolor=None):
    x,y,z=center; L,W,H=size
    _box(root.name+'_CabinShell',(x,y,z),(L,W,H),p['ivory'],root)
    _box(root.name+'_CabinSill',(x,y,z-H*.3),(L+.06,W+.06,.13),p['wood'],root)
    _box(root.name+'_CabinRoof',(x,y,z+H*.5+.07),(L+.35,W+.32,.16),roofcolor or p['white'],root)
    # Large glazing with real opaque pillars between panes and frames around them.
    for sign in (-1,1):
        for j in (-1,0,1):
            _box(root.name+'_SideWindow',(x+j*L*.29,y+sign*(W*.5+.012),z+H*.14),(L*.255,.027,H*.47),p['glass'],root)
        _box(root.name+'_CabinSideRail',(x,y+sign*(W*.5+.04),z-H*.08),(L-.14,.06,.055),p['steel'],root)
    for sign in (-1,1):
        for j in (-1,1):
            _box(root.name+'_Windscreen',(x+sign*(L*.5+.012),y+j*W*.23,z+H*.14),(.028,W*.40,H*.47),p['glass'],root)
    _tube(root.name+'_RadioAntenna',(x-.2,y,z+H*.5+.14),(x-.27,y,z+H*.5+1.6),.018,p['steel'],root)
    _box(root.name+'_NavigationLight',(x+.2,y,z+H*.5+.22),(.23,.22,.12),p['light'],root)


def _rails(root,p,length,beam,regions=('bow','stern')):
    for sign in (-1,1):
        if 'bow' in regions:
            points=[(length*t,sign*beam*w,.85+max(0,t)*.3) for t,w in ((.15,.46),(.28,.39),(.39,.28),(.48,.08))]
            tops=[(a,b,c+.66) for a,b,c in points]
            _line(root.name+'_BowSafetyRail',tops,.025,p['steel'],root)
            for a,b,c in points:
                _tube(root.name+'_RailStanchion',(a,b,c),(a,b,c+.66),.027,p['steel'],root)
        if 'stern' in regions:
            pts=[(-length*.46,sign*beam*.36,1.2),(-length*.34,sign*beam*.45,1.2),(-length*.22,sign*beam*.46,1.2)]
            _line(root.name+'_SternSafetyRail',pts,.025,p['steel'],root)
            for a,b,c in pts:
                _tube(root.name+'_RailStanchion',(a,b,.68),(a,b,c),.028,p['steel'],root)


def _fittings(root,p,length,beam,kind):
    for sign in (-1,1):
        for xx in (-length*.28,length*.22):
            yy=sign*beam*.47
            _tube(root.name+'_Fender',(xx,yy,.13),(xx,yy,.64),.13,p['fender'],root,12)
            _tube(root.name+'_FenderRope',(xx,yy,.65),(xx+.08,yy,.99),.018,p['rope'],root,6)
        for xx in (-length*.40,length*.34):
            _box(root.name+'_MooringCleatBase',(xx,sign*beam*.38,.77),(.24,.13,.07),p['steel'],root)
            _tube(root.name+'_MooringCleat',(xx,sign*beam*.38,.78),(xx,sign*beam*.38,.93),.04,p['steel'],root)
            _tube(root.name+'_MooringCleatTop',(xx-.15,sign*beam*.38,.93),(xx+.15,sign*beam*.38,.93),.035,p['steel'],root)
    # Stern ladder and twin rudder/propulsion details remain separate editable parts.
    for yy in (-.35,.35):
        _tube(root.name+'_SwimLadder',(-length*.505,yy,-.05),(-length*.505,yy,.93),.035,p['steel'],root)
    for zz in (.10,.38,.66):
        _tube(root.name+'_LadderRung',(-length*.515,-.35,zz),(-length*.515,.35,zz),.029,p['steel'],root)
    if kind in ('speed','utility','fishing'):
        for yy in ((-.42,.42) if kind=='speed' else (0,)):
            _box(root.name+'_OutboardPowerhead',(-length*.525,yy,.43),(.62,.43,.65),p['darksteel'],root)
            _box(root.name+'_OutboardLeg',(-length*.535,yy,-.12),(.20,.14,.8),p['darksteel'],root)
            _tube(root.name+'_PropellerShaft',(-length*.57,yy,-.4),(-length*.52,yy,-.4),.08,p['steel'],root)
            for angle in (0,math.tau/3,math.tau*2/3):
                _tube(root.name+'_PropellerBlade',(-length*.57,yy,-.4),(-length*.575,yy+.27*math.cos(angle),-.4+.27*math.sin(angle)),.053,p['steel'],root,6,radius_end=.021)


def _lifering(root,p,center,radius=.3):
    x,y,z=center
    points=[(x+radius*math.cos(i*math.tau/20),y,z+radius*math.sin(i*math.tau/20)) for i in range(21)]
    for i in range(20):
        _tube(root.name+'_Lifebuoy',points[i],points[i+1],.066,p['red'] if i//3%2 else p['ivory'],root,8)


def _sail_mesh(root,p,name,corners,billow):
    a,b,c=[Vector(v) for v in corners]
    n=10; verts=[]; index={}
    for i in range(n+1):
        for j in range(n+1-i):
            u=i/n;v=j/n;w=1-u-v
            pt=a*w+b*u+c*v
            pt.y+=billow*27*u*v*w
            index[(i,j)]=len(verts);verts.append(tuple(pt))
    faces=[]
    for i in range(n):
        for j in range(n-i):
            faces.append((index[(i,j)],index[(i+1,j)],index[(i,j+1)]))
            if j<n-i-1:
                faces.append((index[(i+1,j)],index[(i+1,j+1)],index[(i,j+1)]))
    obj=_mesh(name,verts,faces,p['sail'],root,smooth=True)
    obj['double_sided']=True
    _line(name+'_Edge',[corners[0],corners[1],corners[2],corners[0]],.017,p['rope'],root,6)
    return obj


def boat(name,x,y,z=0,angle=0,kind='fishing',variant=0,scale=1):
    """Boat waterline at z, bow points along local +X; angle in radians."""
    p=palette(); root=_root(name,x,y,z,angle)
    dimensions={'fishing':(10.4,3.45, .62),'sail':(13.1,3.5,.88),'speed':(8.6,2.65,.45),'yacht':(18.0,5.1,1.03),'taxi':(13.8,4.1,.68),'utility':(8.8,3.05,.56)}
    if kind not in dimensions: raise ValueError('Unknown boat kind '+kind)
    L,B,D=dimensions[kind]
    color=[p['teal'],p['blue'],p['red'],p['ivory']][variant%4]
    _hull(root,L,B,D,color,p)
    _rails(root,p,L,B,('bow','stern'))
    _fittings(root,p,L,B,kind)
    if kind=='fishing':
        _cabin(root,p,(L*.06,0,1.57),(L*.29,B*.66,1.65),p['teal'])
        # Working aft deck, bait boxes, gantry and rod holders.
        for xx,yy in ((-L*.33,-.65),(-L*.20,.62)):
            _box(name+'_FishCrate',(xx,yy,.90),(1.05,.74,.43),p['wood'],root)
            for jj in (-.24,0,.24):
                _box(name+'_CrateSlat',(xx,yy+jj,1.13),(1.08,.09,.08),p['woodlight'],root)
        for yy in (-B*.35,B*.35):
            _tube(name+'_FishingGantryLeg',(-L*.23,yy,.7),(-L*.23,yy,2.75),.06,p['steel'],root)
            _tube(name+'_FishingRod',(-L*.38,yy,.95),(-L*.56,yy*1.35,2.6),.027,p['darksteel'],root)
        _tube(name+'_FishingGantryCross',(-L*.23,-B*.35,2.75),(-L*.23,B*.35,2.75),.07,p['steel'],root)
        _lifering(root,p,(L*.035,-B*.34,1.42))
        _box(name+'_BowAnchorWinch',(L*.34,0,.95),(.58,.42,.24),p['darksteel'],root)
    elif kind=='sail':
        _cabin(root,p,(-.35,0,1.12),(4.3,B*.62,.83),p['ivory'])
        _box(name+'_CockpitWell',(-L*.28,0,.8),(2.7,B*.60,.2),p['darksteel'],root)
        for yy in (-B*.24,B*.24):
            _box(name+'_CockpitCushion',(-L*.28,yy,1.02),(2.5,.39,.22),p['seat'],root)
        mx=L*.07; mast_top=(mx,0,14.8)
        _tube(name+'_Mast',(mx,0,.8),mast_top,.09,p['ivory'],root,12,radius_end=.045)
        _tube(name+'_Boom',(mx,0,2.5),(-L*.34,0,2.5),.072,p['steel'],root)
        _sail_mesh(root,p,name+'_Mainsail',[(mx+.07,.03,14.4),(mx+.07,.03,2.66),(-L*.34,.03,2.66)],.54)
        _sail_mesh(root,p,name+'_Headsail',[(mx+.13,-.025,13.7),(L*.455,-.025,1.15),(mx+.2,-.025,2.4)],-.40)
        for target in ((L*.47,0,.95),(-L*.42,0,.77),(mx,-B*.46,.8),(mx,B*.46,.8)):
            _tube(name+'_StandingRigging',mast_top,target,.016,p['steel'],root,6)
        _tube(name+'_SteeringPedestal',(-L*.36,0,.82),(-L*.36,0,1.48),.058,p['steel'],root)
        ring=[(-L*.36,math.cos(i*math.tau/20)*.33,1.46+math.sin(i*math.tau/20)*.33) for i in range(21)]
        _line(name+'_HelmWheel',ring,.025,p['steel'],root)
        _lifering(root,p,(-L*.43,-B*.38,1.0),.24)
    elif kind=='speed':
        _box(name+'_CockpitFloor',(-L*.14,0,.82),(L*.5,B*.70,.15),p['ivory'],root)
        for xx in (-L*.23,-L*.045):
            for yy in (-B*.21,B*.21):
                _box(name+'_UpholsteredSeat',(xx,yy,1.08),(.83,.66,.24),p['ivory'],root)
                _box(name+'_SeatBack',(xx-.32,yy,1.42),(.20,.66,.63),p['seat'],root)
        # Angled wrap windshield with side wings.
        for sign in (-1,1):
            pts=[(L*.11,sign*.06,1.2),(L*.11,sign*B*.37,1.2),(L*.045,sign*B*.34,1.92),(L*.045,sign*.06,1.92)]
            _mesh(name+'_AngledWindshield',pts,[(0,1,2,3)],p['glass'],root)
            _line(name+'_WindscreenFrame',pts+[pts[0]],.033,p['steel'],root)
        _box(name+'_BowSunpad',(L*.28,0,1.02),(L*.23,B*.45,.19),p['ivory'],root)
        _box(name+'_SternSwimPlatform',(-L*.52,0,.52),(.59,B*.66,.13),p['woodlight'],root)
    elif kind=='yacht':
        _cabin(root,p,(-.25,0,1.94),(L*.44,B*.68,2.3))
        _cabin(root,p,(L*.012,0,3.63),(L*.27,B*.54,1.09))
        for xx in (-L*.24,-L*.14):
            _box(name+'_FlybridgeSofa',(xx,0,3.30),(1.3,B*.5,.32),p['ivory'],root)
        _box(name+'_Sunpad',(L*.32,0,1.1),(L*.18,B*.5,.31),p['ivory'],root)
        _box(name+'_BathingPlatform',(-L*.53,0,.58),(1.1,B*.80,.19),p['woodlight'],root)
        for yy in (-.55,.55):
            _tube(name+'_RadarArch',(L*.01,yy,4.28),(-L*.03,yy,5.28),.09,p['white'],root)
        _box(name+'_RadarPod',(-L*.03,0,5.3),(1.3,.5,.2),p['white'],root)
        _lifering(root,p,(-L*.29,-B*.37,1.45))
    elif kind=='taxi':
        _cabin(root,p,(L*.055,0,1.71),(L*.64,B*.77,1.9),p['yellow'])
        # Clearly readable passenger door and low aft boarding platform.
        for sign in (-1,1):
            _box(name+'_PassengerDoor',(-L*.16,sign*B*.392,1.53),(.83,.05,1.55),p['blue'],root)
            _box(name+'_DoorWindow',(-L*.16,sign*B*.402,1.92),(.58,.03,.56),p['glass'],root)
        _box(name+'_AftBoardingDeck',(-L*.42,0,.74),(L*.13,B*.73,.13),p['woodlight'],root)
        _lifering(root,p,(-L*.28,-B*.397,1.7))
        _box(name+'_DestinationSign',(L*.05,-B*.41,2.35),(3.7,.07,.22),p['blue'],root)
    else:
        _cabin(root,p,(L*.17,0,1.44),(L*.24,B*.57,1.43),p['teal'])
        _box(name+'_CargoPallet',(-L*.18,0,.84),(2.9,B*.7,.24),p['wood'],root)
        for xx,yy in ((-2,-.55),(-.85,.55)):
            _box(name+'_CargoCrate',(xx,yy,1.35),(1.15,.90,.8),p['woodlight'],root)
            for sx in (-.39,.39):
                _box(name+'_CrateBand',(xx+sx,yy,1.35),(.075,.92,.83),p['steel'],root)
        _lifering(root,p,(L*.16,-B*.3,1.38))
    root.scale=(scale,scale,scale)
    root['asset_type']='boat';root['boat_kind']=kind;root['bow_axis']='+X';root['waterline']=z
    root['length_m']=L*scale;root['beam_m']=B*scale
    return root, {'kind':kind,'length':L*scale,'beam':B*scale,'draft':D*scale,'components':len(root.children)}


def _train_body(root,p,role):
    profile=[(-1.05,1.15),(-1.43,1.34),(-1.50,1.65),(-1.50,3.21),(-1.40,3.59),(-1.13,3.85),(-.60,4.02),(0,4.07),(.60,4.02),(1.13,3.85),(1.40,3.59),(1.50,3.21),(1.50,1.65),(1.43,1.34),(1.05,1.15)]
    # End cars have a long tapered driver's cab with a lowered streamlined nose.
    sections=[(-8.8,1,1,0),(-8.45,1,1,0),(6.15,1,1,0),(7.05,.94,.94,.06),(8.05,.72,.73,.30),(8.95,.34,.46,.59)] if role in ('front','rear') else [(-8.8,.95,.98,.02),(-8.45,1,1,0),(8.45,1,1,0),(8.8,.95,.98,.02)]
    verts=[(xx,yy*ys,zz*zs+zoff) for xx,ys,zs,zoff in sections for yy,zz in profile]
    n=len(profile);faces=[]
    for s in range(len(sections)-1):
        for j in range(n):
            faces.append((s*n+j,s*n+(j+1)%n,(s+1)*n+(j+1)%n,(s+1)*n+j))
    faces += [tuple(range(n-1,-1,-1)),tuple(range((len(sections)-1)*n,len(sections)*n))]
    return _mesh(root.name+'_StreamlinedBody',verts,faces,p['white'],root,key=('trainbody',role),smooth=True)


def train_car(name,x,y,z,angle=0,role='middle',variant=0):
    """19m coupling pitch, standard gauge 1.435m; rail contact datum = z.

    The rear car's nose is on -X; all groups travel in +X.
    """
    if role not in ('front','middle','rear'): raise ValueError('role must be front, middle or rear')
    p=palette(); root=_root(name,x,y,z,angle)
    # A nested orientation node mirrors only the rear carriage assembly.
    bodyroot=_root(name+'_EditableComponents',0,0,0,math.pi if role=='rear' else 0)
    bodyroot.parent=root
    _train_body(bodyroot,p,role)
    bodyroot.name=name+'_BodyAssembly'
    _box(name+'_Underframe',(0,0,1.04),(16.1,2.46,.31),p['darksteel'],bodyroot)
    for xx in (-3.6,0,3.1):
        _box(name+'_UnderfloorEquipment',(xx,0,.83),(2.1,1.85,.37),p['darksteel'],bodyroot)
    # Shared wheel meshes orient along Y. Centers are exactly at track gauge.
    wheel_r=.46
    for bogie_x in (-5.8,5.5):
        _box(name+'_BogieFrame',(bogie_x,0,.69),(2.94,2.08,.32),p['darksteel'],bodyroot)
        for axle_x in (bogie_x-.88,bogie_x+.88):
            _tube(name+'_Axle',(axle_x,-.96,wheel_r),(axle_x,.96,wheel_r),.12,p['darksteel'],bodyroot,12)
            for side in (-1,1):
                yy=side*.7175
                _tube(name+'_RailWheel',(axle_x,yy-.075,wheel_r),(axle_x,yy+.075,wheel_r),wheel_r,p['darksteel'],bodyroot,24)
                _tube(name+'_WheelFlange',(axle_x,yy-side*.08,wheel_r),(axle_x,yy-side*.10,wheel_r),.487,p['steel'],bodyroot,24)
                _tube(name+'_WheelHub',(axle_x,side*.94,wheel_r),(axle_x,side*1.13,wheel_r),.16,p['steel'],bodyroot,16)
                _box(name+'_Suspension',(axle_x,side*1.02,.98),(.38,.31,.40),p['black'],bodyroot)
        for yy in (-1.1,1.1):
            _box(name+'_BogieOuterBeam',(bogie_x,yy,.71),(2.5,.15,.24),p['steel'],bodyroot)
    # Blue belt and dark window band are separate metal / glazing components.
    end_x=5.95 if role!='middle' else 8.3
    middle_x=(end_x-8.3)*.5; run_length=end_x+8.3
    for sign in (-1,1):
        _box(name+'_BlueLowerStripe',(middle_x,sign*1.507,1.75),(run_length,.025,.44),p['blue'],bodyroot)
        _box(name+'_BlueUpperPinstripe',(middle_x,sign*1.513,3.24),(run_length,.025,.09),p['blue'],bodyroot)
        _box(name+'_WindowGasketBand',(middle_x,sign*1.505,2.69),(run_length,.018,.83),p['black'],bodyroot)
        xs=[-6.9,-5.53,-4.16,-2.79,-1.42,-.05,1.32,2.69,4.06,5.43,6.8]
        for window_x in xs:
            if window_x>end_x-.4:continue
            if -6<window_x<-5:continue
            if 4<window_x<5:continue
            _box(name+'_PassengerWindow',(window_x,sign*1.524,2.73),(1.13,.038,.65),p['glass'],bodyroot)
            _box(name+'_WindowDivider',(window_x+.61,sign*1.53,2.73),(.10,.043,.80),p['white'],bodyroot)
        for dx in (-5.65,4.13):
            _box(name+'_PassengerDoor',(dx,sign*1.528,2.29),(.98,.041,1.81),p['ivory'],bodyroot)
            _box(name+'_DoorGlass',(dx,sign*1.554,2.64),(.60,.015,.89),p['glass'],bodyroot)
            _box(name+'_DoorSplit',(dx,sign*1.571,2.18),(.027,.027,1.55),p['steel'],bodyroot)
            _box(name+'_DoorSill',(dx,sign*1.60,1.33),(1.08,.25,.08),p['steel'],bodyroot)
            for offset in (-.16,.16):
                _box(name+'_DoorHandle',(dx+offset,sign*1.58,1.97),(.028,.03,.18),p['steel'],bodyroot)
        _box(name+'_CarNumberPlate',(-.65,sign*1.551,1.77),(.66,.015,.23),p['ivory'],bodyroot)
    # Roof air conditioning, access panels, edge drains and equipment grilles.
    for xx in (-3.8,1.65):
        _box(name+'_RoofHVAC',(xx,0,4.14),(2.8,1.55,.30),p['ivory'],bodyroot)
        for slat in range(9):
            _box(name+'_HVACLouver',(xx-1.02+slat*.245,0,4.301),(.08,1.31,.025),p['darksteel'],bodyroot)
    for yy in (-1.02,1.02):
        _box(name+'_RoofEdgeDrain',(-.8,yy,3.94),(13.8,.065,.065),p['steel'],bodyroot)
    if variant%2:
        # Articulated pantograph rises to a credible overhead pickup silhouette.
        _box(name+'_PantographBase',(-.9,0,4.21),(1.35,.92,.18),p['darksteel'],bodyroot)
        for yy in (-.3,.3):
            _tube(name+'_PantographArm',(-1.4,yy,4.34),(-.45,yy,5.18),.045,p['darksteel'],bodyroot)
            _tube(name+'_PantographArm',(-.45,yy,5.18),(-1.20,yy,5.74),.045,p['darksteel'],bodyroot)
        _tube(name+'_PantographCollector',(-1.2,-.95,5.74),(-1.2,.95,5.74),.066,p['darksteel'],bodyroot)
    for end in (-1,1):
        if role!='middle' and end==1:continue
        _box(name+'_Gangway',(end*8.87,0,2.4),(.18,1.44,2.27),p['black'],bodyroot)
        for xx in (end*8.95,end*9.09,end*9.23):
            _box(name+'_GangwayBellows',(xx,0,2.4),(.065,1.50,2.32),p['darksteel'],bodyroot)
        _box(name+'_Coupler',(end*9.27,0,.94),(.48,.32,.28),p['darksteel'],bodyroot)
    if role!='middle':
        # Match the upper shell's actual segmented curvature, keeping glazing outside it.
        def cab_surface(xx, base_y):
            if xx<=7.05:
                t=(xx-6.15)/.9;ys=1-.06*t;zs=1-.06*t;oz=.06*t
            else:
                t=(xx-7.05);ys=.94-.22*t;zs=.94-.21*t;oz=.06+.24*t
            ay=abs(base_y)
            if ay<=.6:base_z=4.07-.05*(ay/.6)
            else:base_z=4.02-.17*((ay-.6)/.53)
            return (xx,base_y*ys,base_z*zs+oz+.027)
        for side in (-1,1):
            xs=(6.80,7.05,7.45,7.88);ys=(.07,.60,1.10)
            pts=[cab_surface(xx,side*yy) for xx in xs for yy in ys]
            faces=[(i*3+j,i*3+j+1,(i+1)*3+j+1,(i+1)*3+j) for i in range(3) for j in range(2)]
            _mesh(name+'_DriverWindscreen',pts,faces,p['glass'],bodyroot,smooth=True)
            edges=[cab_surface(xx,side*1.10) for xx in xs]+[cab_surface(7.88,side*yy) for yy in (.6,.07)]+[cab_surface(xx,side*.07) for xx in reversed(xs[:-1])]+[cab_surface(6.8,side*yy) for yy in (.6,1.1)]
            _line(name+'_WindscreenRubber',edges,.025,p['black'],bodyroot)
            _tube(name+'_WindshieldWiper',Vector(cab_surface(7.72,side*.78))+Vector((0,0,.027)),Vector(cab_surface(6.96,side*.40))+Vector((0,0,.03)),.019,p['black'],bodyroot)
            _mesh(name+'_CabSideWindow',[(5.47,side*1.51,2.57),(6.23,side*1.48,2.57),(6.74,side*1.35,3.11),(5.47,side*1.51,3.11)],[(0,1,2,3)],p['glass'],bodyroot)
            _tube(name+'_Headlamp',(8.47,side*.64,1.97),(8.55,side*.64,1.97),.13,p['light'] if role=='front' else p['red'],bodyroot,16)
            _line(name+'_NoseBlueSweep',[(5.9,side*1.516,1.75),(7.08,side*1.42,1.66),(8.07,side*1.11,1.57),(8.8,side*.48,1.48)],.145,p['blue'],bodyroot,10)
        _box(name+'_FrontCouplerCover',(8.77,0,1.38),(.38,.73,.28),p['blue'],bodyroot)
    root['asset_type']='train_car';root['dynamic_owner']=name;root['role']=role
    root['gauge_m']=1.435;root['coupling_pitch_m']=19.0;root['rail_contact_z']=z
    return root,{'role':role,'length':17.9,'coupling_pitch':19.0,'width':3.15,'rail_gauge':1.435,'components':len(bodyroot.children),'rail_datum':z}
