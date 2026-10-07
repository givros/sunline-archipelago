import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout import ROOT
from navigation_source_fixes import apply_navigation_source_fixes,fix_shore_approach_joins,fix_palm_entry_gate,fix_palm_grade_joists
from repair_zero_area import repair_zero_area
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.scene.frame_set(1)
apply_navigation_source_fixes()
fix_shore_approach_joins()
fix_palm_entry_gate()
fix_palm_grade_joists()
repair_zero_area(refresh_targets=True)
bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
