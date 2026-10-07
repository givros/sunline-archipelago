"""Editable tropical architecture; Blender Z-up and full dimensions in metres.

Import safely after bpy initialization. house/church/pavilion/dock_props return a
record containing parent, collection, footprint, entrance, floor_z and obstacles.
Front faces local -Y. Stilt origins are the water datum; their deck is z + 3.2.
All emitted visible components are meshes, grouped by semantic assembly/material.
Closed house interiors are intentionally not enterable. No scene changes on import.
"""
import math
import random
import bpy
from mathutils import Vector

TAU = math.tau
_MATS = {}


def material(name, color, roughness=.72, metallic=0.0):
    key = 'ARC_' + name
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


def palette(variant):
    walls = [(.86,.81,.66),(.9,.88,.76),(.79,.83,.79),(.84,.72,.55),(.79,.82,.73)]
    roofs = [(.55,.20,.09),(.66,.27,.13),(.46,.20,.12),(.49,.32,.21),(.43,.46,.42)]
    return {
        'wall': material('Limewash_' + str(variant%5), walls[variant%5]),
        'woodwall': material('CedarCladding',(.43,.29,.16)),
        'roof': material('RoofClay_'+str(variant%5),roofs[variant%5]),
        'rooflight':material('RoofClayLight_'+str(variant%5),tuple(min(1,c*1.16) for c in roofs[variant%5])),
        'roofdark':material('RoofClayDark_'+str(variant%5),tuple(c*.84 for c in roofs[variant%5])),
        'trim':material('ChalkStone',(.93,.9,.76)),
        'stone':material('CoralStone',(.59,.58,.49)),
        'mortar':material('RecessedMortar',(.43,.44,.38)),
        'wood':material('WeatheredTeak',(.40,.25,.125)),
        'woodlight':material('SawnTeak',(.53,.36,.2)),
        'wooddark':material('TeakEndgrain',(.22,.14,.075)),
        'shutter':material('PaintedShutter_'+str(variant%3),[(.12,.31,.28),(.26,.37,.41),(.43,.25,.16)][variant%3]),
        'glass':material('DeepSeaGlass',(.065,.19,.205),.22,.15),
        'metal':material('WroughtIron',(.09,.105,.085),.42,.65),
        'brass':material('AgedBrass',(.48,.34,.10),.42,.68),
        'fabric':material('LinenCanvas',(.85,.81,.63)),
        'redfabric':material('CoralCanvas',(.67,.22,.12)),
        'terracotta':material('TerracottaPot',(.60,.28,.14)),
        'leaf':material('CourtyardFoliage',(.18,.36,.12)),
    }


class Assembly:
    """One object per editable semantic layer; no expensive mesh operators."""
    def __init__(self,name,x,y,z,angle=0,scale=1):
        self.name=name
        self.buckets={}
        self.origin=(x,y,z)
        self.angle=angle
        self.scale=scale
        self.collection=bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(self.collection)
        self.parent=bpy.data.objects.new(name,None)
        self.parent.empty_display_type='PLAIN_AXES'
        self.parent.location=(x,y,z)
        self.parent.rotation_euler.z=angle
        self.parent.scale=(scale,)*3
        self.collection.objects.link(self.parent)
        self.parent['asset_family']='tropical_architecture'

    def mesh(self,role,mat,verts,faces):
        key=(role,mat.name)
        if key not in self.buckets:self.buckets[key]=[[],[],mat]
        v,f,_=self.buckets[key]
        off=len(v)
        v.extend(verts)
        f.extend([tuple(off+i for i in face) for face in faces])

    def box(self,role,mat,c,d,rot=0):
        x,y,z=c; w,l,h=[q/2 for q in d]
        cs,sn=math.cos(rot),math.sin(rot)
        vs=[]
        for X,Y,Z in [(-w,-l,-h),(w,-l,-h),(w,l,-h),(-w,l,-h),(-w,-l,h),(w,-l,h),(w,l,h),(-w,l,h)]:
            vs.append((x+X*cs-Y*sn,y+X*sn+Y*cs,z+Z))
        self.mesh(role,mat,vs,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)])

    def beam(self,role,mat,a,b,width,depth=None,sides=8):
        a,b=Vector(a),Vector(b)
        axis=b-a
        if axis.length<1e-6:return
        direction=axis.normalized()
        tangent=direction.cross(Vector((0,0,1)))
        if tangent.length<.01:tangent=Vector((1,0,0))
        else:tangent.normalize()
        normal=direction.cross(tangent).normalized()
        verts=[]
        for p in [a,b]:
            for k in range(sides):
                t=TAU*k/sides
                verts.append(tuple(p+tangent*math.cos(t)*width/2+normal*math.sin(t)*(depth or width)/2))
        faces=[tuple(reversed(range(sides))),tuple(range(sides,sides*2))]
        for k in range(sides):faces.append((k,(k+1)%sides,(k+1)%sides+sides,k+sides))
        self.mesh(role,mat,verts,faces)

    def cylinder(self,role,mat,c,r,h,sides=12,r_top=None,phase=0):
        x,y,z=c;r2=r if r_top is None else r_top
        if r2==0:
            verts=[(x+r*math.cos(TAU*i/sides+phase),y+r*math.sin(TAU*i/sides+phase),z-h/2) for i in range(sides)]+[(x,y,z+h/2)]
            faces=[tuple(reversed(range(sides)))]+[(i,(i+1)%sides,sides) for i in range(sides)]
            self.mesh(role,mat,verts,faces);return
        verts=[(x+rad*math.cos(TAU*i/sides+phase),y+rad*math.sin(TAU*i/sides+phase),z+zz) for zz,rad in [(-h/2,r),(h/2,r2)] for i in range(sides)]
        faces=[tuple(reversed(range(sides))),tuple(range(sides,sides*2))]
        faces.extend([(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)])
        self.mesh(role,mat,verts,faces)

    def world(self,p):
        x,y,z=p;cs,sn=math.cos(self.angle),math.sin(self.angle);s=self.scale
        return [self.origin[0]+s*(x*cs-y*sn),self.origin[1]+s*(x*sn+y*cs),self.origin[2]+s*z]

    def finish(self,w,d,floor,entrance,obstacle=None):
        objects=[]
        for (role,_),(verts,faces,mat) in self.buckets.items():
            mesh=bpy.data.meshes.new(self.name+'__'+role)
            mesh.from_pydata(verts,[],faces)
            mesh.materials.append(mat)
            mesh.update()
            obj=bpy.data.objects.new(self.name+'__'+role,mesh)
            self.collection.objects.link(obj)
            obj.parent=self.parent
            obj['component_role']=role
            objects.append(obj)
        footprint=[self.world(p)[:2] for p in [(-w/2,-d/2,0),(w/2,-d/2,0),(w/2,d/2,0),(-w/2,d/2,0)]]
        obs=[]
        if obstacle:
            x0,y0,z0,x1,y1,z1=obstacle
            points=[self.world((X,Y,Z)) for X in [x0,x1] for Y in [y0,y1] for Z in [z0,z1]]
            obs=[{'id':self.name,'min':[min(p[i] for p in points) for i in range(3)],'max':[max(p[i] for p in points) for i in range(3)],'polygon':[self.world(q)[:2] for q in [(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0)]],'enterable':False}]
        self.parent['floor_z']=self.origin[2]+floor*self.scale
        self.parent['component_count']=len(objects)
        return {'parent':self.parent,'collection':self.collection,'objects':objects,'footprint':footprint,'entrance':self.world(entrance),'floor_z':self.origin[2]+floor*self.scale,'obstacles':obs}


def _wall(a,p,origin,tangent,normal,length,zbase,height,bays,door=False,wood=False):
    """Pier/spandrel construction leaves genuine, recessed apertures."""
    ox,oy=origin;tx,ty=tangent;nx,ny=normal
    angle=math.atan2(ty,tx)
    wallmat=p['woodwall'] if wood else p['wall']
    def panel(role,mat,u,z,w,h,depth=.32,out=0):
        a.box(role,mat,(ox+u*tx+out*nx,oy+u*ty+out*ny,z),(w,depth,h),angle)
    bw=length/bays
    for i in range(bays):
        mid=-length/2+bw*(i+.5)
        isdoor=door and i==bays//2
        aperture=min(1.65,bw*.48) if isdoor else min(1.65,bw*.44)
        low=zbase if isdoor else zbase+.93
        high=zbase+2.6 if isdoor else zbase+2.55
        if wood: high=min(high,zbase+height-.28)
        side=(bw-aperture)/2
        for sign in [-1,1]:
            panel('wall_piers',wallmat,mid+sign*(aperture/2+side/2),zbase+height/2,side,height)
        if low>zbase:panel('wall_spandrels',wallmat,mid,(zbase+low)/2,aperture,low-zbase)
        panel('wall_lintels',wallmat,mid,(high+zbase+height)/2,aperture,zbase+height-high)
        # Deep shaded aperture, with jambs, sill and lintel deliberately layered.
        panel('door_leaf' if isdoor else 'window_glazing',p['wooddark'] if isdoor else p['glass'],mid,(low+high)/2,aperture,high-low,.06,-.08)
        for sign in [-1,1]:panel('opening_jambs',p['woodlight'] if wood else p['trim'],mid+sign*(aperture/2+.035),(low+high)/2,.12,high-low+.2,.42,.075)
        panel('opening_lintels',p['woodlight'] if wood else p['trim'],mid,high+.06,aperture+.22,.16,.45,.085)
        panel('opening_sills',p['woodlight'] if wood else p['trim'],mid,low-.045,aperture+.3,.13,.52,.12)
        if isdoor:
            for z in [low+.58,low+1.54,low+2.21]:panel('door_panels',p['wood'],mid,z,aperture-.2,.49,.055,-.025)
            panel('door_stiles',p['woodlight'],mid,(low+high)/2,.07,high-low,.05,.025)
            panel('door_hardware',p['brass'],mid+aperture*.31,low+1.15,.075,.23,.10,.09)
        else:
            panel('window_mullions',p['woodlight'],mid,(low+high)/2,.085,high-low,.075,.02)
            panel('window_transoms',p['woodlight'],mid,low+(high-low)*.58,aperture,.08,.085,.025)
            for sign in [-1,1]:
                shut=mid+sign*(aperture*.75+.11)
                panel('shutter_frames',p['shutter'],shut,(low+high)/2,aperture*.43,high-low+.1,.075,.25)
                for j in range(7):panel('shutter_louvers',p['shutter'],shut,low+.12+j*(high-low-.14)/7,aperture*.38,.065,.11,.31)
                for z in [low+.2,high-.2]:panel('shutter_hinges',p['metal'],mid+sign*(aperture*.56),z,.18,.06,.09,.33)
        if wood:
            for k in range(int(height/.24)):
                zz=zbase+.1+k*.24
                if low-.04 < zz < high+.04:
                    for sign in [-1,1]:panel('cladding_courses',p['woodlight'],mid+sign*(aperture/2+side/2),zz,side,.036,.05,.18)
                else:panel('cladding_courses',p['woodlight'],mid,zz,bw,.036,.05,.18)


def _hiproof(a,p,w,d,z,h,variant=0):
    """Solid hip roof with curved interlocking tile rows and ridge caps."""
    rw,rd=w/2,d/2
    ridge=abs(rw-rd)
    tops=[(-ridge,0,z+h),(ridge,0,z+h)] if rw>=rd else [(0,-ridge,z+h),(0,ridge,z+h)]
    v=[(-rw,-rd,z),(rw,-rd,z),(rw,rd,z),(-rw,rd,z),*tops,(-rw,-rd,z-.17),(rw,-rd,z-.17),(rw,rd,z-.17),(-rw,rd,z-.17)]
    upper=[(0,1,5,4),(1,2,5),(2,3,4,5),(3,0,4)] if rw>=rd else [(0,1,4),(1,2,5,4),(2,3,5),(3,0,4,5)]
    a.mesh('roof_structure',p['roofdark'],v,upper+[(6,9,8,7),(0,6,7,1),(1,7,8,2),(2,8,9,3),(3,9,6,0)])
    def height(x,y):return z+h*max(0,min((rw-abs(x))/min(rw,rd),(rd-abs(y))/min(rw,rd)))
    rng=random.Random(591+variant)
    # Each tile is a low curved extrusion, ensuring roof detail is real mesh.
    nx=max(1,round(w/.48));ny=max(1,round(d/.66));dx=w/nx;dy=d/ny
    for iy in range(ny):
        for ix in range(nx):
            cx=-rw+(ix+.5)*dx;cy=-rd+(iy+.5)*dy
            # Texture-scale tile curvature follows hip face; tile joints remain readable.
            verts=[]
            for yy in [-dy*.49,dy*.49]:
                for k in range(5):
                    xx=(k/4-.5)*dx*.98
                    verts.append((cx+xx,cy+yy,height(cx+xx,cy+yy)+.045+.035*math.sin(math.pi*k/4)))
            faces=[(k,k+1,k+6,k+5) for k in range(4)]
            mat=p['rooflight'] if rng.random()<.16 else (p['roofdark'] if rng.random()<.11 else p['roof'])
            a.mesh('individual_clay_tiles',mat,verts,faces)
    for s in [-1,1]:
        top=(s*ridge,0,z+h+.10) if rw>=rd else (0,s*ridge,z+h+.10)
        corners=[(s*rw,-rd,z+.06),(s*rw,rd,z+.06)] if rw>=rd else [(-rw,s*rd,z+.06),(rw,s*rd,z+.06)]
        for corner in corners:a.beam('roof_ridge_caps',p['rooflight'],top,corner,.16,sides=8)
    a.beam('roof_ridge_caps',p['rooflight'],(tops[0][0],tops[0][1],z+h+.10),(tops[1][0],tops[1][1],z+h+.10),.20,sides=10)
    for yy in [-rd,rd]:a.box('eave_fascia',p['wooddark'],(0,yy,z-.05),(w,.14,.25))
    for xx in [-rw,rw]:a.box('eave_fascia',p['wooddark'],(xx,0,z-.05),(.14,d,.25))


def _railing(a,p,x1,y1,x2,y2,z,spacing=1.25,wood=False):
    length=math.hypot(x2-x1,y2-y1);n=max(1,math.ceil(length/spacing));m=p['woodlight'] if wood else p['metal']
    for i in range(n+1):
        t=i/n;x=x1+(x2-x1)*t;y=y1+(y2-y1)*t
        a.box('balustrade_posts',m,(x,y,z+.53),(.105,.105,1.06))
    for zz in [.45,1.04]:a.beam('balustrade_rails',m,(x1,y1,z+zz),(x2,y2,z+zz),.095,sides=4)


def _stairs(a,p,x,y,z,width,count=3,rise=.18,run=.32):
    for i in range(count):
        hh=rise*(count-i)
        a.box('entrance_steps',p['stone'],(x,y-i*run,z+hh/2),(width,run+.04,hh))


def _planter(a,p,x,y,z,r=.4):
    a.cylinder('terracotta_planters',p['terracotta'],(x,y,z+.37),r*.72,.7,12,r)
    a.cylinder('planter_rims',p['terracotta'],(x,y,z+.72),r*1.06,.11,12)
    for i in range(9):
        ang=TAU*i/9; tip=(x+math.cos(ang)*r*1.4,y+math.sin(ang)*r*1.4,z+1+.2*(i%3))
        base=(x,y,z+.76);mid=((base[0]+tip[0])*.5,(base[1]+tip[1])*.5,z+1.25)
        side=(-math.sin(ang)*.11,math.cos(ang)*.11,0)
        a.mesh('planter_leaves',p['leaf'],[base,(mid[0]+side[0],mid[1]+side[1],mid[2]),tip,(mid[0]-side[0],mid[1]-side[1],mid[2])],[(0,1,2,3)])


def house(name,x,y,z,angle=0,kind='villa',variant=0,scale=1):
    """Villa/cottage/shop or stilt bungalow; deck front connection at local -Y."""
    a=Assembly(name,x,y,z,angle,scale);p=palette(variant)
    stilt=kind in ('stilt','bungalow','overwater')
    w=[11.8,13.4,10.6,12.2,14.1][variant%5] if not stilt else [8.7,9.5,8.2,10.0][variant%4]
    d=[9.0,9.7,8.5,10.4,9.5][variant%5] if not stilt else [7.0,7.7,7.5,8.1][variant%4]
    floors=1 if stilt or kind=='cottage' or variant%5==2 else 2
    if kind in ('shop','service'):
        w=7.6+(variant%3)*.65;d=10.2+(variant%2)*1.2;floors=2
    floor=3.48 if stilt else .55
    story=3.25 if stilt else 3.45
    roofbase=floor+floors*story
    if stilt:
        deckw=max(13,w+3);deckd=max(12,d+4)
        for X in [-deckw/2+.4,0,deckw/2-.4]:
            for Y in [-deckd/2+.4,0,deckd/2-.4]:
                a.cylinder('structural_pilings',p['wooddark'],(X,Y,.55),.20,5.2,10)
                a.cylinder('piling_caps',p['woodlight'],(X,Y,2.99),.28,.16,10)
        for X in [-deckw/2+.4,deckw/2-.4]:
            a.box('deck_bearers',p['wooddark'],(X,0,2.87),(.30,deckd,.44))
            for Y in [-deckd/2+.4,deckd/2-.4]:
                a.beam('piling_cross_braces',p['wood'],(X,Y,1.25),(X,0,2.9),.20,sides=4)
        for j in range(round(deckd/.32)):
            yy=-deckd/2+(j+.5)*deckd/round(deckd/.32)
            a.box('individual_deck_planks',p['woodlight'] if j%4==0 else p['wood'],(0,yy,3.12),(deckw,deckd/round(deckd/.32)-.022,.17))
        # Front central 3m remains open for a district boardwalk connection.
        _railing(a,p,-deckw/2,-deckd/2,-1.6,-deckd/2,3.22,wood=True)
        _railing(a,p,1.6,-deckd/2,deckw/2,-deckd/2,3.22,wood=True)
        for X in [-deckw/2,deckw/2]:_railing(a,p,X,-deckd/2,X,deckd/2,3.22,wood=True)
        _railing(a,p,-deckw/2,deckd/2,deckw/2,deckd/2,3.22,wood=True)
        _stairs(a,p,0,-d/2-.28,3.20,2.3,count=2,rise=.14,run=.28)
        a.box('raised_floor_frame',p['wooddark'],(0,0,floor-.14),(w+.12,d+.12,.25))
    else:
        a.box('foundation_masonry',p['stone'],(0,0,-.10),(w+.28,d+.28,1.15))
        # Bonded stone courses make the base read at pedestrian distance.
        for zz in [-.4,0,.38]:
            for yy in [-d/2-.15,d/2+.15]:a.box('foundation_courses',p['mortar'],(0,yy,zz),(w+.28,.028,.035))
        a.box('foundation_coping',p['trim'],(0,0,.49),(w+.48,d+.48,.18))
        _stairs(a,p,0,-d/2-.35,0,2.8,count=3,rise=.183,run=.34)
    for f in range(floors):
        zb=floor+f*story
        _wall(a,p,(0,-d/2),(1,0),(0,-1),w,zb,story,3,door=f==0,wood=stilt)
        _wall(a,p,(0,d/2),(-1,0),(0,1),w,zb,story,3,wood=stilt)
        _wall(a,p,(-w/2,0),(0,-1),(-1,0),d,zb,story,2,wood=stilt)
        _wall(a,p,(w/2,0),(0,1),(1,0),d,zb,story,2,wood=stilt)
        if f:
            a.box('floor_stringcourse',p['trim'],(0,0,zb-.03),(w+.30,d+.30,.18))
    for X in [-w/2,w/2]:
        for Y in [-d/2,d/2]:
            a.box('corner_posts' if stilt else 'corner_pilasters',p['wooddark'] if stilt else p['trim'],(X,Y,(floor+roofbase)/2),(.28,.28,roofbase-floor))
    a.box('roof_bearing_cornice',p['woodlight'] if stilt else p['trim'],(0,0,roofbase-.03),(w+.32,d+.32,.24))
    _hiproof(a,p,w+1.15,d+1.2,roofbase+.1,2.25 if stilt else 2.6,variant)
    # Veranda on one-storey and overwater homes; column anchors meet canopy.
    if stilt or floors==1:
        front=-d/2-1.3
        porchfloor=3.205 if stilt else floor
        if not stilt:
            a.box('veranda_foundation',p['stone'],(0,-d/2-1.00,floor/2),(w*.92,2.15,floor))
            a.box('veranda_floor',p['trim'],(0,-d/2-1.00,floor-.025),(w*.94,2.20,.12))
        column_top=floor+2.7
        for X in [-w*.36,w*.36]:a.box('veranda_columns',p['woodlight'] if stilt else p['trim'],(X,front,(porchfloor+column_top)/2),(.18,.18,column_top-porchfloor))
        canopy_z=floor+2.8
        a.mesh('veranda_canopy',p['roof'],[(-w*.45,-d/2+.08,canopy_z+.40),(w*.45,-d/2+.08,canopy_z+.4),(w*.45,front-.4,canopy_z),(-w*.45,front-.4,canopy_z)],[(0,1,2,3)])
        a.box('veranda_front_beam',p['wooddark'],(0,front,canopy_z-.06),(w*.9,.20,.22))
        for X in [-w*.3,w*.3]:
            a.box('veranda_seats',p['woodlight'],(X,front+.25,porchfloor+.42),(1.25,.48,.13))
            for dx in [-.46,.46]:a.box('veranda_seat_legs',p['wooddark'],(X+dx,front+.25,porchfloor+.2),(.1,.33,.4))
    elif variant%2==0:
        by=-d/2-1.05;bz=floor+story
        a.box('balcony_slab',p['stone'],(0,by,bz-.12),(w*.62,2.1,.23))
        _railing(a,p,-w*.31,by-1.03,w*.31,by-1.03,bz)
        for X in [-w*.31,w*.31]:
            _railing(a,p,X,-d/2,X,by-1.03,bz)
            a.beam('balcony_brackets',p['wooddark'],(X,-d/2-.02,bz-1),(X,by-1,bz-.15),.19,sides=4)
    if not stilt:
        # Chimney seats within the actual hipped roof surface.
        chx=w*.28;chy=d*.18
        roof_h=2.6*min(((w+1.15)/2-abs(chx))/((d+1.2)/2),((d+1.2)/2-abs(chy))/((d+1.2)/2))
        bottom=roofbase+roof_h-.3
        a.box('chimney_shaft',p['wall'],(chx,chy,bottom+1.0),(.72,.8,2.0))
        a.box('chimney_cap',p['trim'],(chx,chy,bottom+2.05),(1,.99,.2))
        for xx in [chx-.25,chx+.25]:a.box('chimney_vent',p['wooddark'],(xx,chy-.405,bottom+1.7),(.18,.035,.25))
        # Downpipes are independently owned and terminate beside foundation.
        for X in [-w/2-.2,w/2+.2]:a.beam('rainwater_downpipes',p['metal'],(X,d/2+.21,.2),(X,d/2+.21,roofbase),.09,sides=8)
    if kind in ('shop','service'):
        # A narrow shopfront has an occupied upper storey and a supported striped
        # canvas sunshade. It shares the same real openings and complete roof.
        canopy_y=-d/2-1.35
        for X in [-w*.42,w*.42]:
            a.beam('shop_awning_brackets',p['metal'],(X,-d/2-.15,floor+2.4),(X,canopy_y,floor+2.8),.075,sides=6)
        stripes=8
        for j in range(stripes):
            x0=-w*.47+j*w*.94/stripes;x1=x0+w*.94/stripes
            a.mesh('striped_shop_awning',p['fabric'] if j%2 else p['redfabric'],[(x0,-d/2-.04,floor+3.0),(x1,-d/2-.04,floor+3.0),(x1,canopy_y,floor+2.76),(x0,canopy_y,floor+2.76)],[(0,1,2,3)])
            a.box('awning_valance',p['fabric'] if j%2 else p['redfabric'],((x0+x1)/2,canopy_y,floor+2.62),(x1-x0,.035,.27))
        a.box('shop_signboard',p['wooddark'],(0,-d/2-.23,floor+3.21),(w*.73,.15,.32))
    planter_floor=3.19 if stilt else (floor if floors==1 else 0)
    _planter(a,p,-w*.41,-d/2-.6,planter_floor,.35)
    _planter(a,p,w*.41,-d/2-.6,planter_floor,.35)
    a.parent['building_kind']=kind
    a.parent['storeys']=floors
    a.parent['walls_have_real_openings']=True
    a.parent['enterable']=False
    return a.finish(deckw if stilt else w+1.3,deckd if stilt else d+4.3,floor,(0,-(deckd/2 if stilt else d/2+1.1),3.2 if stilt else 0),(-w/2,-d/2,floor,w/2,d/2,roofbase+2.6))


def church(name,x,y,z,angle=0,scale=1):
    """Coastal parish church with tiled nave, open belfry, clock, spire and steps."""
    a=Assembly(name,x,y,z,angle,scale);p=palette(1)
    w,d=12,22;floor=.65;walltop=9.0
    a.box('coral_stone_foundation',p['stone'],(0,0,.12),(w+.5,d+.5,1.05))
    for O,T,N,L,B in [((0,-d/2),(1,0),(0,-1),w,3),((0,d/2),(-1,0),(0,1),w,3),((-w/2,0),(0,-1),(-1,0),d,5),((w/2,0),(0,1),(1,0),d,5)]:
        _wall(a,p,O,T,N,L,floor,4.3,B,door=O[1]==-d/2)
        _wall(a,p,O,T,N,L,floor+4.3,4.05,B)
    _hiproof(a,p,w+1,d+1,walltop,3.6,1)
    # Local tower at front right, with true open belfry spans between four piers.
    tx,ty=3.8,-8.5;tw=4.4
    a.box('tower_body',p['wall'],(tx,ty,8.0),(tw,tw,16))
    for zz in [1.1,8.0,12.4,16.2,20.4]:a.box('tower_cornices',p['trim'],(tx,ty,zz),(tw+.45,tw+.45,.32))
    for X in [-1,1]:
        for Y in [-1,1]:a.box('belfry_corner_piers',p['trim'],(tx+X*(tw/2-.26),ty+Y*(tw/2-.26),18.4),(.58,.58,4.05))
    for Y in [-1,1]:a.box('belfry_open_span_lintels',p['trim'],(tx,ty+Y*(tw/2-.26),20.1),(tw,.54,.55))
    for X in [-1,1]:a.box('belfry_open_span_lintels',p['trim'],(tx+X*(tw/2-.26),ty,20.1),(.54,tw,.55))
    a.cylinder('hanging_bell',p['brass'],(tx,ty,18.25),.67,1.25,16,.36)
    a.cylinder('bell_lip',p['brass'],(tx,ty,17.63),.78,.18,16)
    a.beam('bell_hanger',p['metal'],(tx,ty,18.9),(tx,ty,20.0),.14,sides=8)
    # Clock sits on the front wall; individual radial markers and hands.
    cy=ty-tw/2-.05;cz=13.92
    a.beam('clock_face',p['trim'],(tx,cy,cz),(tx,cy-.10,cz),1.64,sides=24)
    for i in range(12):
        th=TAU*i/12
        a.beam('clock_hour_marks',p['metal'],(tx+math.sin(th)*.62,cy-.13,cz+math.cos(th)*.62),(tx+math.sin(th)*.71,cy-.13,cz+math.cos(th)*.71),.052,sides=4)
    a.beam('clock_hands',p['metal'],(tx,cy-.17,cz),(tx-.43,cy-.17,cz+.22),.06,sides=4)
    a.beam('clock_hands',p['metal'],(tx,cy-.17,cz),(tx+.1,cy-.17,cz+.53),.055,sides=4)
    a.cylinder('tower_hipped_spire',p['roof'],(tx,ty,22.05),3.65,3.3,4,0,math.pi/4)
    a.beam('tower_cross',p['metal'],(tx,ty,23.55),(tx,ty,25.0),.14,sides=4)
    a.beam('tower_cross',p['metal'],(tx-.48,ty,24.5),(tx+.48,ty,24.5),.14,sides=4)
    _stairs(a,p,-2,-d/2-.4,0,5,count=4,rise=.1625,run=.37)
    for X in [-w/2,w/2]:
        for Y in [-d*.3,d*.15,d*.4]:a.box('side_buttresses',p['trim'],(X,Y,4.25),(.75,.8,8.3))
    a.parent['landmark_kind']='coastal_church'
    a.parent['spire_square_eaves_v1']=True
    return a.finish(w+1.5,d+3,.65,(-2,-d/2-1.5,0),(-w/2,-d/2,0,w/2,d/2,25))


def pavilion(name,x,y,z,radius=5):
    """Lagoon meeting pavilion: circular timber deck, piles and octagonal roof."""
    a=Assembly(name,x,y,z);p=palette(3);floor=3.2
    a.cylinder('radial_deck_frame',p['wooddark'],(0,0,3.0),radius,.4,32)
    for k in range(math.ceil(radius*2/.32)):
        yy=-radius+(k+.5)*(2*radius/math.ceil(radius*2/.32));width=2*math.sqrt(max(0,radius*radius-yy*yy))
        a.box('individual_deck_planks',p['woodlight'] if k%3 else p['wood'],(0,yy,3.18),(width,.3,.14))
    for k in range(12):
        t=TAU*k/12;X=math.cos(t)*radius*.86;Y=math.sin(t)*radius*.86
        a.cylinder('pavilion_pilings',p['wooddark'],(X,Y,.6),.20,5.0,10)
    rr=radius*.57
    for k in range(8):
        t=TAU*k/8;X=math.cos(t)*rr;Y=math.sin(t)*rr
        a.box('pavilion_columns',p['woodlight'],(X,Y,floor+1.72),(.23,.23,3.44))
        a.beam('pavilion_rafters',p['wooddark'],(X,Y,floor+3.36),(0,0,floor+5.1),.16,sides=4)
    a.cylinder('pavilion_roof',p['roof'],(0,0,floor+4.15),rr+1.0,1.7,8,.15)
    for k in range(8):
        t=TAU*k/8;a.beam('pavilion_roof_ribs',p['rooflight'],(math.cos(t)*(rr+1),math.sin(t)*(rr+1),floor+3.3),(0,0,floor+5),.13,sides=8)
    a.cylinder('pavilion_finial',p['woodlight'],(0,0,floor+5.3),.11,.65,8)
    a.cylinder('round_table',p['woodlight'],(0,0,floor+.9),1.1,.17,16)
    a.cylinder('table_pedestal',p['wooddark'],(0,0,floor+.43),.2,.86,8)
    return a.finish(radius*2,radius*2,floor,(0,-radius,floor))


def dock_props(name,x,y,z,angle=0):
    """Compact dockside mooring bollards, tied crates, barrel, bench and lamp."""
    a=Assembly(name,x,y,z,angle);p=palette(0)
    for X in [-2.0,2.0]:
        a.cylinder('bollard_base',p['metal'],(X,0,.06),.3,.12,12)
        a.cylinder('mooring_bollard',p['metal'],(X,0,.35),.12,.58,10)
        a.beam('bollard_crossbar',p['metal'],(X-.28,0,.58),(X+.28,0,.58),.13,sides=8)
    for i in range(2):
        X=-1.5+i*.92;Y=1.6
        a.box('cargo_crate',p['woodlight'],(X,Y,.47),(.82,.78,.94))
        for zz in [.12,.8]:
            for yy in [Y-.405,Y+.405]:a.box('crate_straps',p['wooddark'],(X,yy,zz),(.87,.055,.095))
        for xx in [X-.31,X+.31]:a.box('crate_slats',p['wood'],(xx,Y-.4,.46),(.075,.065,.86))
        a.beam('crate_diagonal_brace',p['wood'],(X-.36,Y-.45,.15),(X+.36,Y-.45,.8),.09,sides=4)
    a.cylinder('water_barrel',p['wood'],(1.6,1.6,.58),.37,1.15,14,.33)
    for zz in [.12,.55,1.04]:a.cylinder('barrel_hoops',p['metal'],(1.6,1.6,zz),.38,.055,14)
    for zz in [.48,.83]:a.box('dock_bench',p['woodlight'],(0,3,zz),(2.8,.48,.12))
    for X in [-1,1]:
        a.box('bench_supports',p['wooddark'],(X,3,.4),(.13,.3,.8))
        a.box('bench_back_supports',p['wooddark'],(X,3.2,.63),(.1,.1,1.25))
    a.beam('harbor_lamp_post',p['metal'],(2.3,2.8,0),(2.3,2.8,3.2),.11,sides=8)
    a.box('lantern_glass',p['fabric'],(2.3,2.8,3.27),(.36,.36,.56))
    a.cylinder('lantern_roof',p['metal'],(2.3,2.8,3.68),.36,.24,4,0)
    a.box('lantern_base',p['metal'],(2.3,2.8,2.97),(.44,.44,.09))
    for X in [-.18,.18]:
        for Y in [-.18,.18]:a.box('lantern_frame',p['metal'],(2.3+X,2.8+Y,3.27),(.035,.035,.62))
    return a.finish(5.2,4,0,(0,-1,0))
