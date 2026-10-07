"""Reference-positioned villages, connected lagoon districts and inhabited docks.

Stages are safe to call independently in an existing Blender scene. All public
functions return JSON-compatible records. Visible surfaces own their walkable
tags; exterior building geometry is solid and interiors remain closed.
"""
import math
import bpy
from mathutils import Vector
from layout import xy, pixel, VILLAS, PLAZAS, STILT_DISTRICTS, DOCKS, catmull
from terrain import at, nearest_island
from core import collection, material, mesh, box, cylinder, beam
import architecture as A

# GEOS is already present in the local Python 3.13 user environment. The Blender
# runtime deliberately ignores that search path, so expose the existing package.
try:
    from shapely.geometry import Polygon, Point, LineString, GeometryCollection
    from shapely.ops import unary_union
    from shapely import constrained_delaunay_triangles
except ImportError:
    import site,sys
    userpackages=site.getusersitepackages()
    if userpackages not in sys.path:sys.path.append(userpackages)
    from shapely.geometry import Polygon, Point, LineString, GeometryCollection
    from shapely.ops import unary_union
    from shapely import constrained_delaunay_triangles

_SURFACE_RECORDS=[]
_SURFACE_GRID={}
_PLAZA_SURFACES=[]
_SURFACE_UNION=GeometryCollection()
_SURFACE_READY=False


def _grid_keys(bounds):
    x0,y0,x1,y1=bounds
    for i in range(math.floor(x0/4),math.floor(x1/4)+1):
        for j in range(math.floor(y0/4),math.floor(y1/4)+1):yield (i,j)


def _register_triangle(vertices,owner):
    poly=Polygon([(p[0],p[1]) for p in vertices])
    if poly.area<1e-9:return None
    idx=len(_SURFACE_RECORDS);_SURFACE_RECORDS.append((poly,vertices,owner))
    for key in _grid_keys(poly.bounds):_SURFACE_GRID.setdefault(key,[]).append(idx)
    return poly


def _surface_height(x,y,exclude_owner=None):
    point=Point(x,y)
    for poly,z in _PLAZA_SURFACES:
        if poly.distance(point)<1e-7:return z
    ids=_SURFACE_GRID.get((math.floor(x/4),math.floor(y/4)),[])
    for idx in ids:
        poly,coords,owner=_SURFACE_RECORDS[idx]
        if owner==exclude_owner:continue
        a,b,c=coords
        den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
        if abs(den)<1e-12:continue
        u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
        v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den;w=1-u-v
        if min(u,v,w)>-1e-6:return a[2]*u+b[2]*v+c[2]*w
    return None


def _surface_context():
    """Recover prior-stage ownership when a later saved checkpoint is loaded."""
    global _SURFACE_READY,_SURFACE_UNION
    if _SURFACE_READY:return
    polygons=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH':continue
        if ob.get('plaza_shape')=='soft rectangular civic square':
            points=[ob.matrix_world@v.co for v in ob.data.vertices]
            poly=Polygon([(v.x,v.y) for v in points[1:]])
            _PLAZA_SURFACES.append((poly,points[0].z));polygons.append(poly)
        elif ob.get('surface_owner_type')=='village_path':
            for face in list(ob.data.polygons)[:int(ob.get('surface_top_faces',0))]:
                coords=[tuple(ob.matrix_world@ob.data.vertices[i].co) for i in face.vertices]
                if len(coords)!=3:continue
                poly=_register_triangle(coords,ob.name)
                if poly is not None:polygons.append(poly)
    _SURFACE_UNION=unary_union(polygons) if polygons else GeometryCollection()
    _SURFACE_READY=True


def _claim_surface_triangle(coords,owner,verts,faces,claimed):
    """Clip one top triangle against prior owners, including same-path loops."""
    poly=Polygon([(p[0],p[1]) for p in coords])
    if poly.area<1e-8:return
    ids=set()
    for key in _grid_keys(poly.bounds):ids.update(_SURFACE_GRID.get(key,()))
    cutters=[_SURFACE_RECORDS[i][0] for i in ids if _SURFACE_RECORDS[i][0].intersects(poly)]
    cutters.extend(p for p,z in _PLAZA_SURFACES if p.intersects(poly))
    remainder=poly.difference(unary_union(cutters)) if cutters else poly
    if remainder.is_empty:return
    pieces=[remainder] if remainder.geom_type=='Polygon' else [p for p in remainder.geoms if p.geom_type=='Polygon']
    a,b,c=coords;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
    for piece in pieces:
        if piece.area<1e-8:continue
        for tri in constrained_delaunay_triangles(piece).geoms:
            new=[]
            for x,y in list(tri.exterior.coords)[:3]:
                u=((b[1]-c[1])*(x-c[0])+(c[0]-b[0])*(y-c[1]))/den
                v=((c[1]-a[1])*(x-c[0])+(a[0]-c[0])*(y-c[1]))/den
                z=a[2]*u+b[2]*v+c[2]*(1-u-v)
                existing=_surface_height(x,y,exclude_owner=owner)
                new.append((x,y,z if existing is None else existing))
            # GEOS may choose either winding; top normals must face upwards.
            cross=(new[1][0]-new[0][0])*(new[2][1]-new[0][1])-(new[1][1]-new[0][1])*(new[2][0]-new[0][0])
            if cross<0:new[1],new[2]=new[2],new[1]
            idx=len(verts);verts.extend(new);faces.append((idx,idx+1,idx+2))
            registered=_register_triangle(new,owner)
            if registered is not None:claimed.append(registered)


def _clipped_wall(a,b,lo_a,lo_b,mask,owner,verts,faces):
    line=LineString([a[:2],b[:2]])
    if line.length<1e-8:return
    remainder=line.difference(mask)
    parts=[remainder] if remainder.geom_type=='LineString' else [q for q in getattr(remainder,'geoms',[]) if q.geom_type=='LineString']
    dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
    for part in parts:
        if part.length<1e-6:continue
        for p,q in zip(part.coords,list(part.coords)[1:]):
            output=[]
            for x,y in [p,q]:
                t=((x-a[0])*dx+(y-a[1])*dy)/den
                top=a[2]*(1-t)+b[2]*t;bottom=lo_a*(1-t)+lo_b*t
                existing=_surface_height(x,y,exclude_owner=owner)
                if existing is not None:top=existing;bottom=min(bottom,top)
                output.extend([(x,y,bottom),(x,y,top)])
            if max(output[1][2]-output[0][2],output[3][2]-output[2][2])<1e-6:continue
            idx=len(verts);verts.extend(output);faces.append((idx,idx+2,idx+3,idx+1))


_SUPPORT_CACHE={}
def _support(x,y):
    """Sample actual rendered island triangles, falling back to semantic height."""
    key=(round(x,3),round(y,3))
    if key in _SUPPORT_CACHE:return _SUPPORT_CACHE[key]
    isle=nearest_island(x,y);ob=bpy.data.objects.get(isle['id'])
    if ob and ob.type=='MESH':
        hit,loc,normal,index=ob.ray_cast(Vector((x,y,200)),Vector((0,0,-1)))
        if hit:
            _SUPPORT_CACHE[key]=loc.z
            return loc.z
    value=at(x,y);_SUPPORT_CACHE[key]=value;return value


def _tag(record,region=None):
    for ob in record['objects']:
        role=ob.get('component_role','')
        ob['asset_id']=record['parent'].name
        if region:ob['region_id']=region
        ob['collider']=True
        if any(q in role for q in ['deck_planks','entrance_steps','veranda_floor','balcony_slab']):ob['walkable']=True
    record['parent']['collider']=True
    return {'id':record['parent'].name,'footprint':record['footprint'],'entrance':record['entrance'],'floor_z':record['floor_z'],'obstacles':record['obstacles'],'region':region}


def _nearest(p,polylines):
    best=None
    for path in polylines:
        for a,b in zip(path,path[1:]):
            dx,dy=b[0]-a[0],b[1]-a[1]
            den=dx*dx+dy*dy
            t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(den or 1)))
            q=(a[0]+dx*t,a[1]+dy*t)
            dist=math.dist(p[:2],q)
            if best is None or dist<best[0]:best=(dist,q)
    return best[1]


def _sample_poly(points,spacing=.75):
    result=[]
    for aa,bb in zip(points,points[1:]):
        n=max(1,math.ceil(math.dist(aa[:2],bb[:2])/spacing))
        for j in range(n):
            t=j/n
            result.append(tuple(aa[k]*(1-t)+bb[k]*t for k in range(len(aa))))
    result.append(tuple(points[-1]));return result


def _terrain_path(name,points,width=3.3,pixels=True,mat=None,start_z=None):
    global _SURFACE_UNION
    _surface_context()
    prior_mask=_SURFACE_UNION
    points=[xy(p) for p in points] if pixels else points
    path=catmull(points,.35) if len(points)>2 else _sample_poly(points,.35)
    heights=[max(.15,_support(*p))+.085 for p in path]
    if start_z is not None:
        distance=0
        for i in range(len(path)):
            if i:distance+=math.dist(path[i],path[i-1])
            heights[i]=max(heights[i],start_z-.35*distance)
    # Hillside routes hug the actual hill rather than introducing tall artificial
    # berms. Steeper runs have real horizontal treads, each no higher than .25m.
    dense=[];denseh=[]
    for i in range(len(path)-1):
        n=max(1,math.ceil(abs(heights[i+1]-heights[i])/.25))
        for j in range(n):
            t=j/n;dense.append(tuple(path[i][k]*(1-t)+path[i+1][k]*t for k in range(2)));denseh.append(heights[i]*(1-t)+heights[i+1]*t)
    path=dense+[path[-1]];heights=denseh+[heights[-1]]
    sections=[]
    for i,(p,h) in enumerate(zip(path,heights)):
        before=path[max(0,i-1)];after=path[min(len(path)-1,i+1)]
        dx,dy=after[0]-before[0],after[1]-before[1];norm=math.hypot(dx,dy) or 1
        nx,ny=-dy/norm,dx/norm
        section=[]
        for s in [-1,1]:
            X,Y=p[0]+s*nx*width/2,p[1]+s*ny*width/2
            side_h=max(h,_support(X,Y)+.045)
            section.append((X,Y,side_h))
        sections.append(section)
    # Each physical top face is geometrically clipped before emission. There is
    # exactly one visible paving owner at crossings and throughout the plaza.
    verts=[];faces=[];claimed=[];outer_walls=[];risers=[];last_end=None
    for i in range(len(path)-1):
        run=math.dist(path[i],path[i+1]);rise=heights[i+1]-heights[i]
        a0,a1=sections[i];b0,b1=sections[i+1]
        if abs(rise)>.42*run:
            h=max(p[2] for p in [a0,a1,b0,b1])
            a0,a1,b0,b1=[(p[0],p[1],h) for p in [a0,a1,b0,b1]]
        _claim_surface_triangle([a0,b0,b1],name,verts,faces,claimed)
        _claim_surface_triangle([a0,b1,a1],name,verts,faces,claimed)
        outer_walls.extend([(a0,b0,min(a0[2]-.13,_support(*a0[:2])-.12),min(b0[2]-.13,_support(*b0[:2])-.12)),(b1,a1,min(b1[2]-.13,_support(*b1[:2])-.12),min(a1[2]-.13,_support(*a1[:2])-.12))])
        if last_end:
            lo0,lo1=last_end
            if max(abs(a0[2]-lo0[2]),abs(a1[2]-lo1[2]))>1e-5:
                top0=(a0[0],a0[1],max(a0[2],lo0[2]));top1=(a1[0],a1[1],max(a1[2],lo1[2]))
                risers.append((top0,top1,min(a0[2],lo0[2]),min(a1[2],lo1[2])))
        last_end=(b0,b1)
    top_faces=len(faces)
    local_mask=unary_union(claimed) if claimed else GeometryCollection()
    exterior_mask=unary_union([prior_mask,local_mask.buffer(-.002)])
    for wall in outer_walls:_clipped_wall(*wall,exterior_mask,name,verts,faces)
    for wall in risers:_clipped_wall(*wall,prior_mask,name,verts,faces)
    _SURFACE_UNION=unary_union([prior_mask,local_mask])
    col=collection('06 • Village lanes and plazas')
    if verts:
        ob=mesh(name,verts,faces,mat or material('Warm worn village paving',(.61,.54,.38),.96),col)
        ob['walkable']=True;ob['route_id']=name;ob['surface_owner_type']='village_path';ob['surface_top_faces']=top_faces;ob['owned_paving_area_m2']=float(local_mask.area)
    print('PAVING_OWNER',name,'top_triangles',top_faces,'area_m2',round(local_mask.area,3),flush=True)
    return {'id':name,'points':[[p[0],p[1],h] for p,h in zip(path,heights)],'width':width,'surface_ownership':'exact polygon clipping; prior paving owns intersections','owned_surface_area_m2':float(local_mask.area)}


def _foundation(record,base_z):
    # Dependent foundation follows the actual occupied solid polygon. Basement
    # contact is resolved under each building, independently of public routes.
    if not record['obstacles']:return
    polygon=record['obstacles'][0]['polygon']
    p=[(q[0],q[1],min(base_z-.24,_support(q[0],q[1])-.30)) for q in polygon]
    top=base_z+.08
    verts=p+[(q[0],q[1],top) for q in polygon]
    faces=[(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]
    ob=mesh(record['parent'].name+'__terrain_bearing',verts,faces,material('Terrain bearing stone',(.46,.45,.36),.94),record['collection'])
    ob['collider']=True;ob['structural_contact']='Ground sampled at each footprint corner'


def _plaza(plaza):
    global _SURFACE_UNION
    _surface_context()
    col=collection('06 • Village lanes and plazas');cx,cy=xy(plaza['center']);rx=plaza['radius'][0]*.65;ry=plaza['radius'][1]*.82;z=plaza['level']+.045
    hw=rx*(.85 if plaza['id']=='PORTO_PLAZA' else .81);hh=ry*(.58 if plaza['id']=='PORTO_PLAZA' else .66);corner=5.5 if plaza['id']=='PORTO_PLAZA' else 4.3
    outline=[]
    for ox,oy,start in [(hw-corner,hh-corner,0),(-hw+corner,hh-corner,90),(-hw+corner,-hh+corner,180),(hw-corner,-hh+corner,270)]:
        for j in range(13):
            ang=math.radians(start+j*90/12);outline.append((cx+ox+math.cos(ang)*corner,cy+oy+math.sin(ang)*corner,z))
    verts=[(cx,cy,z)]+outline
    plaza_polygon=Polygon([(p[0],p[1]) for p in outline])
    _PLAZA_SURFACES.append((plaza_polygon,z));_SURFACE_UNION=unary_union([_SURFACE_UNION,plaza_polygon])
    ob=mesh(plaza['id']+' paving',verts,[(0,1+i,1+(i+1)%len(outline)) for i in range(len(outline))],material('Sunlit square limestone',(.68,.60,.44),.91),col);ob['walkable']=True;ob['plaza_shape']='soft rectangular civic square'
    # Pale slabs are resolved by a restrained, full-scale bonded paving joint
    # rhythm. Their tiny relief touches the paving, without floating overlays.
    a=A.Assembly(plaza['id']+'_furniture',cx,cy,z);p=A.palette(1)
    joint=material('Limestone paving joints',(.49,.45,.35),.99)
    def clip_extent(t,extent,other):
        if abs(t)<=other-corner:return extent
        dd=abs(t)-(other-corner)
        return extent-corner+math.sqrt(max(0,corner*corner-dd*dd))
    for i in range(-int(hh/.95),int(hh/.95)+1):
        yy=i*.95;span=clip_extent(yy,hw,hh)
        a.box('paving_bed_joints',joint,(0,yy,.002),(span*2,.022,.010))
        for j in range(-int(span/1.6),int(span/1.6)+1):
            xx=j*1.6+(i%2)*.8
            yy2=min(hh-.02,yy+.92)
            if yy2>yy and abs(xx)<min(span,clip_extent(yy2,hw,hh))-.03:a.box('paving_cross_joints',joint,(xx,(yy+yy2)/2,.002),(.022,yy2-yy,.010))
    if plaza['id']=='PORTO_PLAZA':
        for i in range(40):
            ang=math.tau*i/40;pos=(math.cos(ang)*3.5,math.sin(ang)*3.5)
            a.box('fountain_basin_rim',p['stone'],(*pos,.48),(.65,.47,.8),ang+math.pi/2)
        a.cylinder('fountain_water',material('Fountain water',(.12,.45,.46),.2),(0,0,.45),3.24,.05,48)
        a.cylinder('fountain_pedestal',p['trim'],(0,0,1.05),.62,1.5,16,.36)
        a.cylinder('fountain_upper_bowl',p['stone'],(0,0,1.90),1.45,.23,24,1.52)
        a.cylinder('fountain_finial',p['trim'],(0,0,2.18),.22,.48,12)
    bench_positions=[(-hw*.48,hh-2.2,0),(hw*.48,hh-2.2,0),(-hw*.50,-hh+2.2,0),(hw*.50,-hh+2.2,0)]
    for X,Y,ang in bench_positions:
        a.box('plaza_bench_seat',p['woodlight'],(X,Y,.5),(2.6,.5,.13),ang)
        for s in [-1,1]:
            xx=X+math.cos(ang)*s*.91;yy=Y+math.sin(ang)*s*.91
            a.box('plaza_bench_legs',p['metal'],(xx,yy,.23),(.14,.32,.46),ang)
    palm_positions=[]
    if plaza['id']=='PORTO_PLAZA':
        palm_positions=[(-hw+7,-hh+5),(hw-7,-hh+5),(-hw+7,hh-5),(hw-17,hh-7)]
        for X,Y in palm_positions:
            a.cylinder('palm_planter_stone',p['stone'],(X,Y,.30),1.30,.60,16)
            a.cylinder('palm_planter_soil',p['wooddark'],(X,Y,.615),1.17,.05,16)
        # Compact market stalls frame the west side and keep a broad opening
        # through the center for the west avenue and cathedral approach.
        for stall,(X,Y) in enumerate([(-hw+3.9,-8.3),(-hw+3.9,8.3),(-9,hh-3.7),(9,hh-3.7)]):
            for sx in [-1,1]:
                for sy in [-1,1]:a.box('market_canopy_posts',p['wooddark'],(X+sx*1.72,Y+sy*.98,1.34),(.095,.095,2.68))
            for j in range(8):
                x0=X-1.95+j*.4875;x1=x0+.4875
                mat=p['redfabric'] if (j+stall)%2 else p['fabric']
                a.mesh('striped_market_canopies',mat,[(x0,Y-1.25,2.64),(x1,Y-1.25,2.64),(x1,Y,2.88),(x0,Y,2.88),(x0,Y+1.25,2.64),(x1,Y+1.25,2.64)],[(0,1,2,3),(3,2,5,4)])
                a.box('market_canvas_valance',mat,((x0+x1)/2,Y-1.25,2.53),(.4875,.03,.22))
            a.box('market_counter',p['woodlight'],(X,Y,.95),(3.5,.80,.15))
            for sx in [-1,1]:a.box('market_counter_legs',p['wooddark'],(X+sx*1.45,Y,.43),(.12,.48,.86))
            for j in range(5):
                a.box('market_display_trays',p['wood'],(X-1.3+j*.63,Y,1.09),(.54,.65,.13))
                for k in range(4):a.cylinder('market_ceramic_goods',p['terracotta'],(X-1.48+j*.63+(k%2)*.22,Y-.16+(k//2)*.26,1.30),.105,.28,8,.085)
    record=a.finish(rx*2,ry*2,0,(0,-ry,0));_tag(record)
    if palm_positions:
        from vegetation import _palm_proto,_palette,_instantiate
        palmpalette=_palette();prototypes=[_palm_proto(i,palmpalette) for i in [0,2]]
        for i,(X,Y) in enumerate(palm_positions):
            _instantiate(prototypes[i%2],plaza['id']+'_PlanterPalm_'+str(i+1),(cx+X,cy+Y,z+.65),.66,i*.81,col,'REG_MAIN')
    return {'id':plaza['id'],'center':[cx,cy,z],'shape':'rounded_rectangle','full_dimensions':[hw*2,hh*2],'corner_radius':corner}


def _boardwalk(name,points,width=2.8,level=3.2,rails=True,gaps=None,shore=False):
    """Mesh plank walkway from WORLD XY or XYZ points, with real bearing piles."""
    if len(points[0])==2:
        path=[(p[0],p[1],level) for p in _sample_poly(points,.33)]
    else:path=_sample_poly(points,.33)
    if shore:
        path=[(X,Y,max(level,_support(X,Y)+.08)) for X,Y,_ in path]
        dense=[]
        for aa,bb in zip(path,path[1:]):
            n=max(1,math.ceil(abs(bb[2]-aa[2])/.25))
            for j in range(n):
                t=j/n;dense.append(tuple(aa[k]*(1-t)+bb[k]*t for k in range(3)))
        path=dense+[path[-1]]
    a=A.Assembly(name,0,0,0);p=A.palette(0);gaps=gaps or []
    support_dist=0;rail_dist=0
    for i,(pa,pb) in enumerate(zip(path,path[1:])):
        dx,dy=pb[0]-pa[0],pb[1]-pa[1];dist=math.hypot(dx,dy)
        if dist<.001:continue
        nx,ny=-dy/dist,dx/dist;cx,cy,cz=(pa[0]+pb[0])/2,(pa[1]+pb[1])/2,(pa[2]+pb[2])/2
        a.box('walkable_deck_planks',p['woodlight'] if i%5==0 else p['wood'],(cx,cy,cz-.09),(width,dist+.01,.18),math.atan2(dy,dx)-math.pi/2)
        support_dist+=dist;rail_dist+=dist
        if support_dist>=6.5 or i==0:
            support_dist=0
            for sign in [-1,1]:
                X,Y=cx+nx*sign*(width/2-.13),cy+ny*sign*(width/2-.13)
                bottom=min(-1.5,_support(X,Y)-.7)
                a.cylinder('bearing_piles',p['wooddark'],(X,Y,(bottom+cz-.18)/2),.15,cz-.18-bottom,10)
            a.beam('cross_bearers',p['wooddark'],(cx-nx*width/2,cy-ny*width/2,cz-.28),(cx+nx*width/2,cy+ny*width/2,cz-.28),.24,sides=4)
        clear=all(math.dist((cx,cy),g[:2])>(g[2] if len(g)>2 else 2.65) for g in gaps)
        if rails and clear and (rail_dist>2.0 or i==0):
            rail_dist=0
            for sign in [-1,1]:
                X,Y=cx+nx*sign*(width/2-.04),cy+ny*sign*(width/2-.04)
                a.box('railing_posts',p['wooddark'],(X,Y,cz+.52),(.10,.10,1.04))
        if rails and clear:
            for sign in [-1,1]:
                for hh in [.53,1.03]:
                    a.beam('railing_handrails',p['woodlight'],(pa[0]+nx*sign*(width/2-.04),pa[1]+ny*sign*(width/2-.04),pa[2]+hh),(pb[0]+nx*sign*(width/2-.04),pb[1]+ny*sign*(width/2-.04),pb[2]+hh),.075,sides=4)
    # Longitudinal load-bearing beams are full profile between sampled anchors.
    for pa,pb in zip(path[::12],path[12::12]):
        dx,dy=pb[0]-pa[0],pb[1]-pa[1];dist=math.hypot(dx,dy) or 1;nx,ny=-dy/dist,dx/dist
        for sign in [-1,1]:a.beam('longitudinal_joists',p['wooddark'],(pa[0]+nx*sign*(width/2-.25),pa[1]+ny*sign*(width/2-.25),pa[2]-.30),(pb[0]+nx*sign*(width/2-.25),pb[1]+ny*sign*(width/2-.25),pb[2]-.30),.24,sides=4)
    rec=a.finish(1,1,level,path[0]);_tag(rec)
    return {'id':name,'points':[[*q] for q in path[::9]]+[list(path[-1])],'width':width,'level':level}


def _station():
    # Main line is at 18m. Platform and ramp are one continuous supported route.
    q=xy((372,750));prev=xy((440,724));dx,dy=q[0]-prev[0],q[1]-prev[1];ll=math.hypot(dx,dy);tx,ty=dx/ll,dy/ll;nx,ny=-ty,tx
    center=(q[0]-tx*22+nx*7.5,q[1]-ty*22+ny*7.5);z=18.65
    a=A.Assembly('Porto_Sol_station',center[0],center[1],0);p=A.palette(1)
    angle=math.atan2(ty,tx)
    a.box('walkable_platform',p['stone'],(0,0,z-.28),(48,5.0,.56),angle)
    for t in [-20,-10,0,10,20]:
        X,Y=tx*t,ty*t;terrainz=_support(center[0]+X,center[1]+Y)
        a.box('platform_piers',p['stone'],(X,Y,(terrainz+z-.56)/2),(1.1,1.1,z-.56-terrainz))
    for t in [-16,0,16]:
        X,Y=tx*t,ty*t
        a.box('platform_canopy_columns',p['trim'],(X,Y,z+1.65),(.23,.23,3.3))
    # Lightweight weather canopy, roof plane and valence supported by columns.
    a.box('station_shelter_roof',p['roof'],(0,0,z+3.42),(38,4.5,.25),angle)
    a.box('station_timetable_panel',p['shutter'],(tx*18,ty*18,z+1.25),(.12,1.25,1.8),angle)
    rec=a.finish(50,7,z,(0,0,z));_tag(rec,'REG_MAIN')
    for ob in rec['objects']:
        if ob.get('component_role')=='walkable_platform':ob['walkable']=True
    # Switchback switch is a broad landing; incline run follows a side avenue.
    platform_entry=(center[0]-tx*22,center[1]-ty*22,z)
    landing=(platform_entry[0]+nx*17,platform_entry[1]+ny*17,z)
    endxy=(landing[0]-tx*46,landing[1]-ty*46)
    ground=max(.2,_support(*endxy))+.10
    ramp=_boardwalk('Station access ramp',[platform_entry,landing,(*endxy,ground)],4.0,rails=True)
    return [{'id':'Porto_Sol_station','center':[center[0],center[1],z]},ramp]


def build_villages():
    """Stage 6: complete reference-traced villas, two church landmarks and lanes."""
    bpy.context.view_layer.update();_SUPPORT_CACHE.clear()
    result=[_plaza(p) for p in PLAZAS]
    lane_defs={
      'Porto waterfront loop':[[135,818],[184,788],[252,801],[321,795],[391,809],[452,815],[491,807],[533,771]],
      'Porto west avenue':[[139,755],[169,714],[210,683],[248,696],[290,696],[340,701],[390,751],[393,800]],
      'Porto cathedral avenue':[[227,753],[270,733],[311,704],[343,673],[369,657],[379,628],[387,586],[405,552]],
      'Porto hillside lane':[[221,804],[245,776],[298,752],[344,748],[401,717],[451,704],[505,679],[554,646],[601,625]],
      'Porto ridge lane':[[322,574],[355,556],[405,536],[456,556],[510,565],[548,594],[574,620]],
      'Porto harbor link':[[321,795],[351,816],[384,811]],
      'San Aurelio village lane':[[1076,186],[1103,207],[1145,231],[1190,241],[1224,245],[1240,228],[1215,211],[1196,209]],
      'San Aurelio harbor lane':[[1092,232],[1130,260],[1171,279],[1191,300],[1191,330]],
      'San Aurelio upper lane':[[1097,154],[1129,176],[1164,190],[1190,204]],
      'Coral Key promenade':[[1019,686],[1048,707],[1083,744],[1107,788],[1147,827],[1129,868],[1080,910],[1023,895],[989,854],[1005,782]],
      'Emerald hillside walk':[[568,60],[603,78],[645,78],[682,65],[700,103],[696,123]],
      'Emerald coast path':[[591,187],[559,204],[524,217],[506,226]],
    }
    lanes=[]
    for name,pts in lane_defs.items():
        rec=_terrain_path(name,pts,4.3 if name.startswith('Porto') else 3.25)
        lanes.append([q[:2] for q in rec['points']]);result.append(rec)
    hero_scales={0:1.55,1:1.5,2:1.35,3:1.5,4:1.45,5:1.4,6:1.5,7:1.4,8:1.5,9:1.4,10:1.35,11:1.5,12:1.3,13:1.4,14:1.15,15:1.2,16:1.25,17:1.05}
    for i,(px,py,angle,variant) in enumerate(VILLAS):
        X,Y=xy((px,py));z=_support(X,Y);region=nearest_island(X,Y)['id']
        kind='cottage' if i>=36 or (i>=18 and region=='REG_MAIN') else 'villa'
        building_scale=hero_scales.get(i,1.2 if 26<=i<=35 else 1.0)
        rec=A.house(f'VILLA_{i+1:03d}',X,Y,z,angle,kind,variant,building_scale)
        _foundation(rec,z);metadata=_tag(rec,region);metadata['reference_pixel']=[px,py];metadata['scale']=building_scale;result.append(metadata)
        ep=rec['entrance'];front=(math.sin(angle),-math.cos(angle));approach=(ep[0]+front[0]*3,ep[1]+front[1]*3)
        candidates=[path for path in lanes if min(math.dist(p,(X,Y)) for p in path)<150]
        if candidates:
            target=_nearest(approach,candidates)
            pts=[ep[:2],approach]
            # A path must not cut across its own house when the nearest lane is behind.
            if (target[0]-approach[0])*front[0]+(target[1]-approach[1])*front[1]<-2:
                side=(math.cos(angle),math.sin(angle));sgn=1 if (target[0]-X)*side[0]+(target[1]-Y)*side[1]>0 else -1
                pts.append((approach[0]+side[0]*sgn*10,approach[1]+side[1]*sgn*10))
            pts.append(target)
            result.append(_terrain_path(f'Villa_{i+1:03d}_approach',pts,2.1,pixels=False,start_z=ep[2]))
    # Complementary narrow frontages occupy the reference's market/harbor parcels,
    # without moving existing buildings or introducing a new street network.
    service_frontages=[('Porto_Grocer',[225,666],1.10,0,1.08),('Porto_Market_Hall',[268,663],0,1,1.12),('Porto_Harbor_Inn',[341,786],0,3,1.16),('Porto_Marine_Workshop',[433,835],math.pi,4,1.10)]
    for name,point,angle,variant,scale in service_frontages:
        X,Y=xy(point);cs,sn=math.cos(angle),math.sin(angle)
        fw=(7.6+(variant%3)*.65)*scale;fd=(10.2+(variant%2)*1.2)*scale
        support_samples=[_support(X+u*cs-v*sn,Y+u*sn+v*cs) for u in [-fw/2,0,fw/2] for v in [-fd/2,0,fd/2]]
        z=max(support_samples)-.06;rec=A.house(name,X,Y,z,angle,'shop',variant,scale)
        _foundation(rec,z);metadata=_tag(rec,'REG_MAIN');metadata['reference_pixel']=point;metadata['scale']=scale;metadata['use']='harbor or village service';result.append(metadata)
        ep=rec['entrance'];front=(math.sin(angle),-math.cos(angle));approach=(ep[0]+front[0]*2.4,ep[1]+front[1]*2.4)
        result.append(_terrain_path(name+'_public_approach',[ep[:2],approach,_nearest(approach,lanes)],2.2,pixels=False,start_z=ep[2]))
    for name,point,angle,scale in [('Porto_Sol_Parish',[369,657],-.08,.90),('San_Aurelio_Parish',[1196,209],-.15,.88)]:
        X,Y=xy(point);z=_support(X,Y);rec=A.church(name,X,Y,z,angle,scale);_foundation(rec,z);result.append(_tag(rec,nearest_island(X,Y)['id']))
        ep=rec['entrance'];result.append(_terrain_path(name+'_approach',[ep[:2],_nearest(ep,lanes)],3.1,pixels=False))
    result.extend(_station())
    return result


_STILT_SPINES={
 'STILT_NORTHWEST':[[[492,134],[466,129],[434,122],[403,132],[391,153],[413,164]],[[434,122],[425,97],[415,79]]],
 'STILT_NORTH':[[[690,82],[719,70],[752,62],[785,67],[817,82],[854,90],[875,89]]],
 'STILT_WEST':[[[243,261],[213,272],[189,287],[200,305],[237,316],[275,307],[296,289]],[[296,289],[304,267],[312,250]]],
 'STILT_LAGOON':[[[1039,500],[1000,482],[960,469],[907,462]],[[907,462],[903,435],[908,416],[888,403],[856,403],[831,423],[809,444],[776,460],[763,479],[791,490],[836,487],[871,500]],[[903,435],[942,416],[968,415]]],
 'STILT_CORAL':[[[1166,811],[1207,814],[1246,819],[1291,808],[1322,798]],[[1246,819],[1272,779],[1283,763]],[[1291,808],[1305,843],[1297,879],[1269,922],[1232,951]]],
 'STILT_CORAL_NORTH':[[[1093,701],[1132,699],[1161,681],[1202,684],[1249,690]],[[1132,699],[1123,667],[1115,644]],[[1093,701],[1077,666],[1057,640]]],
}


def build_stilts():
    """Stage 7: six shore-connected branch/crescent neighborhoods, 46 houses."""
    result=[]
    for district in STILT_DISTRICTS:
        name=district['id'];spines=[catmull([xy(p) for p in pts],2) for pts in _STILT_SPINES[name]]
        branches=[];gaps=[]
        for i,point in enumerate(district['houses']):
            X,Y=xy(point);target=_nearest((X,Y),spines)
            dx,dy=target[0]-X,target[1]-Y;ang=math.atan2(dx,-dy)
            rec=A.house(f'{name}_HOUSE_{i+1:02d}',X,Y,0,ang,'stilt',i%5)
            result.append(_tag(rec,name));ep=rec['entrance']
            target_z=max(3.2,_support(*target)+.08)
            branches.append((f'{name}_BRANCH_{i+1:02d}',[tuple(ep),(*target,target_z)]));gaps.append(target)
        # Connect secondary spines with intentional open walking intersections.
        for s in spines[1:]:gaps.extend([s[0],s[-1]])
        if name in ('STILT_LAGOON','STILT_WEST'):
            hx,hy=xy(district['hub']);gaps.append((hx,hy,10 if name=='STILT_LAGOON' else 5))
        for j,path in enumerate(spines):result.append(_boardwalk(f'{name}_SPINE_{j+1}',path,3.2 if name=='STILT_LAGOON' else 2.7,3.2,True,gaps,shore=True))
        for b,points in branches:result.append(_boardwalk(b,points,2.3,3.2,False))
        shore=xy(district['shore']);inland=nearest_island(*shore);center=xy(inland['center']);dx,dy=center[0]-shore[0],center[1]-shore[1];length=math.hypot(dx,dy) or 1
        inland_point=(shore[0]+dx/length*13,shore[1]+dy/length*13)
        result.append(_terrain_path(name+'_shore_path',[inland_point,shore],2.8,pixels=False))
        if name=='STILT_LAGOON':
            hx,hy=xy(district['hub']);rec=A.pavilion('Lagoon_Circle_Pavilion',hx,hy,0,8.4);result.append(_tag(rec,name))
        elif name=='STILT_WEST':
            hx,hy=xy(district['hub']);rec=A.pavilion('Palm_Crescent_Shelter',hx,hy,0,4);result.append(_tag(rec,name))
    return result


def build_docks():
    """Stage 9: reference piers with physical decks, piles, bollards and cargo."""
    result=[]
    for i,dock in enumerate(DOCKS):
        points=[xy(p) for p in dock['points']]
        if dock['id']!='DOCK_PORTO_CROSS' and _support(*points[0])<1.8:
            # Keep the traced pier intact, but close a short water gap where the
            # analytic shoreline differs from the image's dock-root pixel.
            shore_island=nearest_island(*points[0]);center=xy(shore_island['center']);dx,dy=center[0]-points[0][0],center[1]-points[0][1];dist=math.hypot(dx,dy) or 1
            for step in range(1,math.ceil(dist)+1):
                candidate=(points[0][0]+dx/dist*step,points[0][1]+dy/dist*step)
                if _support(*candidate)>=2.4:
                    result.append(_boardwalk(dock['id']+'_shore_connection',[candidate,points[0]],min(3.3,dock['width']),2.4,False,shore=True))
                    break
        result.append(_boardwalk(dock['id'],points,dock['width'],2.4,False,shore=True))
        # Clear edge apron is deliberately left for boat access.
        pa,pb=points[-2:];ang=math.atan2(pb[1]-pa[1],pb[0]-pa[0]);tx,ty=math.cos(ang),math.sin(ang);nx,ny=-ty,tx
        # Mooring cleats align with the edges instead of blocking the route center.
        a=A.Assembly(dock['id']+'_mooring',0,0,0);p=A.palette(0)
        path=_sample_poly(points,7)
        for j,q in enumerate(path):
            if j%2:continue
            for sign in [-1,1]:
                X,Y=q[0]+nx*sign*(dock['width']/2-.12),q[1]+ny*sign*(dock['width']/2-.12)
                local_deck=max(2.4,_support(q[0],q[1])+.08)
                a.cylinder('mooring_posts',p['wooddark'],(X,Y,local_deck+.3),.13,.72,10)
                a.cylinder('mooring_caps',p['woodlight'],(X,Y,local_deck+.7),.17,.12,10)
        rec=a.finish(1,1,2.4,(*points[0],2.4));_tag(rec)
        end=points[-1]
        if dock['width']>=4:
            # End loading apron supports the crates and harbor light visibly.
            apron_a=(end[0]-tx*2,end[1]-ty*2);apron_b=(end[0]+tx*2,end[1]+ty*2)
            result.append(_boardwalk(dock['id']+'_loading_apron',[apron_a,apron_b],7,2.4,False))
            rec=A.dock_props(dock['id']+'_arrival_props',end[0],end[1],2.4,ang-math.pi/2);result.append(_tag(rec))
    return result
