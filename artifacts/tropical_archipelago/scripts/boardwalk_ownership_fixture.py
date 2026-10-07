"""CPU-only proof that overlap removal preserves complete walking coverage."""
import bpy,sys,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import settlements as S
import refine_architecture as R
from shapely.geometry import Polygon
from shapely.ops import unary_union
OUT=ROOT/'comparisons/architecture_audit/fixture';(OUT/'checkpoints').mkdir(parents=True,exist_ok=True);R.ROOT=OUT
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
S._boardwalk('FIXTURE_SPINE_A',[(-12,0),(0,0),(9,8),(17,8)],3.2,rails=False)
S._boardwalk('FIXTURE_BRANCH_A',[(0,-12),(0,8)],2.7,rails=False)
S._boardwalk('FIXTURE_BRANCH_B',[(9,8),(15,1),(17,-6)],2.5,rails=False)
def surfaces():
 result=[]
 for ob in bpy.data.objects:
  if ob.type!='MESH' or ob.get('component_role')!='walkable_deck_planks':continue
  for face in ob.data.polygons:
   if face.normal.z>.9:
    p=[ob.matrix_world@ob.data.vertices[i].co for i in face.vertices];result.append(Polygon([(v.x,v.y) for v in p]))
 return result
before=surfaces();before_union=unary_union(before);report=R.fix_boardwalk_surface_ownership();after=surfaces();after_union=unary_union(after)
report.update(original_surface_area=before_union.area,remaining_surface_area=after_union.area,coverage_symmetric_difference=before_union.symmetric_difference(after_union).area,remaining_duplicate_top_area=sum(p.area for p in after)-after_union.area,collider_tags_preserved=all(o.get('collider') and o.get('walkable') for o in bpy.data.objects if o.get('component_role')=='walkable_deck_planks'))
(OUT/'coverage_proof.json').write_text(json.dumps(report,indent=2));print('COVERAGE_PROOF',json.dumps(report),flush=True)
assert report['coverage_symmetric_difference']<1e-4
assert abs(report['remaining_duplicate_top_area'])<1e-4
assert report['collider_tags_preserved']
