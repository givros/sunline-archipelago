import {chromium} from 'playwright';
import {writeFile,readFile} from 'node:fs/promises';
import * as THREE from 'three/webgpu';
const browser=await chromium.launch({headless:true,executablePath:process.env.ARCHIPELAGO_CHROMIUM||'C:/Users/limou/AppData/Local/ms-playwright/chromium-1237/chrome-win64/chrome.exe',args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11']});
const context=await browser.newContext({viewport:{width:1448,height:1086}}),page=await context.newPage();const results=[];let sourceSha256=null;
try{
  await page.goto('http://127.0.0.1:4173/',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__archipelago?.diagnostic.ready,null,{timeout:180000});sourceSha256=await page.evaluate(()=>window.__archipelago.diagnostic.source);
  const coastal=await page.evaluate(()=>{
    const api=window.__archipelago,candidates=[];
    // Castaway Sand is the reference's central natural islet. Find a real low
    // beach by querying the exported source support triangles.
    for(let x=-77;x<5;x+=1.2)for(let z=-201;z<-132;z+=1.2){const top=api.navigationProbe(x,z,Infinity);if(top.support===null||top.support<.09||top.support>.75)continue;const p=api.navigationProbe(x,z,top.support);if(p.stand===null||p.blocked)continue;
      for(let j=0;j<16;j++){const angle=j*Math.PI/8,dx=Math.cos(angle),dz=Math.sin(angle),water=api.navigationProbe(x+dx*4,z+dz*4,Infinity);if(water.terrain===null&&water.support===null)candidates.push({x,z,foot:p.support,dx,dz});}}
    const attempts=[];
    for(const c of candidates.slice(0,80)){const yaw=Math.atan2(-c.dx,-c.dz);api.walkerPose([c.x,c.foot+1.72,c.z],yaw);const out=api.moveFor(['KeyW'],4),swim=api.snapshot();if(!swim.swimming)continue;api.moveFor(['KeyS'],6);const back=api.snapshot();attempts.push({coast:c,outDistance:out.distance,waterPosition:swim.position,waterEye:swim.eyeAboveSupport,returnPosition:back.position,returnedToLand:!back.swimming&&back.foot>.08});if(attempts.at(-1).returnedToLand)return{status:'passed',method:'Bounded actual controller updates over exported triangles, walk-to-swim and swim-to-land',...attempts.at(-1)};}
    return{status:'failed',candidates:candidates.length,attempts};
  });results.push({check:'coastal_swimming',...coastal});
  const data=JSON.parse(await readFile(new URL('./public/assets/scene.json',import.meta.url),'utf8')),raw=await readFile(new URL('./public/assets/scene.bin',import.meta.url));const binary=raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength);const basis=new THREE.Matrix4().makeRotationX(-Math.PI/2),walls=[];
  for(const obj of data.objects.filter(o=>o.properties.component_role==='wall_piers'&&o.properties.collider)){
    const g=data.geometries[obj.geometry],coords=new Float32Array(binary,g.position.offset,g.position.count*3),bounds=new THREE.Box3();for(let i=0;i<coords.length;i+=3)bounds.expandByPoint(new THREE.Vector3(coords[i],coords[i+1],coords[i+2]));const matrix=basis.clone().multiply(new THREE.Matrix4().fromArray(obj.matrix)),center=bounds.getCenter(new THREE.Vector3()).applyMatrix4(matrix);
    for(const side of[-1,1]){const local=bounds.getCenter(new THREE.Vector3());local.x=side===1?bounds.max.x:bounds.min.x;const edge=local.applyMatrix4(matrix),out=edge.clone().sub(center).setY(0).normalize();walls.push({id:obj.id,edge:edge.toArray(),outside:edge.clone().addScaledVector(out,1.4).toArray(),direction:out.multiplyScalar(-1).toArray()});}
  }
  const collision=await page.evaluate(walls=>{const api=window.__archipelago;for(const wall of walls){const[x,,z]=wall.outside,top=api.navigationProbe(x,z,Infinity);if(top.support===null)continue;const p=api.navigationProbe(x,z,top.support);if(p.stand===null||p.blocked)continue;const dx=wall.direction[0],dz=wall.direction[2],yaw=Math.atan2(-dx,-dz),inside=api.navigationProbe(wall.edge[0]+dx*.6,wall.edge[2]+dz*.6,p.support);if(!inside.blocked)continue;api.walkerPose([x,p.support+1.72,z],yaw);const moved=api.moveFor(['KeyW'],2),end=api.snapshot(),progress=(end.position[0]-x)*dx+(end.position[2]-z)*dz;return{status:progress<1.5&&progress>=0&&end.foot>0?'passed':'failed',wall:wall.id,attemptedDistanceMetres:7.6,actualProgressMetres:progress,actualTravel:moved.distance,solidProbe:true,finalPosition:end.position};}return{status:'failed',reason:'No verified wall approach found'};},walls);results.push({check:'solid_building_collision',...collision});
}catch(e){results.push({check:'execution',status:'failed',error:String(e)});process.exitCode=1;}
finally{await browser.close();await writeFile(new URL('./output/playwright/circulation-validation.json',import.meta.url),JSON.stringify({timestamp:new Date().toISOString(),sourceSha256,results},null,2));console.log(JSON.stringify(results,null,2));if(results.some(r=>r.status==='failed'))process.exitCode=1;}
