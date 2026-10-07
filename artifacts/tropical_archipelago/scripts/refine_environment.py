"""Reference-led water and framing corrections after the first complete pass."""
import sys,bpy,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from core import ROOT

def refine_environment():
    changes=[]
    for image in bpy.data.images:
        if 'ocean_bathymetry' in image.name:
            if image.packed_file:image.unpack(method='REMOVE')
            image.filepath=str(ROOT/'references/ocean_bathymetry.png')
            image.reload();image.pack()
            changes.append('Repacked brighter, softly graded granular coral bathymetry')
    for name in ['CAM_Reference_Overview','CAM_overview']:
        ob=bpy.data.objects.get(name)
        if ob:ob.data.ortho_scale=965
    changes.append('Widened reference framing by 2.5% to retain Northpoint treetops')
    horizon=bpy.data.objects.get('OCEAN_Horizon')
    if horizon:
        def linear(v):
            v/=255
            return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
        color=tuple(linear(v) for v in (24,114,153))+(1,)
        mat=horizon.data.materials[0];mat.diffuse_color=color
        mat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=color
    world=bpy.context.scene.world
    nodes=world.node_tree.nodes;links=world.node_tree.links
    background=nodes.get('Background');output=nodes.get('World Output')
    visible=nodes.new('ShaderNodeBackground');visible.name='Clear tropical sky'
    visible.inputs['Color'].default_value=(.10,.42,.82,1);visible.inputs['Strength'].default_value=.85
    ray=nodes.new('ShaderNodeLightPath');mix=nodes.new('ShaderNodeMixShader');maximum=nodes.new('ShaderNodeMath');maximum.operation='MAXIMUM'
    links.new(ray.outputs['Is Camera Ray'],maximum.inputs[0]);links.new(ray.outputs['Is Glossy Ray'],maximum.inputs[1]);links.new(maximum.outputs[0],mix.inputs[0]);links.new(background.outputs[0],mix.inputs[1]);links.new(visible.outputs[0],mix.inputs[2]);links.new(mix.outputs[0],output.inputs[0])
    changes.append('Replaced the flat gray camera background with a clear maritime blue sky; retained physical ambient lighting')
    (ROOT/'checkpoints/environment_refinements.json').write_text(json.dumps(changes,indent=2))
    return changes

if __name__=='__main__':
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
    refine_environment()
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'),compress=False)
