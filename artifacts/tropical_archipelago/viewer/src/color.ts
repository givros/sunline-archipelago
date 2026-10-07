import * as THREE from 'three/webgpu';
import {Fn,texture3D,log2,max,clamp} from 'three/tsl';

/** Blender's actual OCIO AgX Medium High Contrast display transform.
 * The stored LUT returns linear sRGB; Three performs the output encoding once.
 */
export async function installSourceColorTransform(renderer:THREE.WebGPURenderer){
  const response=await fetch('./assets/agx-medium-high.bin');if(!response.ok)throw new Error('The island color transform could not be loaded. Please reload.');
  const source=new Float32Array(await response.arrayBuffer()),half=new Uint16Array(source.length);for(let i=0;i<source.length;i++)half[i]=THREE.DataUtils.toHalfFloat(source[i]);
  const lut=new THREE.Data3DTexture(half,65,65,65);lut.format=THREE.RGBAFormat;lut.type=THREE.HalfFloatType;lut.minFilter=THREE.LinearFilter;lut.magFilter=THREE.LinearFilter;lut.unpackAlignment=1;lut.needsUpdate=true;
  const transform=Fn(([color,exposure]:any[])=>{const uv=clamp(log2(max(color.mul(exposure),Math.pow(2,-12.5))).add(12.5).div(20),0,1).mul(64/65).add(.5/65);return texture3D(lut,uv).rgb;});
  renderer.library.addToneMapping(transform,THREE.CustomToneMapping);renderer.toneMapping=THREE.CustomToneMapping;renderer.toneMappingExposure=Math.pow(2,.1);
  return lut;
}
