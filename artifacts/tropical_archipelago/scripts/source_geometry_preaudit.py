"""Read-only geometry preaudit before the final source freeze."""
import bpy,sys,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from final_audit import geometry_audit,visible_names,dependency_audit,route_inventory,dynamic_audit
ROOT=HERE.parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
s=bpy.context.scene;s.frame_set(1);bpy.context.view_layer.update();names=visible_names(s.collection)
meshes=[o for o in s.objects if o.type=='MESH' and not o.hide_render and o.name in names]
unique,counts,issues,prototypes=geometry_audit(meshes)
report={'scope':'Read-only geometry preaudit before the final source freeze; camera saves may still occur. This is not the final source hash witness.',
        'source':bpy.data.filepath,'geometry':counts,'issue_meshes':issues,'dependencies':dependency_audit(),'routes':route_inventory(s),'dynamic':dynamic_audit(s),
        'visible_mesh_objects':len(meshes),'unique_meshes':len(unique)}
(ROOT/'checkpoints'/'source_geometry_preaudit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('SOURCE_GEOMETRY_PREAUDIT',json.dumps({'geometry':counts,'issue_mesh_count':len(issues),'issue_examples':issues[:12],'missing_dependencies':report['dependencies']['missing'],'motion_pass':report['dynamic']['pass']}),flush=True)
