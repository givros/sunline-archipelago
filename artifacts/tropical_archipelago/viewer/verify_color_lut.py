import sys,json
from pathlib import Path
import numpy as np
base=Path(__file__).resolve().parent;sys.path.insert(0,str(base/'tools_py'));import PyOpenColorIO as ocio
config=ocio.Config.CreateFromFile('C:/Program Files/Blender Foundation/Blender 5.1/5.1/datafiles/colormanagement/config.ocio');pipe=ocio.LegacyViewingPipeline();pipe.setDisplayViewTransform(ocio.DisplayViewTransform(src='Linear Rec.709',display='sRGB',view='AgX'));pipe.setLooksOverride('AgX - Medium High Contrast');pipe.setLooksOverrideEnabled(True);cpu=pipe.getProcessor(config).getDefaultCPUProcessor()
rng=np.random.default_rng(27);log=rng.uniform(-12.5,7.5,(10000,3));ref=np.exp2(log).astype(np.float32);cpu.applyRGB(ref);ref=np.where(ref<=.04045,ref/12.92,((ref+.055)/1.055)**2.4)
lut=np.fromfile(base/'public/assets/agx-medium-high.bin',np.float32).reshape(65,65,65,4).astype(np.float16).astype(np.float32);coord=(log+12.5)/20*64;index=np.floor(coord).astype(int);factor=coord-index;pred=np.zeros_like(ref)
for b in [0,1]:
 for g in [0,1]:
  for r in [0,1]:
   weight=(factor[:,0]if r else 1-factor[:,0])*(factor[:,1]if g else 1-factor[:,1])*(factor[:,2]if b else 1-factor[:,2]);pred+=lut[index[:,2]+b,index[:,1]+g,index[:,0]+r,:3]*weight[:,None]
err=np.abs(ref-pred);report={'status':'passed'if float(np.max(err))<.015 else'failed','samples':10000,'deterministicSeed':27,'comparison':'Exact Blender OCIO CPU versus65-cube trilinear runtime simulation includingFloat16GPU storage','linearRGBError':{'maximum':float(np.max(err)),'p95':float(np.quantile(err,.95)),'mean':float(np.mean(err))},'sourceColorEncoding':'linear','LutOutputEncoding':'linear-sRGB','browserOutputEncoding':'sRGB exactlyonce','exposure':2**.1}
(base/'output/playwright/color-transform-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
