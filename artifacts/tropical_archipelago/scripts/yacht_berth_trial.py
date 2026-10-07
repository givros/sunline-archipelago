"""Unsaved trial of final yacht berth adjustment."""
import bpy,sys,math
from pathlib import Path
from mathutils import Vector
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from refine_marine import tighten_yacht_berth
from core import camera
ROOT=HERE.parent;bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
tighten_yacht_berth(persist=False,report_path=ROOT/'checkpoints'/'yacht_berth_precision_trial.json')
s=bpy.context.scene;o=bpy.data.objects['BOAT_06_yacht'];a=o.rotation_euler.z;f=Vector((math.cos(a),math.sin(a),0));n=Vector((-math.sin(a),math.cos(a),0));p=o.location
s.camera=camera('INSPECT_FINAL_YACHT',p+f*15-n*20+Vector((0,0,11)),p+Vector((0,0,1.1)),28)
s.render.engine='CYCLES';s.cycles.samples=20;s.cycles.use_denoising=True;s.render.resolution_percentage=100;s.render.resolution_x=1500;s.render.resolution_y=1100
s.render.filepath=str(ROOT/'renders'/'marine_validation'/'moored_yacht_final_berth.png');bpy.ops.render.render(write_still=True)
