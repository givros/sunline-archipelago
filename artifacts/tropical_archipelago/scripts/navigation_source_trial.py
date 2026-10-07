"""Unsaved CPU validation of final circulation fixes."""
import bpy,sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
import navigation_source_fixes as N
import refine_architecture as R
trial=ROOT/'comparisons/architecture_audit/navigation_trial'
(trial/'checkpoints').mkdir(parents=True,exist_ok=True)
for name in ['07_metadata.json','refined_routes.json']:
    shutil.copy2(ROOT/'checkpoints'/name,trial/'checkpoints'/name)
N.ROOT=trial;R.ROOT=trial
result=N.fix_palm_grade_joists()
print('TRIAL_SUCCESS',json.dumps(result),flush=True)
