import sys,json,hashlib
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parent
sys.path.insert(0,str(base/'tools_py'))
import PyOpenColorIO as ocio
config_path=Path('C:/Program Files/Blender Foundation/Blender 5.1/5.1/datafiles/colormanagement/config.ocio')
config=ocio.Config.CreateFromFile(str(config_path))
view=ocio.DisplayViewTransform(src='Linear Rec.709',display='sRGB',view='AgX')
pipeline=ocio.LegacyViewingPipeline();pipeline.setDisplayViewTransform(view);pipeline.setLooksOverride('AgX - Medium High Contrast');pipeline.setLooksOverrideEnabled(True)
processor=pipeline.getProcessor(config).getDefaultCPUProcessor()
size=65;low=-12.5;high=7.5
axis=np.exp2(np.linspace(low,high,size)).astype(np.float32)
b,g,r=np.meshgrid(axis,axis,axis,indexing='ij');rgb=np.stack([r,g,b],axis=-1).reshape(-1,3).copy();processor.applyRGB(rgb)
linear=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4).astype(np.float32)
rgba=np.ones((len(rgb),4),np.float32);rgba[:,:3]=linear
out=base/'public/assets/agx-medium-high.bin';rgba.tofile(out)
metadata={'generator':'OpenColorIO '+ocio.__version__,'source':'Blender5.1 config.ocio','configuration_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'input':'Linear Rec.709','view':'AgX','look':'AgX - Medium High Contrast','display':'sRGB','storedOutput':'linear-sRGB; browser applies the sRGB encoding once','lutSize':size,'inputLog2Range':[low,high],'format':'RGBA Float32; R axis varies fastest','bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
(base/'color_transform.json').write_text(json.dumps(metadata,indent=2))
print(json.dumps(metadata,indent=2))
