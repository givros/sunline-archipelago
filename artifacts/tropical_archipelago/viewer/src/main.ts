import './style.css';
import * as THREE from 'three/webgpu';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {SkyMesh} from 'three/addons/objects/SkyMesh.js';
import {ao} from 'three/addons/tsl/display/GTAONode.js';
import {denoise} from 'three/addons/tsl/display/DenoiseNode.js';
import {texture,screenUV,normalView,vec4,builtinAOContext,uniform,mix} from 'three/tsl';
import {loadWorld,RailwayAnimation} from './scene';
import {installSourceColorTransform} from './color';
import {NavigationWorld,FirstPerson,fromBlender,controllerProfile} from './navigation';
import type {Diagnostic,Landmark} from './types';

const $=<T extends HTMLElement=HTMLElement>(id:string)=>document.getElementById(id)as T;
const canvas=$<HTMLCanvasElement>('world'),loadStart=performance.now();
const diagnostic:Diagnostic={phase:'initializing',backend:null,source:null,adapter:null,timings:{},errors:[],frames:0,frameTimes:[],cpuTimes:[],objects:0,triangles:0,drawCalls:0,ready:false};
let renderer:THREE.WebGPURenderer,world:Awaited<ReturnType<typeof loadWorld>>,navigation:NavigationWorld,controller:FirstPerson,animation:RailwayAnimation;
const scene=new THREE.Scene(),walkCamera=new THREE.PerspectiveCamera(50,innerWidth/innerHeight,.15,12000),overviewCamera=new THREE.OrthographicCamera(-470.6,470.6,470.6/innerWidth*innerHeight,-470.6/innerWidth*innerHeight,.15,12000);
let camera:THREE.PerspectiveCamera|THREE.OrthographicCamera=overviewCamera,overviewWidth=941.2;
let orbit:OrbitControls,disposed=false,mode:'overview'|'walking'|'train'='overview',lastTime=0,landmarks:Landmark[]=[],selected=0,raf=0,toastTimer=0;
let targetTransition:{from:THREE.Vector3;to:THREE.Vector3;targetFrom:THREE.Vector3;targetTo:THREE.Vector3;start:number}|null=null;
let sun:THREE.DirectionalLight,envTarget:THREE.RenderTarget,pmrem:THREE.PMREMGenerator;
let colorLut:THREE.Data3DTexture;
const sunOffset=new THREE.Vector3(-350,600,240);
const sky=new SkyMesh();
const reflectedPerspective=new THREE.PerspectiveCamera(),reflectedOrthographic=new THREE.OrthographicCamera();
const reflectionPlane=new THREE.Plane(new THREE.Vector3(0,1,0),-.03);
const reflectionClip=new THREE.Vector4(),reflectionQ=new THREE.Vector4();
const contactTarget=new THREE.RenderTarget(1,1,{type:THREE.HalfFloatType,samples:0});contactTarget.depthTexture=new THREE.DepthTexture(1,1,THREE.FloatType);
const contactMaterial=new THREE.NodeMaterial();contactMaterial.fragmentNode=vec4(normalView,1);contactMaterial.side=THREE.DoubleSide;
const contactNodes=new Map<THREE.Camera,ReturnType<typeof ao>>();const contactWeight=uniform(0),contactTexture=texture(new THREE.Texture(),screenUV),contactContext=builtinAOContext(mix(1,contactTexture.r,contactWeight));
const smoothContact=new THREE.RenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:false}),contactQuad=new THREE.QuadMesh(contactMaterial),contactFilters=new Map<THREE.Camera,THREE.NodeMaterial>();
const fallbackLandmarks:Landmark[]=[
 {id:'main_village',label:'Port Azure',position:[-270,-120,3],target:[-260,-135,22],yaw:-.5},
 {id:'stilt_lagoon',label:'Lagoon Boardwalk',position:[122,-8,3],target:[145,-8,8],yaw:1},
 {id:'east_village',label:'Bellflower Cove',position:[268,240,4],target:[292,240,28],yaw:.8},
 {id:'southern_retreat',label:'Palm Retreat',position:[245,-262,4],target:[261,-290,20],yaw:1.8},
 {id:'north_island',label:'Emerald Heights',position:[-84,282,4],target:[-93,280,27],yaw:1.1}
];
function progress(text:string,value:number){if(disposed)return;$('loading-label').textContent=text;$('loading-bar').style.width=`${value}%`;diagnostic.phase=text;}
function toast(text:string){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=window.setTimeout(()=>$('toast').hidden=true,5000);}
function currentRegion(){
  const ref=world.data.spec.reference||{scale_x:.65,scale_y:.82,pixels:[1448,1086]},px=camera.position.x/ref.scale_x+ref.pixels[0]/2,py=camera.position.z/ref.scale_y+ref.pixels[1]/2;
  for(const island of world.data.spec.islands||[]){const poly=island.shore||[];let inside=false;for(let i=0,j=poly.length-1;i<poly.length;j=i++){const a=poly[i],b=poly[j];if((a[1]>py)!==(b[1]>py)&&px<(b[0]-a[0])*(py-a[1])/(b[1]-a[1])+a[0])inside=!inside;}if(inside)return island.name;}
  return controller.foot>10?'Sunline viaduct':controller.foot>1?'Lagoon boardwalk':'Open lagoon';
}
function fail(error:unknown){if(disposed)return;const message=error instanceof Error?error.message:String(error);diagnostic.errors.push(message);diagnostic.phase='failed';diagnostic.ready=false;cancelAnimationFrame(raf);$('loading').hidden=false;$('loading-label').textContent=message.length>500?'Rendering could not complete. Reload the world; if the problem persists, restart your graphics-enabled browser.':message;$('reload').hidden=false;console.error(error);dispose();}
function overview(){controller?.stop();mode='overview';camera=overviewCamera;overviewCamera.zoom=1;overviewCamera.updateProjectionMatrix();orbit.object=camera;document.body.classList.remove('walking');$('pause').hidden=true;$('crosshair').hidden=true;orbit.enabled=true;$('region').textContent='Archipelago overview';$('overview').classList.add('active');$('train').classList.remove('active');transitionCamera(fromBlender(world.data.spec.camera?.position||[0,-900,1180]),new THREE.Vector3());}
function transitionCamera(position:THREE.Vector3,target:THREE.Vector3){targetTransition={from:camera.position.clone(),to:position,targetFrom:orbit.target.clone(),targetTo:target,start:performance.now()};}
function destination(index:number,walk=false){selected=index;const l=landmarks[index];if(!l)return;if(walk){beginWalking();return;}controller?.stop();mode='overview';camera=overviewCamera;overviewCamera.zoom=3.5;overviewCamera.updateProjectionMatrix();orbit.object=camera;document.body.classList.remove('walking');$('pause').hidden=true;$('crosshair').hidden=true;orbit.enabled=true;const target=fromBlender(l.target||l.position);transitionCamera(target.clone().add(new THREE.Vector3(150,250,220)),target);$('region').textContent=l.label;}
async function beginWalking(){try{const l=landmarks[selected]||landmarks[0];controller.spawn(fromBlender(l.position),l.yaw||0);camera=walkCamera;targetTransition=null;orbit.enabled=false;mode='walking';document.body.classList.add('walking');$('crosshair').hidden=false;$('pause').hidden=true;$('region').textContent=l.label;await controller.resume();if(document.pointerLockElement===canvas)toast('WASD / ZQSD · Mouse to look · Shift to move faster · Escape to pause');}catch(e){toast(e instanceof Error?e.message:String(e));}}
function pause(){if(mode!=='walking')return;$('pause').hidden=false;$('crosshair').hidden=true;}
async function resume(){$('pause').hidden=true;$('crosshair').hidden=false;await controller.resume();}
let fullscreenSession=0;
async function fullscreen(){try{if(document.fullscreenElement){await document.exitFullscreen();return;}await document.documentElement.requestFullscreen();const token=++fullscreenSession;const keyboard=(navigator as any).keyboard;if(keyboard?.lock){try{await keyboard.lock(['Escape']);if(token!==fullscreenSession||!document.fullscreenElement)keyboard.unlock();}catch{toast('Fullscreen is active. Your browser may also exit fullscreen when Escape is pressed.');}}}catch{toast('Fullscreen is unavailable in this window. You can continue exploring here.');}}
document.addEventListener('fullscreenchange',()=>{if(!document.fullscreenElement){fullscreenSession++;(navigator as any).keyboard?.unlock?.();}$('fullscreen').setAttribute('aria-label',document.fullscreenElement?'Exit fullscreen':'Enter fullscreen');$('fullscreen').title=document.fullscreenElement?'Exit fullscreen':'Enter fullscreen';resize();});
function resize(){if(!renderer||disposed)return;renderer.setPixelRatio(devicePixelRatio);renderer.setSize(innerWidth,innerHeight);walkCamera.aspect=innerWidth/innerHeight;walkCamera.updateProjectionMatrix();overviewCamera.left=-overviewWidth/2;overviewCamera.right=overviewWidth/2;overviewCamera.top=overviewWidth/2/innerWidth*innerHeight;overviewCamera.bottom=-overviewCamera.top;overviewCamera.updateProjectionMatrix();world?.reflection.setSize(Math.round(innerWidth*devicePixelRatio),Math.round(innerHeight*devicePixelRatio));contactTarget.setSize(Math.round(innerWidth*devicePixelRatio),Math.round(innerHeight*devicePixelRatio));smoothContact.setSize(Math.round(innerWidth*devicePixelRatio),Math.round(innerHeight*devicePixelRatio));}
function renderPasses(){
  let contact=contactNodes.get(camera);if(!contact){contact=ao(texture(contactTarget.depthTexture!),texture(contactTarget.texture),camera);contact.radius.value=2.2;contact.thickness.value=1.2;contact.samples.value=16;contact.setup({renderer,getSharedContext:()=>({})} as any);contactNodes.set(camera,contact);const filter=denoise(texture(contact.getTextureNode().value),texture(contactTarget.depthTexture!),texture(contactTarget.texture),camera);filter.radius.value=3;filter.depthPhi.value=10;filter.normalPhi.value=20;const material=new THREE.NodeMaterial();material.fragmentNode=filter;material.name='Contact occlusion denoise';contactFilters.set(camera,material);}
  contactTexture.value=smoothContact.texture;renderer.contextNode=contactContext;contactWeight.value=0;
  // One current sun map serves both camera passes; its casters and transforms
  // are unchanged between the reflection and beauty draw of this same frame.
  sun.shadow.autoUpdate=false;sun.shadow.needsUpdate=true;
  if(world.oceanMaterials.length){
    const reflectedCamera=camera===overviewCamera?reflectedOrthographic:reflectedPerspective;
    reflectedCamera.copy(camera as any);reflectedCamera.position.copy(camera.position);reflectedCamera.position.y=-camera.position.y;
    const direction=new THREE.Vector3();camera.getWorldDirection(direction);direction.y=-direction.y;reflectedCamera.up.set(0,-1,0);reflectedCamera.lookAt(reflectedCamera.position.clone().add(direction));reflectedCamera.updateMatrixWorld();
    const plane=reflectionPlane.clone().applyMatrix4(reflectedCamera.matrixWorldInverse);reflectionClip.set(plane.normal.x,plane.normal.y,plane.normal.z,plane.constant);
    const p=reflectedCamera.projectionMatrix.elements;reflectionQ.set(Math.sign(reflectionClip.x),Math.sign(reflectionClip.y),1,1).applyMatrix4(reflectedCamera.projectionMatrix.clone().invert());reflectionClip.multiplyScalar(1/reflectionClip.dot(reflectionQ));p[2]=reflectionClip.x;p[6]=reflectionClip.y;p[10]=reflectionClip.z;p[14]=reflectionClip.w;
    for(const material of world.oceanMaterials)material.visible=false;
    try{renderer.setRenderTarget(world.reflection);renderer.render(scene,reflectedCamera);}finally{renderer.setRenderTarget(null);for(const material of world.oceanMaterials)material.visible=true;}
  }
  const previousOverride=scene.overrideMaterial;sky.visible=false;scene.overrideMaterial=contactMaterial;
  try{renderer.setRenderTarget(contactTarget);renderer.render(scene,camera);}finally{renderer.setRenderTarget(null);scene.overrideMaterial=previousOverride;sky.visible=true;}
  contact.updateBefore({renderer} as any);contactQuad.material=contactFilters.get(camera)!;renderer.setRenderTarget(smoothContact);contactQuad.render(renderer);renderer.setRenderTarget(null);contactWeight.value=1;renderer.render(scene,camera);
}

async function init(){
  progress('Finding a window onto the islands…',4);
  if(!isSecureContext||!(navigator as any).gpu)throw new Error('This world needs WebGPU. Open this local address in a recent desktop Chrome or Edge with graphics acceleration enabled.');
  const adapter=await(navigator as any).gpu.requestAdapter({powerPreference:'high-performance'});if(!adapter)throw new Error('No WebGPU graphics adapter is available. Enable graphics acceleration and reload.');
  diagnostic.adapter=adapter.info?{vendor:adapter.info.vendor,architecture:adapter.info.architecture,device:adapter.info.device,description:adapter.info.description,isFallbackAdapter:adapter.info.isFallbackAdapter??adapter.isFallbackAdapter??null}:null;
  const features=adapter.features.has('timestamp-query')?['timestamp-query']:[];const device=await adapter.requestDevice({requiredFeatures:features});
  renderer=new THREE.WebGPURenderer({canvas,antialias:true,samples:4,alpha:false,device,trackTimestamp:features.length>0}as any);
  await renderer.init();if(!(renderer.backend as any).isWebGPUBackend)throw new Error('The WebGPU renderer could not start. This viewer does not reduce quality through a compatibility renderer.');diagnostic.backend='WebGPU';
  walkCamera.coordinateSystem=THREE.WebGPUCoordinateSystem;overviewCamera.coordinateSystem=THREE.WebGPUCoordinateSystem;
  device.lost.then((info:any)=>{if(!disposed)fail(`The graphics device was interrupted: ${info.message||info.reason}. Reload to restore the islands.`);});
  device.addEventListener('uncapturederror',(event:any)=>fail(`The graphics device reported: ${event.error.message}`));
  renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.AgXToneMapping;renderer.toneMappingExposure=Math.pow(2,.1);renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFShadowMap;renderer.info.autoReset=false;
  colorLut=await installSourceColorTransform(renderer);
  resize();window.addEventListener('resize',resize);diagnostic.timings.backend=performance.now()-loadStart;
  world=await loadWorld(progress);if(disposed){world.dispose();return;}diagnostic.source=world.data.source_sha256;diagnostic.objects=world.data.objects.length;diagnostic.triangles=world.data.stats.source_evaluated_triangles;diagnostic.timings.scene=world.loadMilliseconds;
  scene.add(world.root);overviewWidth=world.data.spec.camera?.ortho_scale||941.2;resize();
  const navStart=performance.now();navigation=new NavigationWorld(world.data,world.binary);diagnostic.timings.navigation=performance.now()-navStart;
  const raw=world.data.spec.viewer?.landmarks||world.data.spec.landmarks||world.data.spec.navigation?.landmarks;landmarks=raw?.length?raw.map((l:any)=>({id:l.id,label:l.label||l.name,position:l.spawn||l.position,target:l.target||l.look_at||l.position,yaw:l.yaw??Math.atan2(-((l.target||l.look_at||l.position)[0]-(l.spawn||l.position)[0]),(l.target||l.look_at||l.position)[1]-(l.spawn||l.position)[1])})):fallbackLandmarks;
  for(let i=0;i<landmarks.length;i++){const button=document.createElement('button');button.innerHTML=`<span>${String(i+1).padStart(2,'0')}</span>${landmarks[i].label}`;button.addEventListener('click',()=>{destination(i);$('destinations').hidden=true;$('places').setAttribute('aria-expanded','false');});$('landmarks').appendChild(button);}
  $('places').addEventListener('click',()=>{$('destinations').hidden=!$('destinations').hidden;$('places').setAttribute('aria-expanded',String(!$('destinations').hidden));});
  const sourceSun=world.data.lighting?.suns[0];if(sourceSun)sunOffset.copy(fromBlender(sourceSun.direction)).normalize().multiplyScalar(750);
  sky.scale.setScalar(9000);sky.turbidity.value=2.2;sky.rayleigh.value=1.6;sky.mieCoefficient.value=.002;sky.mieDirectionalG.value=.8;sky.sunPosition.value.copy(sunOffset).normalize();sky.showSunDisc.value=false;
  const envScene=new THREE.Scene();envScene.add(sky);pmrem=new THREE.PMREMGenerator(renderer);envTarget=pmrem.fromScene(envScene,.035,.1,10000);scene.environment=envTarget.texture;scene.environmentIntensity=.1;envScene.remove(sky);scene.add(sky);sky.showSunDisc.value=true;
  sun=new THREE.DirectionalLight(sourceSun?new THREE.Color().fromArray(sourceSun.color):0xffefdc,sourceSun?.energy||2.4);sun.position.copy(sunOffset);sun.castShadow=true;sun.shadow.mapSize.set(4096,4096);sun.shadow.camera.near=1;sun.shadow.camera.far=1900;sun.shadow.camera.left=-560;sun.shadow.camera.right=560;sun.shadow.camera.top=560;sun.shadow.camera.bottom=-560;sun.shadow.normalBias=.08;sun.shadow.bias=-.00012;sun.shadow.camera.updateProjectionMatrix();scene.add(sun,sun.target);
  scene.add(new THREE.HemisphereLight(0xd5f2ff,0x677952,.28));
  camera.position.copy(fromBlender(world.data.spec.camera?.position||[0,-900,1180]));camera.lookAt(0,0,0);orbit=new OrbitControls(camera,canvas);orbit.target.set(0,0,0);orbit.enableDamping=true;orbit.dampingFactor=.065;orbit.minDistance=4;orbit.maxDistance=1850;orbit.maxPolarAngle=Math.PI*.489;orbit.minZoom=.45;orbit.maxZoom=50;
  controller=new FirstPerson(walkCamera,navigation,canvas,pause,toast);animation=new RailwayAnimation(world.data,world.moving);
  $('walk').addEventListener('click',beginWalking);$('resume').addEventListener('click',resume);$('overview').addEventListener('click',overview);$('pause-overview').addEventListener('click',overview);$('reset').addEventListener('click',()=>{selected=0;beginWalking();});$('fullscreen').addEventListener('click',fullscreen);
  $('train').addEventListener('click',()=>{controller.stop();mode='train';camera=walkCamera;targetTransition=null;orbit.enabled=false;const target=animation.leadPosition();if(target)camera.position.copy(target.clone().add(new THREE.Vector3(-55,40,55)));document.body.classList.remove('walking');$('pause').hidden=true;$('crosshair').hidden=true;$('region').textContent='The Sunline';$('train').classList.add('active');$('overview').classList.remove('active');});
  $('motion').addEventListener('click',()=>{animation.running=!animation.running;$('motion').textContent=animation.running?'Ⅱ':'▷';$('motion').setAttribute('aria-label',animation.running?'Pause trains':'Resume trains');});
  progress('Preparing the sunlight and sea…',76);
  const shaderStart=performance.now();await renderer.compileAsync(scene,camera,undefined,event=>progress(`Preparing the sunlight and sea… ${Math.round(event.loaded/event.total*100)}%`,76+event.loaded/event.total*18));progress('Drawing the islands and their reflections…',95);renderPasses();progress('Finishing the first view…',98);await device.queue.onSubmittedWorkDone();if(diagnostic.errors.length)throw new Error(diagnostic.errors.at(-1));diagnostic.timings.firstFrame=performance.now()-loadStart;diagnostic.timings.shaderAndFirstFrame=performance.now()-shaderStart;
  progress('Your passage is ready.',100);diagnostic.ready=true;diagnostic.phase='ready';$('loading').hidden=true;
  exposeDiagnostics();lastTime=performance.now();raf=requestAnimationFrame(frame);
}

async function frame(now:number){if(disposed||!diagnostic.ready)return;const cpuStart=performance.now();const interval=now-lastTime,dt=Math.min(.25,Math.max(0,interval*.001));lastTime=now;
  try{
    animation.update(Math.max(0,interval*.001));controller.update(dt);if(mode==='walking')$('region').textContent=`${currentRegion()}${controller.swimming?' · Swimming':''}`;
    if(targetTransition){const t=THREE.MathUtils.clamp((now-targetTransition.start)/1300,0,1),smooth=t*t*(3-2*t);camera.position.lerpVectors(targetTransition.from,targetTransition.to,smooth);orbit.target.lerpVectors(targetTransition.targetFrom,targetTransition.targetTo,smooth);if(t===1)targetTransition=null;}
    if(mode==='train'){const target=animation.leadPosition();if(target){camera.position.lerp(target.clone().add(new THREE.Vector3(-55,40,55)),1-Math.exp(-dt*1.4));camera.lookAt(target);}}
    else if(mode==='overview')orbit.update();
    if(mode==='walking'){const p=camera.position;sun.target.position.set(p.x,0,p.z);sun.position.copy(sunOffset).add(sun.target.position);const c=sun.shadow.camera;if(c.right!==95){c.left=-95;c.right=95;c.top=95;c.bottom=-95;c.updateProjectionMatrix();}}
    else if(sun.shadow.camera.right!==560){sun.target.position.set(0,0,0);sun.position.copy(sunOffset);Object.assign(sun.shadow.camera,{left:-560,right:560,top:560,bottom:-560});sun.shadow.camera.updateProjectionMatrix();}
    renderer.info.reset();renderPasses();diagnostic.frames++;diagnostic.drawCalls=renderer.info.render.drawCalls;
    diagnostic.frameTimes.push(interval);diagnostic.cpuTimes.push(performance.now()-cpuStart);if(diagnostic.frameTimes.length>2400){diagnostic.frameTimes.shift();diagnostic.cpuTimes.shift();}
    await (renderer.backend as any).device.queue.onSubmittedWorkDone();if(!disposed)raf=requestAnimationFrame(frame);
  }catch(error){fail(error);}
}
function exposeDiagnostics(){
  const api={diagnostic,controllerProfile,landmarks,
    snapshot:()=>({diagnostic,mode,position:camera.position.toArray(),foot:controller.foot,eyeAboveSupport:camera.position.y-controller.foot,yaw:controller.yaw,pitch:controller.pitch,paused:controller.paused,keys:[...controller.keys],swimming:controller.swimming,distanceWalked:controller.distanceWalked,navigation:{surfaces:navigation.surfaceCount,obstacles:navigation.obstacleCount},trainRoots:[...world.moving].filter(([id])=>id.startsWith('TRAIN_CAR_')).map(([id,g])=>({id,position:g.position.toArray(),rotation:g.rotation.toArray()})),bogieRoots:[...world.moving].filter(([id])=>id.startsWith('TRAIN_BOGIE_')).map(([id,g])=>({id,position:g.position.toArray(),rotation:g.rotation.toArray()})),fullscreen:!!document.fullscreenElement,pointerLocked:document.pointerLockElement===canvas,rendererMemory:renderer.info.memory,viewport:[innerWidth,innerHeight],framebuffer:[canvas.width,canvas.height],dpr:devicePixelRatio}),
    setCamera:(position:number[],target:number[],orthographic=false)=>{controller.stop();mode='overview';camera=orthographic?overviewCamera:walkCamera;orbit.object=camera;targetTransition=null;orbit.enabled=true;document.body.classList.remove('walking');$('pause').hidden=true;$('crosshair').hidden=true;camera.position.fromArray(position);orbit.target.fromArray(target);orbit.update();},
    overview,destination,beginWalking,pause:()=>controller.pause(),resume,
    safeSpawns:()=>landmarks.map(l=>{try{return{id:l.id,position:navigation.safeSpawn(fromBlender(l.position)).toArray(),valid:true};}catch(e){return{id:l.id,valid:false,error:String(e)};}}),
    clearMetrics:()=>{diagnostic.frameTimes.length=0;diagnostic.cpuTimes.length=0;},
    gpuTiming:async()=>{await renderer.resolveTimestampsAsync();return renderer.info.render.timestamp;},
    navigationProbe:(x:number,z:number,foot:number)=>({support:navigation.support(x,z,foot),terrain:navigation.support(x,z,Infinity,true),blocked:navigation.blocks(x,z,foot),blockingObjects:navigation.blockingObjects(x,z,foot),stand:navigation.canStand(x,z,foot)}),
    moveFor:(keys:string[],seconds:number)=>{const before=camera.position.clone();controller.keys=new Set(keys);const was=controller.paused;controller.paused=false;for(let t=0;t<seconds;t+=1/60)controller.update(1/60);controller.keys.clear();controller.paused=was;return{before:before.toArray(),after:camera.position.toArray(),distance:before.distanceTo(camera.position)};},
    geometryInventory:()=>({retainedTriangles:world.retainedTriangles,renderObjects:world.renderObjects,dynamicRootCount:world.moving.size,sourceObjects:world.data.objects.length}),
    walkerPose:(position:number[],yaw:number)=>{const p=new THREE.Vector3().fromArray(position),support=navigation.canStand(p.x,p.z,p.y-1.72);if(support===null)throw new Error('Validation pose must lie on a usable source surface');walkCamera.position.set(p.x,support+1.72,p.z);controller.foot=support;controller.yaw=yaw;controller.pitch=-.06;controller.velocityY=0;controller.swimming=false;controller.updateLook();controller.active=true;controller.paused=true;camera=walkCamera;mode='walking';targetTransition=null;orbit.enabled=false;document.body.classList.add('walking');return{position:camera.position.toArray(),foot:controller.foot};},
    turnWalker:(yaw:number)=>{controller.yaw=yaw;controller.updateLook();},
    setTrainTime:(seconds:number)=>{animation.running=false;animation.seek(seconds);return [...world.moving].map(([id,g])=>({id,position:g.position.toArray(),yaw:g.rotation.z,scale:g.scale.toArray()}));},
    dispose
  };(window as any).__archipelago=api;
}
function dispose(){if(disposed)return;disposed=true;diagnostic.ready=false;if(diagnostic.phase!=='failed')diagnostic.phase='disposed';cancelAnimationFrame(raf);controller?.dispose();orbit?.dispose();window.removeEventListener('resize',resize);(navigator as any).keyboard?.unlock?.();world?.dispose();colorLut?.dispose();contactTarget.dispose();smoothContact.dispose();contactFilters.forEach(m=>{(m.fragmentNode as any)?.dispose?.();m.dispose();});contactMaterial.dispose();contactNodes.forEach(n=>n.dispose());sky.geometry.dispose();sky.material.dispose();envTarget?.dispose();pmrem?.dispose();renderer?.dispose();}
window.addEventListener('beforeunload',dispose);
$('reload').addEventListener('click',()=>location.reload());
init().catch(fail);
