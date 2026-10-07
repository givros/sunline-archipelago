"""Final localized construction corrections from the second visual pass."""
import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout import ROOT
from refine_architecture import fix_parish_spires,fix_boardwalk_surface_ownership
from repair_zero_area import repair_zero_area
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.scene.frame_set(1)
fix_parish_spires()
fix_boardwalk_surface_ownership()
repair_zero_area()
bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
