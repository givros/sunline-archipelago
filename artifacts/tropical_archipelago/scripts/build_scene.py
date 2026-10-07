import bpy,sys,json,math,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from core import *
from layout import *
ARGS=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
STAGE=int(ARGS[0]) if ARGS else 1
def get_overview():return bpy.data.objects.get('CAM_Reference_Overview') or camera('CAM_Reference_Overview',(0,-900,1180),(0,0,0),941.2)
def sea(textured=False):
 col=collection('02 • Tropical ocean');m=material('Ocean optical surface',(.022,.32,.39),.23,.18)
 if textured:
  n=m.node_tree.nodes;links=m.node_tree.links;tex=n.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(ROOT/'references/ocean_bathymetry.png'));tex.image.pack();links.new(tex.outputs['Color'],n.get('Principled BSDF').inputs['Base Color'])
  coord=n.new('ShaderNodeTexCoord');noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=920;noise.inputs['Detail'].default_value=2;noise.inputs['Roughness'].default_value=.65;links.new(coord.outputs['Generated'],noise.inputs[0]);bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.18;bump.inputs['Distance'].default_value=.055;links.new(noise.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs['Normal'],n.get('Principled BSDF').inputs['Normal'])
 ob=bpy.data.objects.get('OCEAN_Surface')
 if not ob:
  ob=mesh('OCEAN_Surface',[(-725,-725,0),(725,-725,0),(725,725,0),(-725,725,0)],[(0,1,2,3)],m,col);uv=ob.data.uv_layers.new()
  for loop in ob.data.loops:
   co=ob.data.vertices[loop.vertex_index].co;uv.data[loop.index].uv=((co.x+725)/1450,(co.y+725)/1450)
 ob['material_role']='ocean';return ob
def save_stage(stage,meta=None):
 if meta is not None:(ROOT/'checkpoints'/f'{stage:02d}_metadata.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 bpy.context.scene['construction_stage']=stage;bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'checkpoints'/f'{stage:02d}_scene.blend'),compress=False)
 render(get_overview(),f'checkpoint_{stage:02d}',1448,1086,24 if stage<10 else 40)
 print('CHECKPOINT_COMPLETE',stage,flush=True)
if STAGE==1:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False);light_scene();sea();col=collection('01 • Reference boundaries');m=material('Layout island reservation',(.34,.58,.28))
 for isle in ISLANDS:
  ob=mesh(isle['id']+'_BOUNDARY',[(*xy(p),.15) for p in isle['shore']],[tuple(range(len(isle['shore'])))],m,col)
 get_overview();write_spec();save_stage(1)
else:
 prev=ROOT/'checkpoints'/f'{STAGE-1:02d}_scene.blend';bpy.ops.wm.open_mainfile(filepath=str(prev));meta=None
 if STAGE==2:sea(True)
 if STAGE==3:
  col=bpy.data.collections.get('01 • Reference boundaries')
  if col:
   for ob in list(col.objects):bpy.data.objects.remove(ob,do_unlink=True)
   bpy.data.collections.remove(col)
  import terrain;terrain.build_islands()
 if STAGE==4:
  import railway;meta=railway.build_tracks()
 if STAGE==5:
  import railway;from rail_junctions import fix_junctions
  meta=railway.build_bridges();meta['junctions']=fix_junctions()
 if STAGE==6:
  import terrain
  for island in ISLANDS:
   old=bpy.data.objects.get(island['id'])
   if old:bpy.data.objects.remove(old,do_unlink=True)
  terrain.build_islands()
  import settlements;meta=settlements.build_villages()
 if STAGE==7:
  import settlements;meta=settlements.build_stilts()
 if STAGE==8:
  import railway;import train_motion
  cars=railway.build_trains();meta=train_motion.animate_trains();meta['source_cars']=cars
  (ROOT/'animation_manifest.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
 if STAGE==9:
  import settlements;from vehicles import boat
  meta={'docks':settlements.build_docks(),'boats':[]}
  for i,b in enumerate(BOATS):
   x,y=xy(b);root,record=boat(f'BOAT_{i:02d}_{b[3]}',x,y,0,b[2],b[3],i%4);meta['boats'].append(record)
   if i in [0,1,2,3,4,18]:
    foam=material('Thin sunlit boat wake',(.64,.83,.79),.55);col=collection('09 • Marine wakes')
    ca,sa=math.cos(b[2]),math.sin(b[2])
    for side in [-1,1]:
     for strand in range(3):
      vs=[];fs=[]
      for j in range(40):
       t=j/39;back=-record['length']*.5-.20-t*(25 if i in [0,1,2] else 15);off=side*(.8+t*(4.4+strand*.6)+math.sin(t*15+strand)*.3);width=(.09+.24*math.sin(math.pi*t))*(1-strand*.2)*(1-.75*t)
       for delta in [-width,width]:vs.append((x+back*ca-(off+delta)*sa,y+back*sa+(off+delta)*ca,.06+.004*strand))
       if j:fs.append((2*j-2,2*j-1,2*j+1,2*j))
      mesh(f'BOAT_{i:02d}_Wake_{side}_{strand}',vs,fs,foam,col)
 if STAGE==10:
  import vegetation;meta=vegetation.build_vegetation()
  ocean_background=material('Ocean horizon deep blue',(.0031,.1046,.2122),.23,.18)
  ob=mesh('OCEAN_Horizon',[(-20000,-20000,-.08),(20000,-20000,-.08),(20000,20000,-.08),(-20000,20000,-.08)],[(0,1,2,3)],ocean_background,collection('02 • Tropical ocean'))
  ob['material_role']='ocean';ob['ocean_backing']=True
 if STAGE==11:
  bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'),compress=False)
 save_stage(STAGE,meta)

