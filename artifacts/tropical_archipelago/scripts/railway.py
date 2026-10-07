import math,bisect,bpy,json
import numpy as np
from mathutils import Vector
from core import *
from layout import *
import terrain
def metrics(points):
 a=[0.]
 for p,q in zip(points,points[1:]):a.append(a[-1]+math.dist(p,q))
 return a
def sample(points,dist,offset=0):
 arc=metrics(points);dist=max(0,min(arc[-1]-.0001,dist));i=max(0,min(len(points)-2,bisect.bisect_right(arc,dist)-1));t=(dist-arc[i])/(arc[i+1]-arc[i]);p=Vector(points[i]).lerp(Vector(points[i+1]),t);v=Vector(points[i+1])-Vector(points[i]);v.normalize();p+=Vector((-v.y,v.x,0))*offset;return p,math.atan2(v.y,v.x)
def ribbon(name,points,width,zoff,thickness,mat,col,offset=0):
 vs=[]
 for i,p in enumerate(points):
  v=Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)]);v.z=0;v.normalize();n=Vector((-v.y,v.x,0));p=Vector(p)+n*offset
  for z in [zoff-thickness,zoff]:
   for side in [-1,1]:vs.append(tuple(p+n*width*.5*side+Vector((0,0,z))))
 fs=[]
 for i in range(len(points)-1):
  a=i*4;b=a+4;fs.extend([(a+2,b+2,b+3,a+3),(a,b,b+2,a+2),(a+1,a+3,b+3,b+1),(a+1,b+1,b,a)])
 fs.extend([(0,2,3,1),(len(vs)-4,len(vs)-3,len(vs)-1,len(vs)-2)])
 return mesh(name,vs,fs,mat,col)
def build_tracks():
 col=collection('04 • Continuous railway');gravel=material('Railway basalt ballast',(.15,.17,.16),.95);steel=material('Rail polished steel',(.36,.42,.44),.28,.8);wood=material('Creosote sleepers',(.16,.12,.075),.8);stone=material('Viaduct limestone deck',(.52,.53,.46),.82);handrail=material('Dark bronze safety rails',(.16,.2,.19),.38,.55)
 for route in RAILS:
  pts=route['points'];name=route['id'];length=metrics(pts)[-1]
  slab=ribbon(name+'_StructuralDeck',pts,11.8,-.7,1.15,stone,col);slab['walkable']=True;slab['asset_role']='rail_deck'
  ballast=ribbon(name+'_Ballast',pts,7.7,-.35,.35,gravel,col);ballast['walkable']=True
  for track in [-2.1,2.1]:
   for railoff in [-.7175,.7175]:
    off=track+railoff
    ribbon(name+'_RailFoot',pts,.15,-.135,.03,steel,col,off)
    ribbon(name+'_RailWeb',pts,.045,-.045,.095,steel,col,off)
    ribbon(name+'_RailHead',pts,.072,0,.052,steel,col,off)
   s=0;idx=0
   while s<length:
    p,a=sample(pts,s,track);box(f'{name}_Sleeper_{track}_{idx}',(p.x,p.y,p.z-.255),(.23,2.65,.17),wood,col,a);idx+=1;s+=.8
  # Continuous public walkway, structural stone edge and full railings.
  for side in [-1,1]:
   walk=ribbon(name+'_Walkway',pts,1.5,-.22,.32,stone,col,side*4.85);walk['walkable']=True
   for dz in [.32,.92]:ribbon(name+'_Handrail',pts,.075,dz,.075,handrail,col,side*5.72)
   s=0;idx=0
   while s<length:
    p,a=sample(pts,s,side*5.72);cylinder(f'{name}_RailingPost_{side}_{idx}',(p.x,p.y,p.z-.3),(p.x,p.y,p.z+1.0),.046,handrail,col,8);idx+=1;s+=3.8
  if route['id']!='RAIL_SPUR':
   for d in ([0,length] if route['id']=='RAIL_MAIN' else [length]):
    for off in [-2.1,2.1]:
     p,a=sample(pts,d,off);p.z+=.55;box(name+'_BufferStop',p,(.35,2.4,.25),steel,col,a)
     for s in [-1,1]:
      n=Vector((-math.sin(a),math.cos(a),0));beam(name+'_BufferBrace',p+n*s*.8+Vector((-.7,0,-.5)),p+n*s*.8,.12,steel,col)
 return {'routes':[{**r,'length':metrics(r['points'])[-1]} for r in RAILS]}
def arch_span(name,p0,p1,width,mat,col):
 v=Vector(p1)-Vector(p0);L=v.length;v.normalize();n=Vector((-v.y,v.x,0));vs=[];segments=22
 for j in range(segments+1):
  t=j/segments;p=Vector(p0).lerp(Vector(p1),t)
  underside=3.2+12.7*math.sin(math.pi*t)**.64
  for side in [-1,1]:
   for z in [underside,17.24]:vs.append((p.x+n.x*width*.5*side,p.y+n.y*width*.5*side,z))
 fs=[]
 for j in range(segments):
  a=j*4;b=a+4;fs.extend([(a,a+1,b+1,b),(a+2,b+2,b+3,a+3),(a,b,b+2,a+2),(a+1,a+3,b+3,b+1)])
 return mesh(name,vs,fs,mat,col)
def build_bridges():
 col=collection('05 • Arched viaducts and causeways');stone=material('Viaduct limestone ashlar',(.56,.56,.48),.9);pale=material('Arch dressed voussoirs',(.64,.62,.53),.86);wet=material('Tidal stone waterline',(.23,.31,.27),.91)
 spans=0
 for route in RAILS:
  pts=route['points'];arc=metrics(pts);length=arc[-1];n=int(math.ceil(length/32));step=length/n
  for k in range(n+1):
   p,a=sample(pts,k*step);h=terrain.at(p.x,p.y)
   if h<15:
    base=max(-2.5,h-.35);height=17.3-base
    ob=box(f'{route["id"]}_Pier_{k}',(p.x,p.y,base+height*.5),(2.9,11.4,height),stone,col,a);ob['collider']=True
    box(f'{route["id"]}_PierFoot_{k}',(p.x,p.y,base+.65),(4.1,12.5,1.3),wet if base<0 else stone,col,a)
    box(f'{route["id"]}_PierCap_{k}',(p.x,p.y,16.05),(3.7,12.0,1),pale,col,a)
  for k in range(n):
   a,_=sample(pts,k*step);b,_=sample(pts,(k+1)*step);p=(a+b)*.5
   if terrain.at(p.x,p.y)<8 and route['id']=='RAIL_MAIN' and pixel(p)[1]<285:
    arch_span(f'{route["id"]}_Arch_{k}',a,b,10.8,stone,col);spans+=1
    # Dressed voussoir edges with actual segmented geometry on both arch faces.
    v=b-a;v.z=0;v.normalize();normal=Vector((-v.y,v.x,0))
    for j in range(19):
     t=(j+.5)/19;q=a.lerp(b,t);z=3.2+12.7*math.sin(math.pi*t)**.64
     slope=12.7*.64*math.pi*math.cos(math.pi*t)*max(.001,math.sin(math.pi*t))**(-.36)/step
     for side in [-1,1]:
      u=q+normal*side*5.46;ob=box(f'{route["id"]}_ArchStone_{k}_{j}_{side}',(u.x,u.y,z+.34),(step/19*.92,.27,.66),pale,col,math.atan2(v.y,v.x));ob.rotation_euler.rotate_axis('Y',-math.atan(slope))
 # Northeast portal and arched tunnel lining; terminates inside mountain.
 pts=RAILS[-1]['points'];p,a=sample(pts,metrics(pts)[-1]-5);n=Vector((-math.sin(a),math.cos(a),0));forward=Vector((math.cos(a),math.sin(a),0));dark=material('Tunnel interior shade',(.023,.035,.034),.97)
 for j in range(22):
  t=(j+.5)/22*math.pi;loc=p+n*math.cos(t)*5.6+Vector((0,0,2+math.sin(t)*5.6));ob=box(f'Tunnel portal voussoir {j}',loc,(2.3,.85,1.05),pale,col,a);ob.rotation_euler.rotate_axis('X',t-math.pi/2)
 for side in [-1,1]:box('Tunnel portal pilaster',p+n*side*5.6+Vector((0,0,.9)),(2.6,1,5.8),stone,col,a)
 # Dark barrel structure provides a readable real opening, no flat front cover.
 for j in range(18):
  theta=(j+.5)/18*math.pi;loc=p+forward*9+n*math.cos(theta)*5.65+Vector((0,0,2+math.sin(theta)*5.65));ob=box('Tunnel barrel lining',loc,(22,1,.95),dark,col,a);ob.rotation_euler.rotate_axis('X',theta-math.pi/2)
 return {'arched_spans':spans,'support_spacing_max_m':step,'deck_width_m':11.8,'walkway_clear_width_m':1.5}
def build_trains():
 from vehicles import train_car
 route=RAILS[0];points=route['points'];arc=metrics(points)
 # Two opposite-side consists reproduce both conspicuous trains in the reference.
 targets=[xy((916,232)),xy((751,603))];car_counts=[5,9];result=[]
 for trainid,target in enumerate(targets):
  ix=min(range(len(points)),key=lambda i:math.dist(points[i][:2],target));head=arc[ix];offset=-2.1 if trainid==0 else 2.1
  for car in range(car_counts[trainid]):
   d=head-car*19;p,a=sample(points,d,offset);role='front' if car==0 else 'rear' if car==car_counts[trainid]-1 else 'middle';root,meta=train_car(f'TRAIN_CAR_{trainid}_{car}',p.x,p.y,p.z,a,role,0)
   root['route_id']=route['id'];root['distance_on_route']=d;root['track_offset']=offset;root['train_id']=f'SUNLINE_{trainid}';root['car_index']=car;root['speed']=7.5;result.append({'id':root.name,'route_id':route['id'],'distance':d,'track_offset':offset,'car_index':car,'length':19})
 return result
