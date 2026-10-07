"""Refresh final metadata references without opening or modifying Blender."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def sha256(path):
    result=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):result.update(block)
    return result.hexdigest()

def enrich_graph(graph):
    override_path=ROOT/'checkpoints'/'refined_routes.json';fix_path=ROOT/'checkpoints'/'navigation_source_fixes.json'
    graph['local_route_overrides']={'reference':'checkpoints/refined_routes.json','records':json.loads(override_path.read_text(encoding='utf-8')) if override_path.exists() else [],
                                    'precedence':'These final same-id route records replace earlier construction-stage routes.'}
    if fix_path.exists():graph['navigation_source_repairs']={'reference':'checkpoints/navigation_source_fixes.json','records':json.loads(fix_path.read_text(encoding='utf-8'))}
    graph['final_refinement_evidence']=[]
    for filename,scope in [('shore_approach_joins.json','Final land-to-boardwalk surface joins'),
                           ('palm_entry_gate_probe.json','Physical Palm Crescent entry gate validation'),
                           ('palm_grade_joists.json','Final Palm grade transition joist clearance repair'),
                           ('final_reef_refinement.json','Final ocean reef pattern and turquoise water correction')]:
        path=ROOT/'checkpoints'/filename
        if path.exists():graph['final_refinement_evidence'].append({'reference':'checkpoints/'+filename,'scope':scope,'sha256':sha256(path),'records':json.loads(path.read_text(encoding='utf-8'))})
    spec_path=ROOT/'scene_spec.json'
    if spec_path.exists():
        spec=json.loads(spec_path.read_text(encoding='utf-8'))
        graph['specification_refinement_references']=[{'reference':ref,'sha256':sha256(ROOT/ref)} for ref in spec.get('refinement_records',[]) if (ROOT/ref).is_file()]
        graph['specification_sha256']=sha256(spec_path)
    return graph

def refresh():
    path=ROOT/'region_graph.json';graph=json.loads(path.read_text(encoding='utf-8'));source_hash=sha256(ROOT/'Tropical_Archipelago.blend')
    if graph.get('source_sha256')!=source_hash:raise RuntimeError('Source changed: a fresh source audit is required before refreshing its graph metadata.')
    enrich_graph(graph);path.write_text(json.dumps(graph,indent=2),encoding='utf-8')
    report={'source_sha256':source_hash,'refined_routes':len(graph['local_route_overrides']['records']),
            'refinement_reference_hashes':len(graph['specification_refinement_references']),'source_unchanged':True}
    print('REGION_GRAPH_METADATA_REFRESH',json.dumps(report))
    return report

if __name__=='__main__':refresh()
