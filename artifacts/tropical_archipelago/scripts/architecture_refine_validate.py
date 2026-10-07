import sys,bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from core import camera,render
from layout import xy
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'checkpoints/10_scene.blend'))
import refine_architecture as R
report=R.refine_architecture()
issues=[]
for rec in report['routes']:
 if '_SPINE_' not in rec['id']:continue
 line=R.LineString([p[:2] for p in rec['points']])
 for ob in bpy.data.objects:
  if ob.type!='EMPTY' or not ob.name.startswith('STILT_') or '_HOUSE_' not in ob.name:continue
  walls=[o for o in ob.children if o.get('component_role')=='wall_piers']
  if not walls:continue
  vs=[o.matrix_world@v.co for o in walls for v in o.data.vertices]
  poly=R.Polygon([(v.x,v.y) for v in vs]).convex_hull
  if line.distance(poly)<1.5:issues.append({'route':rec['id'],'house':ob.name,'clearance':line.distance(poly)})
report['wall_clearance_issues']=issues
report['unapplied_modifiers']=[o.name for o in bpy.data.objects if len(o.modifiers)]
(ROOT/'comparisons/architecture_audit/refine_validation.json').write_text(json.dumps(report,indent=2))
print('VALIDATION',json.dumps(issues),flush=True)
scene=bpy.context.scene;scene.cycles.samples=16;scene.render.resolution_percentage=100
for name,p,z,target,tz,lens in [('refined_church',[376,692],R.S._support(*xy([376,692]))+1.72,[373,657],20,22)]:
 cam=camera('AUDIT_'+name,(*xy(p),z),(*xy(target),tz),lens=lens)
 render(cam,name,1024,768,16)
print('REFINEMENT_ISOLATED_VALIDATED',flush=True)
