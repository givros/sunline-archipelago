import bpy,sys,json
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Tropical_Archipelago.blend'))
out=[]
for label,pos,foot in [('North',(-18.7771757816,379.95535725346),25.7583888538),('NorthNext',(-18.62,380.04),25.7583888538),('West',(-315.52463395,218.45744882),16.1354122162),('WestNext',(-315.6,218.32),16.1354122162)]:
    hits=[]
    for ob in bpy.data.objects:
        if ob.type!='MESH' or not ob.get('walkable'):continue
        inv=ob.matrix_world.inverted()
        for dx,dy in [(0,0),(.2624,0),(-.2624,0),(0,.2624),(0,-.2624),(.1855,.1855),(-.1855,-.1855)]:
            p=inv@Vector((pos[0]+dx,pos[1]+dy,foot+.501));ray=inv.to_3x3()@Vector((0,0,-1));hit,v,n,i=ob.ray_cast(p,ray)
            if hit and n.z>=.7071:
                z=(ob.matrix_world@v).z
                if z>foot-3:hits.append([ob.name,[dx,dy],z])
    out.append({'name':label,'point':pos,'foot':foot,'hits':hits})
print(json.dumps(out,indent=2));(ROOT/'comparisons/architecture_audit/navigation_all_support_probe.json').write_text(json.dumps(out,indent=2))
