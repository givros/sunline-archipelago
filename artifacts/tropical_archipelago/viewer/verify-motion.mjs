import * as THREE from 'three/webgpu';
import ts from 'typescript';
import {readFile,writeFile,mkdir} from 'node:fs/promises';
const output=new URL('./output/motion/',import.meta.url);await mkdir(output,{recursive:true});
const code=await readFile(new URL('./src/scene.ts',import.meta.url),'utf8');
await writeFile(new URL('scene.mjs',output),ts.transpileModule(code,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext}}).outputText);
const{RailwayAnimation}=await import(new URL('scene.mjs',output));
const data=JSON.parse(await readFile(new URL('./public/assets/scene.json',import.meta.url),'utf8'));
const witness=JSON.parse(await readFile(new URL('./output/playwright/train-source-samples.json',import.meta.url),'utf8'));
const roots=new Map(data.dynamic_roots.map(rec=>{const group=new THREE.Group();group.name=rec.id;group.matrix.fromArray(rec.matrix);group.matrix.decompose(group.position,group.quaternion,group.scale);return[rec.id,group];}));
const animation=new RailwayAnimation(data,roots),comparisons=[];
let maxPosition=0,maxYaw=0,maxScale=0;const errors=[];
for(const sample of witness.samples){animation.seek(sample.time);for(const pose of sample.cars){const g=roots.get(pose.id);if(!g){errors.push('Missing runtime root '+pose.id);continue;}const p=g.position.distanceTo(new THREE.Vector3(...pose.position));const yaw=Math.abs(Math.atan2(Math.sin(g.rotation.z-pose.yaw),Math.cos(g.rotation.z-pose.yaw)));const scale=g.scale.distanceTo(new THREE.Vector3(...pose.scale));maxPosition=Math.max(maxPosition,p);maxYaw=Math.max(maxYaw,yaw);maxScale=Math.max(maxScale,scale);comparisons.push({time:sample.time,id:pose.id,positionErrorMetres:p,yawErrorRadians:yaw,scaleError:scale});}}
const report={sourceFile:witness.source_file,sourceSha256:witness.source_sha256,runtimeSourceSha256:data.source_sha256,method:'Reopened Blender source evaluation including parent-local F-curves and live drawbar drivers, compared against the identical TypeScript RailwayAnimation module at keyframes and subframes',roots:roots.size,samples:witness.samples.length,maxPositionErrorMetres:maxPosition,maxYawErrorRadians:maxYaw,maxScaleError:maxScale,tolerance:{positionMetres:.005,yawRadians:.002,scale:.005},errors,status:witness.source_sha256===data.source_sha256&&roots.size===witness.roots&&witness.roots>0&&maxPosition<.005&&maxYaw<.002&&maxScale<.005&&!errors.length?'passed':'failed',comparisons};
await writeFile(new URL('./output/playwright/train-motion-equality.json',import.meta.url),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,comparisons:undefined},null,2));if(report.status!=='passed')process.exitCode=1;
