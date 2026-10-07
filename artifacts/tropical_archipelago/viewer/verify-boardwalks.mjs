import {chromium} from 'playwright';
import {readFile,writeFile} from 'node:fs/promises';
let records=JSON.parse(await readFile(new URL('../checkpoints/07_metadata.json',import.meta.url),'utf8')).filter(r=>r.id.includes('_SPINE_')),metadata='07_metadata.json';
try{const replacements=JSON.parse(await readFile(new URL('../checkpoints/refined_routes.json',import.meta.url),'utf8')),byId=new Map((Array.isArray(replacements)?replacements:replacements.routes).map(r=>[r.id,r]));const originalIds=new Set(records.map(r=>r.id));records=records.map(r=>byId.get(r.id)||r).concat([...byId.values()].filter(r=>!originalIds.has(r.id)));metadata+=' + refined_routes.json';}catch(error){if(error.code!=='ENOENT')throw error;}
const browser=await chromium.launch({headless:true,executablePath:process.env.ARCHIPELAGO_CHROMIUM||'C:/Users/limou/AppData/Local/ms-playwright/chromium-1237/chrome-win64/chrome.exe',args:['--enable-unsafe-webgpu','--ignore-gpu-blocklist','--use-angle=d3d11']});
const page=await browser.newPage({viewport:{width:1448,height:1086}});let results=[],sourceSha256=null;
try{
 await page.goto('http://127.0.0.1:4173/',{waitUntil:'networkidle'});await page.waitForFunction(()=>window.__archipelago?.diagnostic.ready,null,{timeout:180000});sourceSha256=await page.evaluate(()=>window.__archipelago.diagnostic.source);
 results=await page.evaluate(records=>{const api=window.__archipelago;return records.map(route=>{
   const points=route.points.map(p=>[p[0],p[2],-p[1]]),first=points[0],probe=api.navigationProbe(first[0],first[2],first[1]);
   if(probe.stand===null)return{id:route.id,status:'failed',reason:'Start has no usable support',first,probe};
   api.walkerPose([first[0],probe.stand+1.72,first[2]],0);let reached=1,travel=0,stuck=null;
   for(const target of points.slice(1)){
     let steps=0;
     while(steps++<250){const before=api.snapshot(),dx=target[0]-before.position[0],dz=target[2]-before.position[2],d=Math.hypot(dx,dz);if(d<.22){reached++;break;}
       api.turnWalker(Math.atan2(-dx,-dz));api.moveFor(['KeyW'],Math.min(.1,d/3.8));const after=api.snapshot(),moved=Math.hypot(after.position[0]-before.position[0],after.position[2]-before.position[2]);travel+=moved;if(moved<.005||after.swimming){stuck={target,position:after.position,foot:after.foot,swimming:after.swimming,probe:api.navigationProbe(after.position[0]+dx/d*.16,after.position[2]+dz/d*.16,after.foot)};break;}
     }if(stuck)break;
   }
   return{id:route.id,status:reached===points.length?'passed':'failed',reachedPoints:reached,totalPoints:points.length,travelMetres:travel,...stuck?{stuck}:{}};
 });},records);
}catch(e){results.push({status:'failed',error:String(e)});}
finally{await browser.close();await writeFile(new URL('./output/playwright/boardwalk-validation.json',import.meta.url),JSON.stringify({timestamp:new Date().toISOString(),sourceSha256,metadata,method:'Actual bounded first-person controller follows source-authored boardwalk spine samples; no teleport between waypoints',results},null,2));console.log(JSON.stringify(results,null,2));if(results.some(r=>r.status==='failed'))process.exitCode=1;}
