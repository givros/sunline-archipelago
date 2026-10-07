"""Unsaved isolated test of exact-zero cleanup; no source file is written."""
import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from repair_zero_area import repair_zero_area
from final_audit import geometry_audit,visible_names
ROOT=HERE.parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
fresh='--refresh-targets' in sys.argv
trial_path=ROOT/'checkpoints'/('zero_area_fresh_scan_trial.json' if fresh else 'zero_area_repair_trial.json')
report=repair_zero_area(trial_path,refresh_targets=fresh)
names=visible_names(bpy.context.scene.collection)
_,counts,issues,_=geometry_audit([o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render and o.name in names])
report['after_geometry']=counts;report['remaining_issues']=issues
trial_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
print('ZERO_AREA_TRIAL',json.dumps(counts),flush=True)
