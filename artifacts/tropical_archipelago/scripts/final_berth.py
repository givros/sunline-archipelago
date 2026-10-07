import bpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout import ROOT
from refine_marine import tighten_yacht_berth
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.scene.frame_set(1)
tighten_yacht_berth()
bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
