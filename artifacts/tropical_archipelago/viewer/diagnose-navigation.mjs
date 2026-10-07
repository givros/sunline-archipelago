import ts from 'typescript';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
const out=new URL('./output/motion/',import.meta.url);await mkdir(out,{recursive:true});
await writeFile(new URL('navigation.mjs',out),ts.transpileModule(await readFile(new URL('./src/navigation.ts',import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText);
const{NavigationWorld}=await import(new URL('navigation.mjs',out));
const data=JSON.parse(await readFile(new URL('./public/assets/scene.json',import.meta.url),'utf8')),raw=await readFile(new URL('./public/assets/scene.bin',import.meta.url)),world=new NavigationWorld(data,raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength));
const result=JSON.parse(await readFile(new URL('./output/playwright/boardwalk-validation.json',import.meta.url),'utf8')),details=[];
for(const r of result.results.filter(r=>r.status==='failed')){
 const point=r.stuck?.position||r.first,foot=r.stuck?.foot||r.first[1];let[x,,z]=point;
 if(r.stuck){const dx=r.stuck.target[0]-x,dz=r.stuck.target[2]-z,d=Math.hypot(dx,dz);x+=dx/d*.16;z+=dz/d*.16;}
 const radius=.32*.82,diag=radius*.70710678,offsets=[[0,0],[radius,0],[-radius,0],[0,radius],[0,-radius],[diag,diag],[-diag,diag],[diag,-diag],[-diag,-diag]];
 const supports=offsets.map(([dx,dz])=>world.support(x+dx,z+dz,foot));const valid=supports.filter(h=>h!==null&&h>=foot-1.15).sort((a,b)=>a-b),median=valid[Math.floor(valid.length/2)];
 details.push({id:r.id,point:[x,z],foot,supports,median,blockers:world.blockingObjects(x,z,foot),medianBlockers:median===undefined?[]:world.blockingObjects(x,z,median)});
}
console.log(JSON.stringify(details,null,2));await writeFile(new URL('./output/playwright/navigation-diagnosis.json',import.meta.url),JSON.stringify(details,null,2));
