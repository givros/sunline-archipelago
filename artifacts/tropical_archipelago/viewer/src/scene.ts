import * as THREE from 'three/webgpu';
import {normalMap,vec3,sin,cos,positionWorld,normalWorld,cameraPosition,normalize,dot,clamp,pow,mix,output,vec4,float,texture,screenUV} from 'three/tsl';
import type {SceneData,RootRecord} from './types';

export async function loadWorld(progress:(text:string,value:number)=>void){
  progress('Charting the islands…',12);
  const start=performance.now();const manifest=await fetch('./assets/scene.json');if(!manifest.ok)throw new Error('The island scene could not be loaded. Please reload the page.');
  const data:SceneData=await manifest.json();
  const meshResponse=await fetch('./assets/scene.bin');if(!meshResponse.ok)throw new Error('The environment geometry could not be loaded.');const binary=await meshResponse.arrayBuffer();
  progress('Opening the coastal villages…',30);
  const root=new THREE.Group();root.name='Tropical Archipelago — full source geometry';root.rotation.x=-Math.PI/2;
  const textureLoader=new THREE.TextureLoader(),textures:THREE.Texture[]=[];
  const reflection=new THREE.RenderTarget(1,1,{type:THREE.HalfFloatType,samples:4});
  const reflectedColor=texture(reflection.texture,screenUV.flipX());
  const materials=await Promise.all(data.materials.map(async rec=>{
    const mat=new THREE.MeshStandardNodeMaterial({color:new THREE.Color(...rec.color as [number,number,number]),roughness:rec.roughness,metalness:rec.metalness,opacity:rec.opacity,transparent:rec.opacity<.999,side:rec.doubleSide?THREE.DoubleSide:THREE.FrontSide});
    mat.name=rec.name;mat.depthWrite=rec.opacity>=.7;
    if(rec.map){mat.map=await textureLoader.loadAsync('./assets/'+rec.map);mat.map.colorSpace=THREE.SRGBColorSpace;mat.map.flipY=true;mat.map.anisotropy=16;textures.push(mat.map);if(rec.role==='ocean')mat.color.setRGB(1,1,1);}
    if(rec.role==='ocean'){
      mat.roughness=rec.roughness;mat.metalness=rec.metalness;
      const rippleScale=clamp(float(25).div(cameraPosition.sub(positionWorld).length()),0,1).mul(.012);
      const waveX=sin(positionWorld.x.mul(6.4).add(cos(positionWorld.z.mul(4.6)))).mul(rippleScale).add(.5);
      const waveY=cos(positionWorld.z.mul(7.1).add(sin(positionWorld.x.mul(5.4)))).mul(rippleScale).add(.5);
      if(data.geometries.some(g=>g.uv&&g.materials.includes(rec.id)))mat.normalNode=normalMap(vec3(waveX,waveY,1));
      const view=normalize(cameraPosition.sub(positionWorld));const facing=clamp(dot(normalWorld,view),0,1);const fresnel=float(.018).add(pow(float(1).sub(facing),5).mul(.73));
      mat.outputNode=vec4(mix(output.rgb,reflectedColor.rgb,fresnel),output.a);
      mat.userData.role='ocean';
    }
    return mat;
  }));
  const geometries=data.geometries.map(rec=>{
    const g=new THREE.BufferGeometry();g.name=rec.hash;
    for(const key of ['position','normal','uv','color']as const){const a=rec[key];if(a)g.setAttribute(key,new THREE.BufferAttribute(new Float32Array(binary,a.offset,a.count*a.itemSize),a.itemSize));}
    rec.groups.forEach(x=>g.addGroup(x.start,x.count,x.materialIndex));g.computeBoundingSphere();g.computeBoundingBox();return g;
  });
  const materialVariants=new Map<string,THREE.Material[]>();
  function forGeometry(id:number){
    const g=data.geometries[id];const key=g.materials.join(',')+Boolean(g.color);let mats=materialVariants.get(key);if(!mats){mats=g.materials.map(mid=>{const m=materials[mid];if(g.color){const copy=m.clone();copy.vertexColors=true;return copy;}return m;});materialVariants.set(key,mats);}return mats;
  }
  const moving=new Map<string,THREE.Group>();data.dynamic_roots.forEach(rec=>{const group=new THREE.Group();group.name=rec.id;group.matrix.fromArray(rec.matrix);group.matrix.decompose(group.position,group.quaternion,group.scale);root.add(group);moving.set(rec.id,group);});
  const buckets=new Map<string,typeof data.objects>();
  const geometryUses=new Map<number,number>();for(const obj of data.objects)if(!obj.dynamic_root)geometryUses.set(obj.geometry,(geometryUses.get(obj.geometry)||0)+1);
  type MergePart={object:typeof data.objects[number];start:number;count:number;materialIndex:number};
  const mergeBuckets=new Map<string,MergePart[]>();
  // Preserve exact detail and IDs while sharing geometry and draw submission in spatial cells.
  for(const obj of data.objects){
    const rec=data.geometries[obj.geometry],ocean=rec.materials.some(i=>data.materials[i].role==='ocean');
    if(obj.dynamic_root||(!ocean&&(geometryUses.get(obj.geometry)||0)<24)){
      const center=geometries[obj.geometry].boundingSphere!.center.clone().applyMatrix4(new THREE.Matrix4().fromArray(obj.matrix));
      for(const group of rec.groups){const key=`${obj.dynamic_root||'static'}:${rec.materials[group.materialIndex]}:${Boolean(rec.uv)}:${Boolean(rec.color)}:${obj.dynamic_root?'local':Math.floor(center.x/220)+','+Math.floor(center.y/220)}`,part={object:obj,start:group.start,count:group.count,materialIndex:group.materialIndex};const bucket=mergeBuckets.get(key);if(bucket)bucket.push(part);else mergeBuckets.set(key,[part]);}continue;
    }
    const key=String(obj.geometry);const bucket=buckets.get(key);if(bucket)bucket.push(obj);else buckets.set(key,[obj]);
  }
  const mergedGeometries:THREE.BufferGeometry[]=[];
  for(const[key,parts]of mergeBuckets){
    const first=parts[0],firstRecord=data.geometries[first.object.geometry],count=parts.reduce((s,p)=>s+p.count,0),positions=new Float32Array(count*3),normals=new Float32Array(count*3),uvs=firstRecord.uv?new Float32Array(count*2):null,colors=firstRecord.color?new Float32Array(count*4):null;
    let cursor=0;const sourceRanges:{id:string;start:number;count:number}[]=[],point=new THREE.Vector3(),normal=new THREE.Vector3();
    for(const part of parts){const source=geometries[part.object.geometry],p=source.getAttribute('position'),n=source.getAttribute('normal'),uv=source.getAttribute('uv'),color=source.getAttribute('color'),matrix=new THREE.Matrix4().fromArray(part.object.matrix),normalMatrix=new THREE.Matrix3().getNormalMatrix(matrix);sourceRanges.push({id:part.object.id,start:cursor,count:part.count});
      for(let i=part.start;i<part.start+part.count;i++,cursor++){point.fromBufferAttribute(p,i).applyMatrix4(matrix);positions[cursor*3]=point.x;positions[cursor*3+1]=point.y;positions[cursor*3+2]=point.z;normal.fromBufferAttribute(n,i).applyMatrix3(normalMatrix).normalize();normals[cursor*3]=normal.x;normals[cursor*3+1]=normal.y;normals[cursor*3+2]=normal.z;if(uvs){uvs[cursor*2]=uv.getX(i);uvs[cursor*2+1]=uv.getY(i);}if(colors){colors[cursor*4]=color.getX(i);colors[cursor*4+1]=color.getY(i);colors[cursor*4+2]=color.getZ(i);colors[cursor*4+3]=color.getW(i);}}
    }
    const geometry=new THREE.BufferGeometry();geometry.setAttribute('position',new THREE.BufferAttribute(positions,3));geometry.setAttribute('normal',new THREE.BufferAttribute(normals,3));if(uvs)geometry.setAttribute('uv',new THREE.BufferAttribute(uvs,2));if(colors)geometry.setAttribute('color',new THREE.BufferAttribute(colors,4));geometry.computeBoundingBox();geometry.computeBoundingSphere();mergedGeometries.push(geometry);
    const mesh=new THREE.Mesh(geometry,forGeometry(first.object.geometry)[first.materialIndex]);mesh.name='Material group '+key;mesh.userData.sourceRanges=sourceRanges;mesh.castShadow=true;mesh.receiveShadow=true;mesh.matrixAutoUpdate=false;(first.object.dynamic_root?moving.get(first.object.dynamic_root)!:root).add(mesh);
  }
  for(const [key,instances]of buckets){
    const first=instances[0],mats=forGeometry(first.geometry);const ocean=mats.some(m=>m.userData.role==='ocean');
    if(instances.length===1){const mesh=new THREE.Mesh(geometries[first.geometry],mats);mesh.name=first.id;mesh.matrix.fromArray(first.matrix);mesh.matrixAutoUpdate=false;mesh.castShadow=!ocean;mesh.receiveShadow=true;root.add(mesh);}
    else{const mesh=new THREE.InstancedMesh(geometries[first.geometry],mats,THREE.MathUtils.ceilPowerOfTwo(instances.length));mesh.count=instances.length;mesh.name='Instances '+key;mesh.userData.semanticIds=instances.map(o=>o.id);instances.forEach((o,i)=>mesh.setMatrixAt(i,new THREE.Matrix4().fromArray(o.matrix)));mesh.instanceMatrix.needsUpdate=true;mesh.castShadow=!ocean;mesh.receiveShadow=true;mesh.computeBoundingSphere();mesh.computeBoundingBox();root.add(mesh);}
  }
  let retainedTriangles=0,renderObjects=0;root.traverse(o=>{const mesh=o as THREE.Mesh;if(mesh.isMesh){retainedTriangles+=mesh.geometry.getAttribute('position').count/3*((mesh as THREE.InstancedMesh).isInstancedMesh?(mesh as THREE.InstancedMesh).count:1);renderObjects++;}});
  if(retainedTriangles!==data.stats.source_evaluated_triangles)throw new Error('The complete island geometry could not be reconstructed. Please reload.');
  root.updateMatrixWorld(true);progress('Connecting the railway and footpaths…',58);
  return {data,binary,root,moving,reflection,retainedTriangles,renderObjects,oceanMaterials:materials.filter(m=>m.userData.role==='ocean'),loadMilliseconds:performance.now()-start,dispose(){geometries.forEach(g=>g.dispose());mergedGeometries.forEach(g=>g.dispose());new Set([...materials,...Array.from(materialVariants.values()).flat()]).forEach(m=>m.dispose());textures.forEach(t=>t.dispose());reflection.dispose();}};
}

type Lane={points:THREE.Vector3[];cumulative:number[];length:number};
type Route={id:string;points:THREE.Vector3[];normals:THREE.Vector3[];cumulative:number[];length:number;closed:boolean;lanes:Map<number,Lane>};
type Motion={low:number;high:number;stroke:number;speed:number;ramp:number;cruise:number;travel:number;dwell:number;period:number};
type Car={root:THREE.Group;index:number;lateral:number;rear:boolean;bogies:{root:THREE.Group;role:string}[]};
type Train={id:string;route:Route;cars:Car[];motion:Motion;phase:number;duration:number;keyframeStep:number};
type Pose={position:THREE.Vector3;yaw:number;rearDistance:number;frontDistance:number};
type KeyPose={body:Pose;bogies:{position:THREE.Vector3;yaw:number}[]};

/** Exact port of scripts/train_motion.py, including Blender's linear keyframe interpolation. */
export class RailwayAnimation{
  routes:Route[]=[];trains:Train[]=[];running=true;elapsed=0;
  private drawbars:{root:THREE.Group;a:THREE.Group;b:THREE.Group;anchorA:THREE.Vector3;anchorB:THREE.Vector3}[]=[];
  private poseCache=new Map<string,{t0:number;t1:number;a:KeyPose;b:KeyPose}>();
  constructor(data:SceneData,roots:Map<string,THREE.Group>){
    const specRoutes=data.spec.rail_routes||data.spec.railway?.routes||[];
    for(const r of Array.isArray(specRoutes)?specRoutes:Object.values(specRoutes)as any[]){
      const raw=r.points||r.samples||r.centerline;if(!raw?.length)continue;
      const points:THREE.Vector3[]=raw.map((p:any)=>new THREE.Vector3(...(Array.isArray(p)?p:[p.x,p.y,p.z])as[number,number,number])),cumulative=[0];
      for(let i=1;i<points.length;i++)cumulative.push(cumulative[i-1]+points[i].distanceTo(points[i-1]));
      const normals=points.map((_,i)=>{const t=points[Math.min(i+1,points.length-1)].clone().sub(points[Math.max(0,i-1)]);t.z=0;t.normalize();return new THREE.Vector3(-t.y,t.x,0);});
      this.routes.push({id:r.id||r.name,points,normals,cumulative,length:cumulative.at(-1)!,closed:!!r.closed,lanes:new Map()});
    }
    const groups=new Map<string,RootRecord[]>();for(const record of data.dynamic_roots){if(record.properties.asset_type==='train_bogie'||record.properties.car_index===undefined)continue;const id=String(record.properties.train_id||'SUNLINE');if(groups.has(id))groups.get(id)!.push(record);else groups.set(id,[record]);}
    for(const[id,records]of groups){
      records.sort((a,b)=>Number(a.properties.car_index||0)-Number(b.properties.car_index||0));const p=records[0].properties,route=this.routes.find(r=>r.id===p.route_id)||this.routes[0];if(!route)continue;
      const speed=Number(p.speed||7.5),low=Number(p.motion_head_min??(15+(records.length-1)*19)),high=Number(p.motion_head_max??(route.length-15)),stroke=high-low,ramp=Number(p.motion_ramp_seconds??Math.min(5,stroke/speed*.25)),cruise=Math.max(0,stroke/speed-ramp),travel=2*ramp+cruise,dwell=Number(p.motion_dwell_seconds??2),period=Number(p.motion_physical_period_seconds??2*(travel+dwell));
      const motion={low,high,stroke,speed,ramp,cruise,travel,dwell,period},duration=Number(p.motion_duration_seconds??Math.round(period*24)/24);
      const phase=Number(p.motion_phase_seconds??this.phaseForDistance(Number(p.distance_on_route||low),motion));
      const cars=records.map(r=>({root:roots.get(r.id)!,index:Number(r.properties.car_index||0),lateral:Number(r.properties.track_offset||0),rear:Boolean(r.properties.motion_rear_bogie_mirror??r.properties.role==='rear'),bogies:data.dynamic_roots.filter(b=>b.properties.motion_parent_car===r.id).map(b=>({root:roots.get(b.id)!,role:String(b.properties.bogie_role).toLowerCase()}))})).filter(c=>c.root);
      this.trains.push({id,route,cars,motion,phase,duration,keyframeStep:Number(p.motion_keyframe_step||6)/Number(p.motion_fps||24)});
    }
    for(const record of data.dynamic_roots.filter(r=>r.properties.asset_type==='train_drawbar')){const p=record.properties,root=roots.get(record.id),a=roots.get(String(p.car_a)),b=roots.get(String(p.car_b));if(root&&a&&b)this.drawbars.push({root,a,b,anchorA:new THREE.Vector3(...p.anchor_a_local as[number,number,number]),anchorB:new THREE.Vector3(...p.anchor_b_local as[number,number,number])});}
    this.apply();
  }
  lane(route:Route,offset:number){let lane=route.lanes.get(offset);if(!lane){const points=route.points.map((p,i)=>p.clone().addScaledVector(route.normals[i],offset)),cumulative=[0];for(let i=1;i<points.length;i++)cumulative.push(cumulative[i-1]+points[i].distanceTo(points[i-1]));lane={points,cumulative,length:cumulative.at(-1)!};route.lanes.set(offset,lane);}return lane;}
  sample(route:Route,distance:number,offset=0){
    const lane=this.lane(route,offset);distance=Math.max(0,Math.min(lane.length,distance));let lo=0,hi=lane.cumulative.length-1;while(lo+1<hi){const m=(lo+hi)>>1;if(lane.cumulative[m]<=distance)lo=m;else hi=m;}
    const alpha=(distance-lane.cumulative[lo])/(lane.cumulative[hi]-lane.cumulative[lo]);return lane.points[lo].clone().lerp(lane.points[hi],alpha);
  }
  outward(t:number,m:Motion){if(t<=0)return 0;if(t<m.ramp)return m.speed*.5*(t-m.ramp/Math.PI*Math.sin(Math.PI*t/m.ramp));if(t<m.ramp+m.cruise)return m.speed*m.ramp*.5+m.speed*(t-m.ramp);if(t<2*m.ramp+m.cruise){const q=t-m.ramp-m.cruise;return m.stroke-m.speed*m.ramp*.5+m.speed*.5*(q+m.ramp/Math.PI*Math.sin(Math.PI*q/m.ramp));}return m.stroke;}
  phaseForDistance(distance:number,m:Motion){const d=Math.min(m.stroke,Math.max(0,distance-m.low));let lo=0,hi=m.travel;for(let i=0;i<56;i++){const mid=(lo+hi)*.5;if(this.outward(mid,m)<d)lo=mid;else hi=mid;}return(lo+hi)*.5;}
  headAt(elapsed:number,t:Train){const m=t.motion,phase=((elapsed*m.period/t.duration+t.phase)%m.period+m.period)%m.period;if(phase<m.travel)return m.low+this.outward(phase,m);if(phase<m.travel+m.dwell)return m.high;if(phase<2*m.travel+m.dwell)return m.high-this.outward(phase-m.travel-m.dwell,m);return m.low;}
  pose(route:Route,d:number,lateral:number,rear:boolean):Pose{
    const back=rear?-5.5:-5.8,front=rear?5.8:5.5,center=d+(back+front)*.5;let low=(front-back)*.5,high=low*1.04;
    const length=(half:number)=>this.sample(route,center+half,lateral).distanceTo(this.sample(route,center-half,lateral));
    while(length(high)<11.3&&high<20)high*=1.08;for(let i=0;i<22;i++){const mid=(low+high)*.5;if(length(mid)<11.3)low=mid;else high=mid;}
    const half=(low+high)*.5,rearDistance=center-half,frontDistance=center+half,a=this.sample(route,rearDistance,lateral),b=this.sample(route,frontDistance,lateral),direction=b.clone().sub(a).normalize(),position=a.clone().lerp(b,.5).addScaledVector(direction,-(back+front)*.5);return{position,yaw:Math.atan2(direction.y,direction.x),rearDistance,frontDistance};
  }
  private keyPose(train:Train,car:Car,time:number):KeyPose{
    const body=this.pose(train.route,this.headAt(time,train)-car.index*19,car.lateral,car.rear),cs=Math.cos(body.yaw),sn=Math.sin(body.yaw);
    const bogies=car.bogies.map(b=>{const distance=b.role==='rear'?body.rearDistance:body.frontDistance,world=this.sample(train.route,distance,car.lateral),tangent=this.sample(train.route,distance+.88,car.lateral).sub(this.sample(train.route,distance-.88,car.lateral)).normalize(),delta=world.sub(body.position);return{position:new THREE.Vector3(delta.x*cs+delta.y*sn,-delta.x*sn+delta.y*cs,delta.z),yaw:Math.atan2(tangent.y,tangent.x)-body.yaw};});return{body,bogies};
  }
  private angleLerp(a:number,b:number,t:number){let delta=b-a;while(delta>Math.PI)delta-=Math.PI*2;while(delta<-Math.PI)delta+=Math.PI*2;return a+delta*t;}
  apply(){for(const train of this.trains){const time=((this.elapsed%train.duration)+train.duration)%train.duration,t0=Math.floor(time/train.keyframeStep)*train.keyframeStep,t1=Math.min(train.duration,t0+train.keyframeStep),mix=t1===t0?0:(time-t0)/(t1-t0);for(const car of train.cars){let cached=this.poseCache.get(car.root.name);if(!cached||cached.t0!==t0||cached.t1!==t1){cached={t0,t1,a:this.keyPose(train,car,t0),b:this.keyPose(train,car,t1)};this.poseCache.set(car.root.name,cached);}const{a,b}=cached;car.root.position.lerpVectors(a.body.position,b.body.position,mix);const yaw=this.angleLerp(a.body.yaw,b.body.yaw,mix);car.root.rotation.set(0,0,yaw);
      car.bogies.forEach((bogie,i)=>{const local=a.bogies[i].position.clone().lerp(b.bogies[i].position,mix),cs=Math.cos(yaw),sn=Math.sin(yaw);bogie.root.position.set(car.root.position.x+local.x*cs-local.y*sn,car.root.position.y+local.x*sn+local.y*cs,car.root.position.z+local.z);bogie.root.rotation.set(0,0,yaw+this.angleLerp(a.bogies[i].yaw,b.bogies[i].yaw,mix));});
    }}for(const bar of this.drawbars){bar.a.updateMatrix();bar.b.updateMatrix();const a=bar.anchorA.clone().applyMatrix4(bar.a.matrix),b=bar.anchorB.clone().applyMatrix4(bar.b.matrix);bar.root.position.copy(a).lerp(b,.5);bar.root.rotation.set(0,0,Math.atan2(b.y-a.y,b.x-a.x));bar.root.scale.set(a.distanceTo(b),1,1);}}
  update(dt:number){if(!this.running)return;this.elapsed+=dt;this.apply();}
  seek(seconds:number){this.elapsed=seconds;this.apply();}
  leadPosition(){const car=this.trains[0]?.cars[0];return car?car.root.getWorldPosition(new THREE.Vector3()):null;}
}

