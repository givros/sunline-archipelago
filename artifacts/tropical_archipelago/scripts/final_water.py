"""Pack the reference-led coral scale correction into the final source."""
import bpy,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from layout import ROOT
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
for image in bpy.data.images:
    if 'ocean_bathymetry' in image.name:
        if image.packed_file:image.unpack(method='REMOVE')
        image.filepath=str(ROOT/'references/ocean_bathymetry.png')
        image.reload();image.pack()
bpy.context.scene['final_reef_refinement']='Independent 10/4/1.6m coral colonies, saturated turquoise shallows and restrained sand patches; coast and shelf extents unchanged.'
(ROOT/'checkpoints/final_reef_refinement.json').write_text(json.dumps({'change':bpy.context.scene['final_reef_refinement'],'reference':'references/primary_layout.png','texture':'references/ocean_bathymetry.png'},indent=2))
bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
