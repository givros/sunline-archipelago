"""Repeatable full-scene inspection cameras, kept inside the editable scene."""
import bpy,sys,math,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from core import *
from layout import xy
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
pass_id=args[0] if args else 'pass_01'
selected=set(args[1].split(',')) if len(args)>1 else None
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
bpy.context.scene.frame_set(1)
from settlements import _support
def pose(p,z):return (*xy(p),z)
views=[
 ('overview',(0,-900,1180),(0,0,0),965,40),
 ('plan',(0,0,1400),(0,0,0),1280,40),
 ('porto_village',pose([228,864],104),pose([305,680],10),None,43),
 ('church_approach',pose([376,692],_support(*xy([376,692]))+1.72),pose([373,657],21.5),None,20),
 ('lagoon_boardwalk',pose([849,487],8),pose([885,431],5.5),None,34),
 ('sunline_viaduct',pose([808,270],40),pose([820,204],18),None,36),
 ('working_harbor',pose([342,954],16),pose([401,879],3),None,36),
 ('aurelio_arrival',pose([1220,333],42),pose([1171,217],16),None,42),
 ('coral_overwater',pose([1392,897],18),pose([1295,801],4.5),None,40),
]
for name,loc,target,ortho,lens in views:
 if selected is not None and name not in selected:continue
 ob=bpy.data.objects.get('CAM_'+name)
 if not ob:ob=camera('CAM_'+name,loc,target,ortho,lens)
 ob.location=loc;ob.rotation_euler=(Vector(target)-Vector(loc)).to_track_quat('-Z','Y').to_euler()
 if ortho:ob.data.type='ORTHO';ob.data.ortho_scale=ortho
 else:ob.data.type='PERSP';ob.data.lens=lens
 render(ob,f'{pass_id}_{name}',1448 if name=='overview' else 1280,1086 if name=='overview' else 960,48)
 print('VIEW_COMPLETE',pass_id,name,flush=True)
bpy.context.scene.camera=bpy.data.objects.get('CAM_Reference_Overview');bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
