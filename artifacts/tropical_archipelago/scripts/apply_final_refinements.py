"""Apply inspected local corrections while preserving the constructed scene."""
import bpy,sys,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from layout import ROOT,write_spec
args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['all']
source=ROOT/'Tropical_Archipelago.blend'
bpy.ops.wm.open_mainfile(filepath=str(source));bpy.context.scene.frame_set(1)
if args[0] in ['marine','all'] and not bpy.context.scene.get('marine_refinement_v1'):
    from refine_marine import apply_refinements
    apply_refinements();bpy.context.scene['marine_refinement_v1']=True
if args[0] in ['architecture','all']:
    from refine_architecture import refine_architecture
    refine_architecture()
write_spec()
spec=json.loads((ROOT/'scene_spec.json').read_text())
spec['refinement_records']=['checkpoints/environment_refinements.json','checkpoints/architecture_refinements.json','checkpoints/refined_routes.json','marine_clearance_report.json']
(ROOT/'scene_spec.json').write_text(json.dumps(spec,indent=2))
bpy.context.view_layer.update();bpy.ops.wm.save_as_mainfile(filepath=str(source),compress=False)
