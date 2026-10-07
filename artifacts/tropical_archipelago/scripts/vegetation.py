"""Linked, editable botanical vegetation and limestone outcrops.

Tree soil datum is local Z=0, with a buried trunk continuation. Final placement
casts against the visible island triangle mesh after terrain.at estimates height.
Only the first 2.25 metres of trunk receives a solid collider, never the canopy.
"""
import bpy
import math
import random
import json
import sys
from pathlib import Path
if __name__=='__main__':sys.path.insert(0,str(Path(__file__).resolve().parent))
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from core import material, collection, instance
from layout import ISLANDS, RAILS, VILLAS, PLAZAS, DOCKS, STILT_DISTRICTS, xy
from terrain import at, island_distance

_PROTOTYPES=None
_TAU=math.tau


def _palette():
    p={
        'bark':material('VEG Grey tropical bark',(.235,.205,.139),.96),
        'barklight':material('VEG Coconut ring scars',(.47,.41,.29),.9),
        'palmstem':material('VEG Coconut stem',(.40,.34,.23),.92),
        'coconut':material('VEG Young coconuts',(.27,.34,.09),.9),
        'rock':material('VEG Silver limestone',(.42,.45,.40),.92),
        'rocklight':material('VEG Limestone fractured edges',(.57,.56,.47),.94),
        'rockdark':material('VEG Limestone shaded seams',(.26,.29,.26),.96),
    }
    p['leaves']=[material('VEG Rainforest leaf '+str(i),c,.84) for i,c in enumerate(((.032,.115,.015),(.054,.178,.022),(.105,.245,.032),(.185,.315,.05),(.073,.166,.019)))]
    p['palms']=[material('VEG Palm leaf '+str(i),c,.78) for i,c in enumerate(((.12,.255,.031),(.19,.325,.047),(.26,.38,.067),(.078,.205,.023)))]
    p['ferns']=[material('VEG Fern leaf '+str(i),c,.85) for i,c in enumerate(((.16,.35,.065),(.24,.42,.085),(.10,.26,.04)))]
    for m in p['leaves']+p['palms']+p['ferns']:
        m['semantic_role']='foliage';m['double_sided']=True
    return p


class Builder:
    def __init__(self,name):self.name=name;self.buckets={}

    def mesh(self,role,mat,verts,faces,smooth=False):
        if role not in self.buckets:self.buckets[role]={'v':[],'f':[],'materials':[],'ids':[],'smooth':[]}
        b=self.buckets[role]
        if mat not in b['materials']:b['materials'].append(mat)
        mi=b['materials'].index(mat);off=len(b['v']);b['v'].extend([tuple(v) for v in verts]);b['f'].extend([tuple(off+i for i in f) for f in faces]);b['ids'].extend([mi]*len(faces));b['smooth'].extend([smooth]*len(faces))

    def tube(self,role,mat,a,b,r1,r2=None,sides=7):
        a,b=Vector(a),Vector(b);axis=b-a
        if axis.length<1e-7:return
        z=axis.normalized();q=z.cross(Vector((0,0,1)))
        if q.length<.05:q=Vector((1,0,0))
        q.normalize();v=z.cross(q).normalized();r2=r1 if r2 is None else r2
        verts=[a+q*math.cos(_TAU*k/sides)*r1+v*math.sin(_TAU*k/sides)*r1 for k in range(sides)]
        verts += [b+q*math.cos(_TAU*k/sides)*r2+v*math.sin(_TAU*k/sides)*r2 for k in range(sides)]
        faces=[tuple(range(sides-1,-1,-1)),tuple(range(sides,sides*2))]+[(k,(k+1)%sides,(k+1)%sides+sides,k+sides) for k in range(sides)]
        self.mesh(role,mat,verts,faces,True)

    def leaf(self,role,mat,base,tip,width,fold=.10,twist=0):
        """A real, tapered folded lamina with a curved midrib and pointed tip."""
        base,tip=Vector(base),Vector(tip);d=tip-base
        axis=d.normalized();side=axis.cross(Vector((0,0,1)))
        if side.length<.1:side=Vector((1,0,0))
        side.normalize();normal=side.cross(axis).normalized()
        side=side*math.cos(twist)+normal*math.sin(twist)
        normal=side.cross(axis).normalized()
        verts=[base]
        for t in (.22,.5,.78):
            mid=base+d*t+normal*math.sin(math.pi*t)*fold
            w=width*math.sin(math.pi*t)**.86
            verts.extend([mid-side*w,mid+normal*fold*.20,mid+side*w])
        verts.append(tip)
        faces=[(0,1,2),(0,2,3)]
        for j in (1,4):
            faces.extend([(j,j+3,j+4,j+1),(j+1,j+4,j+5,j+2)])
        faces.extend([(7,10,8),(8,10,9)])
        self.mesh(role,mat,verts,faces,False)

    def stem(self,role,mat,points,radii,sides=10):
        verts=[]
        for c,r in zip(points,radii):
            verts.extend([(c[0]+math.cos(k*_TAU/sides)*r,c[1]+math.sin(k*_TAU/sides)*r,c[2]) for k in range(sides)])
        faces=[tuple(range(sides-1,-1,-1)),tuple(range((len(points)-1)*sides,len(points)*sides))]
        for j in range(len(points)-1):
            for k in range(sides):faces.append((j*sides+k,j*sides+(k+1)%sides,(j+1)*sides+(k+1)%sides,(j+1)*sides+k))
        self.mesh(role,mat,verts,faces,True)

    def finish(self):
        meshes={}
        for role,b in self.buckets.items():
            me=bpy.data.meshes.new(self.name+'__'+role);me.from_pydata(b['v'],[],b['f']);me.update()
            for mat in b['materials']:me.materials.append(mat)
            for f,mid,smooth in zip(me.polygons,b['ids'],b['smooth']):f.material_index=mid;f.use_smooth=smooth
            meshes[role]=me
        return meshes


def _broadleaf_proto(index,p):
    rng=random.Random(1901+index*37);b=Builder('PROTO_Broadleaf_'+str(index))
    H=[10.7,12.4,9.2,13.8,11.2,8.7,12.6,10.1][index];R=[4.1,4.8,4.0,4.6,5.2,3.8,4.3,4.7][index]
    lean=Vector((rng.uniform(-.45,.45),rng.uniform(-.45,.45),0))
    def trunk(t):return lean*t*t+Vector((0,0,H*t))
    basal=.34+(H-8)*.04
    t0=2.25/H
    b.stem('trunk_collider',p['bark'],[(0,0,-.65),(0,0,0),trunk(t0)],[basal*1.13,basal,basal*(1-t0*.75)],10)
    ts=[t0]+[j/16 for j in range(1,15) if j/16>t0]
    b.stem('upper_stem',p['bark'],[trunk(t) for t in ts],[basal*(1-t0*.75)*(1-(t-t0)/(.9-t0)*.92) for t in ts],10)
    # Five partly buried buttresses form a modest collar, not an exposed root cone.
    for j in range(5):
        a=j*_TAU/5+index*.37
        b.tube('root_collar',p['bark'],(math.cos(a)*basal*1.7,math.sin(a)*basal*1.7,-.12),(math.cos(a)*basal*.4,math.sin(a)*basal*.4,.34),basal*.20,basal*.13,7)
    # Crown is a branching scaffold, and each leaf spray has its own twig support.
    for j in range(19):
        ang=j*2.39996+rng.uniform(-.25,.25);tier=j/18
        origin=trunk(.34+.40*tier)
        radius=R*(.77+.23*math.sin(math.pi*tier))
        top=H*(.62+.30*tier)
        end=Vector((math.cos(ang)*radius*.50,math.sin(ang)*radius*.50,top))
        elbow=origin.lerp(end,.46)+Vector((0,0,-.25))
        b.tube('branches',p['bark'],origin,elbow,.14*(1-tier*.52),.083,8)
        b.tube('branches',p['bark'],elbow,end,.083,.039,7)
        for fork in range(4):
            fa=ang+(fork-1.5)*.60+rng.uniform(-.1,.1)
            end2=end+Vector((math.cos(fa)*R*.47,math.sin(fa)*R*.47,rng.uniform(.2,1.0)))
            b.tube('branches',p['bark'],end,end2,.043,.018,6)
            shoot_dir=(end2-end).normalized()
            for sub in range(2):
                sa=fa+(sub-.5)*1.12
                shoot_base=end.lerp(end2,.38+sub*.51)
                leaf_end=shoot_base+Vector((math.cos(sa)*rng.uniform(.9,1.45),math.sin(sa)*rng.uniform(.9,1.45),rng.uniform(.3,.8)))
                b.tube('twigs',p['bark'],shoot_base,leaf_end,.015,.006,5)
                stem=leaf_end-shoot_base;side=Vector((-math.sin(sa),math.cos(sa),0))
                for k in range(5):
                    t=.10+k*.19;attach=shoot_base+stem*t
                    for sign in (-1,1):
                        ll=rng.uniform(.58,.91)*(1-t*.16)
                        direction=side*sign+Vector((math.cos(sa)*.40,math.sin(sa)*.40,rng.uniform(-.08,.68)))
                        tip=attach+direction.normalized()*ll
                        color=(j+fork+sub+k+index)%len(p['leaves'])
                        b.leaf('articulated_leaves',p['leaves'][color],attach,tip,ll*(.31 if index%3 else .37),.048,rng.uniform(-.6,.6))
                b.leaf('articulated_leaves',p['leaves'][(j+index)%5],leaf_end-stem*.04,leaf_end+stem.normalized()*.4,.13,.024)
    return {'id':b.name,'family':'broadleaf','meshes':b.finish(),'height':H+1.4,'radius':R+1.9,'trunk_radius':basal,'soil_datum':0,'leaf_count':1672}


def _palm_proto(index,p):
    rng=random.Random(4080+index*17);b=Builder('PROTO_CoconutPalm_'+str(index))
    H=[13.6,16.5,11.8,14.8,17.5,12.7][index];bend=[1.1,1.75,.7,2.2,1.3,1.9][index]
    ang=rng.uniform(0,_TAU);lean=Vector((math.cos(ang)*bend,math.sin(ang)*bend,0))
    def stem(t):return lean*t*t+Vector((0,0,H*t))
    R=.28+H*.004
    t0=2.25/H
    b.stem('trunk_collider',p['palmstem'],[(0,0,-.65),(0,0,0),stem(t0)],[R*1.25,R,R*(1-.34*t0)],10)
    ts=[t0]+[j/24 for j in range(1,25) if j/24>t0]
    b.stem('upper_stem',p['palmstem'],[stem(t) for t in ts],[R*(1-.34*t) for t in ts],10)
    # Fine raised trunk scars follow the curved stem rather than horizontal world rings.
    for j in range(4,int(H/.31)):
        t=j*.31/H;pos=stem(t);a=stem(max(0,t-.001));c=stem(min(1,t+.001));d=(c-a).normalized()
        b.tube('growth_rings',p['barklight'],pos-d*.016,pos+d*.016,R*(1-.34*t)+.018,None,10)
    crown=stem(1)
    for j in range(14):
        a=j*2.39996+rng.uniform(-.12,.12);length=rng.uniform(5.0,6.9);rise=rng.uniform(1.0,2.4);sag=rng.uniform(1.6,3.3)
        outward=Vector((math.cos(a),math.sin(a),0));cross=Vector((-math.sin(a),math.cos(a),0))
        def point(t):return crown+outward*(length*t)+Vector((0,0,rise*math.sin(math.pi*t*.87)-sag*t*t))
        for s in range(12):
            b.tube('frond_ribs',p['palms'][2],point(s/12),point((s+1)/12),.048*(1-s/14),.046*(1-(s+1)/14),6)
        for k in range(23):
            t=.07+k*.039;origin=point(t);length_leaf=1.02*math.sin(math.pi*t)**.61*(.95+length*.065)
            for sign in (-1,1):
                tip=origin+cross*(sign*length_leaf)+outward*(.24+length_leaf*.12)+Vector((0,0,-.23-length_leaf*.19))
                b.leaf('pinnate_leaflets',p['palms'][(j+k+index)%4],origin,tip,.055+length_leaf*.030,.042,sign*.18)
        b.leaf('pinnate_leaflets',p['palms'][(index+j)%4],point(.94),point(1.025),.10,.025)
    # Two upright juvenile fronds break the radial silhouette.
    for j in range(2):
        a=ang+j*1.7;direction=Vector((math.cos(a)*1.1,math.sin(a)*1.1,3.1))
        tip=crown+direction;b.tube('frond_ribs',p['palms'][1],crown,tip,.065,.019,7)
        for k in range(13):
            t=.18+k*.053;base=crown+direction*t
            side=Vector((-math.sin(a),math.cos(a),-.3))
            for sign in (-1,1):b.leaf('pinnate_leaflets',p['palms'][(index+j)%4],base,base+side*sign*(1-t)*1.1+direction*.05,.07,.025)
    for j in range(5):
        a=j*1.9;c=crown+Vector((math.cos(a)*.44,math.sin(a)*.44,-.35-j*.055))
        b.tube('coconut_cluster',p['coconut'],c-Vector((0,0,.15)),c+Vector((0,0,.15)),.19,.155,10)
    return {'id':b.name,'family':'palm','meshes':b.finish(),'height':H+3.4,'radius':8.2,'trunk_radius':R,'soil_datum':0,'leaf_count':710}


def _fern_proto(index,p):
    rng=random.Random(911+index);b=Builder('PROTO_Fern_'+str(index));H=[1.0,1.4,1.85][index]
    for j in range(11):
        a=j*2.39996;rad=H*rng.uniform(.62,1.12);unit=Vector((math.cos(a),math.sin(a),0));side=Vector((-math.sin(a),math.cos(a),0))
        def pt(t):return unit*rad*t+Vector((0,0,H*(math.sin(t*math.pi*.85)*.6+.20*t)))
        for k in range(7):b.tube('fern_stems',p['ferns'][0],pt(k/7),pt((k+1)/7),.014*(1-k/10),.012*(1-k/10),5)
        for k in range(13):
            t=.13+k*.062;base=pt(t);ll=H*.27*math.sin(t*math.pi)**.72
            for sign in (-1,1):b.leaf('fern_leaflets',p['ferns'][(k+j)%3],base,base+side*sign*ll+unit*ll*.36+Vector((0,0,-ll*.10)),ll*.14,.019)
    return {'id':b.name,'family':'fern','meshes':b.finish(),'height':H,'radius':H*1.2,'soil_datum':0}


def _shrub_proto(index,p):
    rng=random.Random(9930+index);b=Builder('PROTO_CoastalShrub_'+str(index));H=[1.7,2.4,3.0][index]
    for j in range(12):
        a=j*2.39996;r=H*.5*rng.uniform(.6,1.1);top=Vector((math.cos(a)*r,math.sin(a)*r,H*rng.uniform(.65,1)))
        b.tube('shrub_branches',p['bark'],(0,0,-.15),top,.04,.012,6)
        for k in range(6):
            origin=top*(.40+k*.09);sa=a+k*.73;ll=rng.uniform(.26,.48)
            for sign in (-1,1):
                tip=origin+Vector((math.cos(sa)*sign*ll,math.sin(sa)*sign*ll,.13))
                b.leaf('shrub_leaves',p['leaves'][(j+k+index)%5],origin,tip,ll*.37,.035)
    return {'id':b.name,'family':'shrub','meshes':b.finish(),'height':H,'radius':H*.6+.5,'soil_datum':0}


def _rock_proto(index,p):
    rng=random.Random(6420+index);b=Builder('PROTO_Limestone_'+str(index))
    N=19;layers=[(-.72,.84),(-.08,1.08),(.34,1.02),(.86,.91),(1.40,.84),(1.97,.73),(2.57,.50),(3.08,.23)]
    verts=[]
    # Faceted, eroded rock beds with offset ridgelines and directional faulting.
    phase=rng.uniform(0,_TAU);rad=[rng.uniform(.73,1.17) for _ in range(N)]
    for j,(z,r) in enumerate(layers):
        for k in range(N):
            a=k*_TAU/N+phase+(.055 if j%2 else 0);rr=r*rad[k]*rng.uniform(.94,1.06)
            verts.append((math.cos(a)*rr*1.43+.055*j,math.sin(a)*rr*1.07-.025*j,z+rng.uniform(-.18,.18)))
    faces=[]
    for j in range(len(layers)-1):
        for k in range(N):
            a=j*N+k;bidx=j*N+(k+1)%N;c=(j+1)*N+(k+1)%N;d=(j+1)*N+k
            if (j+k)%3:faces.extend([(a,bidx,c),(a,c,d)])
            else:faces.append((a,bidx,c,d))
    faces.append(tuple(range((len(layers)-1)*N,len(layers)*N)))
    for i,f in enumerate(faces):
        v0,v1,v2=[Vector(verts[j]) for j in f[:3]];normal=(v1-v0).cross(v2-v0).normalized();midz=sum(verts[j][2] for j in f)/len(f)
        mat=p['rocklight'] if normal.z>.60 else p['rockdark'] if normal.x<-.70 and midz<1.0 else p['rock']
        b.mesh('weathered_limestone',mat,[verts[j] for j in f],[tuple(range(len(f)))])
    return {'id':b.name,'family':'rock','meshes':b.finish(),'height':3.2,'radius':1.8,'soil_datum':0}


def build_prototypes():
    """Return mesh-only reusable prototypes; no hidden geometry or scene reset."""
    global _PROTOTYPES
    if _PROTOTYPES is None:
        p=_palette()
        _PROTOTYPES={
            'broadleaf':[_broadleaf_proto(i,p) for i in range(8)],
            'palm':[_palm_proto(i,p) for i in range(6)],
            'fern':[_fern_proto(i,p) for i in range(3)],
            'shrub':[_shrub_proto(i,p) for i in range(3)],
            'rock':[_rock_proto(i,p) for i in range(9)],
        }
    return _PROTOTYPES


def _instantiate(proto,name,pos,scale,angle,col,region):
    out=[]
    for role,me in proto['meshes'].items():
        ob=instance(name+'__'+role,me,pos,(scale,scale,scale),angle,col)
        ob['asset_family']=proto['family'];ob['prototype_id']=proto['id'];ob['region_id']=region;ob['component_role']=role;ob['planting_datum_z']=float(pos[2]);ob['soil_contact_local_z']=0.0
        ob['collider']=role=='trunk_collider'
        if role=='trunk_collider':ob['collision_role']='lower_trunk_only'
        out.append(ob)
    return out


def _point_segment(px,py,a,b):
    dx=b[0]-a[0];dy=b[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((px-a[0])*dx+(py-a[1])*dy)/den)) if den else 0
    return math.hypot(px-a[0]-t*dx,py-a[1]-t*dy)


def _poly_inside(x,y,poly):
    inside=False
    for i in range(len(poly)):
        a,b=poly[i-1],poly[i]
        if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:inside=not inside
    return inside


class Reservations:
    def __init__(self):
        # Spatial bin of rail samples makes exact corridor checks inexpensive.
        self.rail={};self.cells=12
        for route in RAILS:
            for p in route['points']:
                k=(math.floor(p[0]/self.cells),math.floor(p[1]/self.cells));self.rail.setdefault(k,[]).append(p)
        self.villas=[(*xy(v),v[2]) for v in VILLAS]
        self.paths=[];self.rects={};self.polys=[]
        def add_rect(a,b,c,d):
            for ix in range(math.floor(a/self.cells),math.floor(c/self.cells)+1):
                for iy in range(math.floor(b/self.cells),math.floor(d/self.cells)+1):self.rects.setdefault((ix,iy),[]).append((a,b,c,d))
        for d in DOCKS:
            q=[xy(p) for p in d['points']]
            self.paths.extend((q[j],q[j+1],d['width']*.5+2.0) for j in range(len(q)-1))
        for d in STILT_DISTRICTS:
            self.paths.append((xy(d['shore']),xy(d['hub']),4.0))
        # Known built circulation can add semantic reservations without rebuilding layout.
        bpy.context.view_layer.update()
        for ob in bpy.context.scene.objects:
            if ob.type!='MESH':continue
            lower=ob.name.lower();role=str(ob.get('component_role','')).lower()
            if bool(ob.get('walkable',False)) and not ob.name.startswith(('REG_','RAIL_')):
                if any(s in lower+' '+role for s in ('lane','path','street','boardwalk','plaza','walkway','platform','dock','steps')):
                    pts=[ob.matrix_world@Vector(c) for c in ob.bound_box]
                    if max(ob.dimensions.x,ob.dimensions.y)<35:
                        add_rect(min(p.x for p in pts)-1.1,min(p.y for p in pts)-1.1,max(p.x for p in pts)+1.1,max(p.y for p in pts)+1.1)
                    else:
                        for face in ob.data.polygons:
                            pts=[ob.matrix_world@ob.data.vertices[j].co for j in face.vertices]
                            add_rect(min(p.x for p in pts)-1.1,min(p.y for p in pts)-1.1,max(p.x for p in pts)+1.1,max(p.y for p in pts)+1.1)
            raw=ob.get('footprint')
            if raw:
                try:self.polys.append([(float(p[0]),float(p[1])) for p in raw])
                except (TypeError,ValueError):pass

    def rail_distance(self,x,y):
        kx,ky=math.floor(x/self.cells),math.floor(y/self.cells);d=1e6
        for a in range(kx-1,kx+2):
            for b in range(ky-1,ky+2):
                for p in self.rail.get((a,b),[]):d=min(d,math.hypot(x-p[0],y-p[1]))
        return d

    def blocked(self,x,y,margin=0):
        if self.rail_distance(x,y)<9+margin:return True
        for vx,vy,angle in self.villas:
            dx=x-vx;dy=y-vy
            if abs(dx)>20 or abs(dy)>20:continue
            cs=math.cos(angle);sn=math.sin(angle);lx=dx*cs+dy*sn;ly=-dx*sn+dy*cs
            if abs(lx)<12.0+margin and abs(ly)<10.0+margin:return True
        for p in PLAZAS:
            cx,cy=xy(p['center']);rx=p['radius'][0]*.65+4+margin;ry=p['radius'][1]*.82+4+margin
            if ((x-cx)/rx)**2+((y-cy)/ry)**2<1.0:return True
        for a,b,w in self.paths:
            if _point_segment(x,y,a,b)<w+margin:return True
        rects=[]
        key=(math.floor(x/self.cells),math.floor(y/self.cells))
        for ix in range(key[0]-1,key[0]+2):
            for iy in range(key[1]-1,key[1]+2):rects.extend(self.rects.get((ix,iy),[]))
        for a,b,c,d in rects:
            if a-margin<x<c+margin and b-margin<y<d+margin:return True
        for poly in self.polys:
            if _poly_inside(x,y,poly):return True
            if any(_point_segment(x,y,poly[j-1],poly[j])<2+margin for j in range(len(poly))):return True
        return False


class Ground:
    def __init__(self):
        self.bvhs={};self.checked=0;self.failed=0;self.analytical_fallback=0;self.max_correction=0
        for isle in ISLANDS:
            obj=bpy.data.objects.get(isle['id'])
            if obj and obj.type=='MESH':
                mat=obj.matrix_world;verts=[mat@v.co for v in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons]
                self.bvhs[isle['id']]=BVHTree.FromPolygons(verts,faces,all_triangles=False)

    def height(self,isle,x,y,radius=.4):
        estimate=at(x,y);bvh=self.bvhs.get(isle['id'])
        if bvh is None:self.analytical_fallback+=1;return estimate-.12
        hit,normal,_,_=bvh.ray_cast(Vector((x,y,200)),Vector((0,0,-1)),300)
        if hit is None:self.failed+=1;return None
        # Footprint samples ensure the partly buried root collar never hovers downhill.
        heights=[hit.z]
        for a in (0,math.pi*.5,math.pi,math.pi*1.5):
            point,_,_,_=bvh.ray_cast(Vector((x+math.cos(a)*radius,y+math.sin(a)*radius,200)),Vector((0,0,-1)),300)
            if point is not None:heights.append(point.z)
        h=min(heights)-.10
        if max(heights)-min(heights)>1.25:return None
        self.checked+=1;self.max_correction=max(self.max_correction,abs(hit.z-estimate))
        return h


def _area(isle):
    p=[xy(q) for q in isle['shore']]
    return abs(sum(p[j][0]*p[(j+1)%len(p)][1]-p[(j+1)%len(p)][0]*p[j][1] for j in range(len(p)))/2)


def build_vegetation():
    """Build region-coherent planting; return source counts and grounding evidence."""
    prototypes=build_prototypes();reserve=Reservations();ground=Ground();counts={k:0 for k in prototypes};regions=[];placements=[]
    for isle in ISLANDS:
        col=collection('10 • '+isle['name']+' vegetation');rng=random.Random(isle['seed']*997);poly=[xy(q) for q in isle['shore']];xmin=min(p[0] for p in poly);xmax=max(p[0] for p in poly);ymin=min(p[1] for p in poly);ymax=max(p[1] for p in poly);area=_area(isle)
        density=.0063
        if isle['id']=='REG_NORTH':density=.0080
        elif isle['id']=='REG_NORTHEAST':density=.0075
        elif isle['id']=='REG_MAIN':density=.0055
        elif isle['id']=='REG_SOUTHEAST':density=.0065
        elif isle['id']=='REG_CENTER_CAY':density=.0027
        elif isle['id']=='REG_CENTRAL_PALMS':density=.0020
        targets={'broadleaf':int(area*density),'palm':int(area*.00215),'shrub':int(area*.0035),'fern':int(area*.0020),'rock':int(area*.0017)}
        if isle['id'] in ('REG_WEST_LAGOON','REG_CENTRAL_PALMS'):targets['palm']=int(area*.0048)
        if isle['id']=='REG_CENTER_CAY':targets['palm']=8
        region_counts={k:0 for k in prototypes};occupied={};cell=5.5
        def near_plant(x,y,radius):
            key=(math.floor(x/cell),math.floor(y/cell))
            for a in range(key[0]-2,key[0]+3):
                for b in range(key[1]-2,key[1]+3):
                    for xx,yy,rr in occupied.get((a,b),[]):
                        if math.hypot(x-xx,y-yy)<radius+rr:return True
            return False
        for family in ('palm','broadleaf','rock','shrub','fern'):
            accepted=0;attempts=0
            while accepted<targets[family] and attempts<targets[family]*90+50:
                attempts+=1;x=rng.uniform(xmin,xmax);y=rng.uniform(ymin,ymax);coast=island_distance(isle,x,y)
                if coast<2.8:continue
                h=at(x,y)
                if h<1.5:continue
                if reserve.blocked(x,y,1.5 if family=='broadleaf' else .65 if family=='palm' else 0):continue
                if family=='palm':
                    # Palms favor beach shoulders, village margins and low lagoon islands.
                    if coast>25 and h>13 and rng.random()<.90:continue
                    if coast>38 and rng.random()<.86:continue
                    radius=2.5
                elif family=='broadleaf':
                    if coast<10:continue
                    if h<7 and rng.random()<.65:continue
                    radius=2.9
                elif family=='rock':
                    if coast>9 and h<17 and rng.random()<.95:continue
                    if coast>9 and rng.random()<.40:continue
                    radius=1.5
                elif family=='fern':
                    if coast<14 or h<9:continue
                    radius=.7
                else:
                    if coast<6:continue
                    radius=.9
                if near_plant(x,y,radius):continue
                proto=rng.choice(prototypes[family]);scale=rng.uniform(.79,1.20)
                if family=='rock':scale=rng.uniform(2.0,5.5) if h>15 else rng.uniform(.65,2.7)
                gz=ground.height(isle,x,y,min(1.2,proto.get('trunk_radius',.4)*scale))
                if gz is None:continue
                # Rock roots deliberately continue below the final terrain triangles.
                if family=='rock':gz-=.15*scale
                name='VEG_'+isle['id'][4:]+'_'+family.upper()+f'_{accepted:04d}'
                _instantiate(proto,name,(x,y,gz),scale,rng.uniform(0,_TAU),col,isle['id'])
                key=(math.floor(x/cell),math.floor(y/cell));occupied.setdefault(key,[]).append((x,y,radius if family in ('palm','broadleaf') else radius*.5))
                placements.append({'id':name,'region':isle['id'],'family':family,'prototype':proto['id'],'position':[round(x,3),round(y,3),round(gz,3)],'scale':round(scale,4),'soil_datum':0})
                accepted+=1;counts[family]+=1;region_counts[family]+=1
            if accepted<targets[family]*.75:print('VEGETATION_DENSITY_CONSTRAINED',isle['id'],family,accepted,targets[family],flush=True)
        regions.append({'id':isle['id'],'area_m2':round(area,1),'counts':region_counts,'targets':targets})
        # Deliberate fracture clusters break smooth hill silhouettes into limestone ridges.
        if isle['id'] in ('REG_NORTH','REG_NORTHEAST','REG_MAIN','REG_SOUTHEAST'):
            for hi,hill in enumerate(isle['hills']):
                hx,hy,hh,rx,ry=hill;cx,cy=xy((hx,hy))
                for j in range(10 if hh>40 else 6):
                    a=(j*.67+hi*1.7);rad=rng.uniform(.20,.70);x=cx+math.cos(a)*rx*.65*rad;y=cy+math.sin(a)*ry*.82*rad
                    if reserve.blocked(x,y,3.5) or island_distance(isle,x,y)<8:continue
                    h=at(x,y)
                    if h<15:continue
                    gz=ground.height(isle,x,y,.7)
                    if gz is None:continue
                    proto=rng.choice(prototypes['rock']);scale=rng.uniform(3.7,6.7) if hh>40 else rng.uniform(2.8,4.6)
                    name='VEG_'+isle['id'][4:]+'_RIDGE_'+str(hi)+'_'+str(j)
                    _instantiate(proto,name,(x,y,gz-.40*scale),scale,a,col,isle['id']);counts['rock']+=1;region_counts['rock']+=1
                    placements.append({'id':name,'region':isle['id'],'family':'rock','prototype':proto['id'],'position':[round(x,3),round(y,3),round(gz-.4*scale,3)],'scale':round(scale,4),'soil_datum':0})
    report={'counts':counts,'regions':regions,'prototype_count':sum(len(a) for a in prototypes.values()),'grounding':{'actual_triangle_samples':ground.checked,'analytical_fallbacks':ground.analytical_fallback,'missing_support_rejections':ground.failed,'max_analytic_to_mesh_correction_m':round(ground.max_correction,4),'root_embed_m':.10},'collision':'Only lower trunk meshes; crowns and branches have no collider.','rail_clearance_m':9,'geometry':'Actual folded laminae, pinnae, branched scaffold and faceted limestone; no billboard or canopy blob proxies.','placements':placements}
    out=Path(__file__).resolve().parents[1]/'vegetation_registry.json';out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('VEGETATION_COMPLETE',json.dumps({k:v for k,v in report.items() if k not in ('placements','regions')}),flush=True)
    return report


def inspect_prototypes():
    """Local isolated prototype inspection, invoked only by executing this file."""
    from core import light_scene,camera
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    ps=build_prototypes();col=collection('Prototype inspection');rows=[]
    for i,proto in enumerate(ps['broadleaf'][:4]+ps['palm'][:3]):
        x=(i-3)*18;_instantiate(proto,proto['id'],(x,0,0),1,0,col,'INSPECTION');rows.append(proto['id'])
    for i,proto in enumerate(ps['fern']+ps['shrub']+ps['rock'][:3]):_instantiate(proto,proto['id'],(-20+i*5,-9,0),1.4,0,col,'INSPECTION')
    from core import box
    box('Inspection soil',(0,0,-.35),(160,65,.7),material('VEG Inspection sand',(.65,.59,.41),.95),col)
    light_scene();s=bpy.context.scene;s.render.engine='BLENDER_EEVEE';s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
    out=Path(__file__).resolve().parents[1]/'renders'/'vegetation_details';out.mkdir(parents=True,exist_ok=True)
    s.camera=camera('Botanical families',(58,-90,42),(0,0,8),ortho=140);s.render.resolution_x=2000;s.render.resolution_y=1000;s.render.filepath=str(out/'botanical_families.png');bpy.ops.render.render(write_still=True)
    s.camera=camera('Broadleaf detail',(-40,-15,10),(-36,0,7),ortho=18);s.render.resolution_x=1300;s.render.resolution_y=1300;s.render.filepath=str(out/'broadleaf_detail.png');bpy.ops.render.render(write_still=True)
    s.camera=camera('Palm detail',(16,-22,18),(18,0,12),ortho=23);s.render.filepath=str(out/'palm_detail.png');bpy.ops.render.render(write_still=True)
    stats={family:[{'id':p['id'],'vertices':sum(len(m.vertices) for m in p['meshes'].values()),'faces':sum(len(m.polygons) for m in p['meshes'].values()),'components':len(p['meshes']),'finite_vertices':all(math.isfinite(c) for m in p['meshes'].values() for v in m.vertices for c in v.co),'zero_face_normals':sum(1 for m in p['meshes'].values() for f in m.polygons if f.normal.length<.99),'zero_area_faces':sum(1 for m in p['meshes'].values() for f in m.polygons if f.area<1e-10)} for p in items] for family,items in ps.items()}
    (out/'prototype_validation.json').write_text(json.dumps(stats,indent=2));print('BOTANICAL_PROTOTYPES_VALIDATED',json.dumps(stats),flush=True)


if __name__=='__main__':inspect_prototypes()
