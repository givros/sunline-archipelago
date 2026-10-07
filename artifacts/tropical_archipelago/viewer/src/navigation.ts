import {Matrix4,Vector3,Box3,Euler,PerspectiveCamera,Triangle as MeshTriangle} from 'three/webgpu';
import type {SceneData,Landmark} from './types';

const CELL=8, RADIUS=.32, EYE=1.72, STEP=.5, MAX_DROP=1.15;
const basis=new Matrix4().makeRotationX(-Math.PI/2);
type Triangle={a:Vector3;b:Vector3;c:Vector3;minY:number;maxY:number;terrain:boolean;walkableSlope:boolean};
type Obstacle={id:string;inverse:Matrix4;bounds:Box3;minY:number;maxY:number;scale:Vector3;triangles?:MeshTriangle[]};
function segmentDistanceSquared(a:Vector3,b:Vector3,c:Vector3,d:Vector3){
 const u=b.clone().sub(a),v=d.clone().sub(c),w=a.clone().sub(c),aa=u.dot(u),bb=u.dot(v),cc=v.dot(v),dd=u.dot(w),ee=v.dot(w),den=aa*cc-bb*bb;let s=den>1e-12?Math.max(0,Math.min(1,(bb*ee-cc*dd)/den)):0,t=cc>1e-12?(bb*s+ee)/cc:0;if(t<0){t=0;s=aa>1e-12?Math.max(0,Math.min(1,-dd/aa)):0;}else if(t>1){t=1;s=aa>1e-12?Math.max(0,Math.min(1,(bb-dd)/aa)):0;}return w.addScaledVector(u,s).addScaledVector(v,-t).lengthSq();
}
function capsuleHitsTriangles(triangles:MeshTriangle[],x:number,z:number,foot:number){
 const a=new Vector3(x,foot+RADIUS,z),b=new Vector3(x,foot+EYE-RADIUS,z),closest=new Vector3(),normal=new Vector3(),direction=b.clone().sub(a),intersection=new Vector3(),rr=RADIUS*RADIUS;
 for(const tri of triangles){if(Math.max(tri.a.y,tri.b.y,tri.c.y)<foot+.12||Math.min(tri.a.y,tri.b.y,tri.c.y)>foot+EYE)continue;
  if(tri.closestPointToPoint(a,closest).distanceToSquared(a)<rr||tri.closestPointToPoint(b,closest).distanceToSquared(b)<rr)return true;
  tri.getNormal(normal);const denominator=normal.dot(direction);if(Math.abs(denominator)>1e-12){const t=normal.dot(tri.a.clone().sub(a))/denominator;if(t>=0&&t<=1&&tri.containsPoint(intersection.copy(a).addScaledVector(direction,t)))return true;}
  if(segmentDistanceSquared(a,b,tri.a,tri.b)<rr||segmentDistanceSquared(a,b,tri.b,tri.c)<rr||segmentDistanceSquared(a,b,tri.c,tri.a)<rr)return true;
 }return false;
}
export function fromBlender(p:number[]):Vector3{return new Vector3(p[0],p[2],-p[1]);}
export class NavigationWorld{
  private surfaces=new Map<string,Triangle[]>();private obstacles=new Map<string,Obstacle[]>();
  surfaceCount=0;obstacleCount=0;
  constructor(data:SceneData,binary:ArrayBuffer){
    const local=new Vector3(), world=new Vector3();
    for(const obj of data.objects){
      if(obj.dynamic_root)continue;
      const g=data.geometries[obj.geometry];const p=new Float32Array(binary,g.position.offset,g.position.count*3);
      const m=new Matrix4().multiplyMatrices(basis,new Matrix4().fromArray(obj.matrix));
      const walkable=Boolean(obj.properties.walkable),collider=Boolean(obj.properties.collider)&&!walkable;
      if(!walkable&&!collider)continue;
      if(walkable){
        for(let i=0;i<p.length;i+=9){
          const a=new Vector3(p[i],p[i+1],p[i+2]).applyMatrix4(m),b=new Vector3(p[i+3],p[i+4],p[i+5]).applyMatrix4(m),c=new Vector3(p[i+6],p[i+7],p[i+8]).applyMatrix4(m);
          const normal=new Vector3().subVectors(b,a).cross(new Vector3().subVectors(c,a)).normalize();
          const terrain=obj.id.startsWith('REG_');if(normal.y<Math.SQRT1_2&&!terrain)continue;
          const tri={a,b,c,minY:Math.min(a.y,b.y,c.y),maxY:Math.max(a.y,b.y,c.y),terrain,walkableSlope:normal.y>=Math.SQRT1_2};
          this.insert(this.surfaces,tri,Math.min(a.x,b.x,c.x),Math.max(a.x,b.x,c.x),Math.min(a.z,b.z,c.z),Math.max(a.z,b.z,c.z));this.surfaceCount++;
        }
      }
      if(collider){
        const closedExterior=obj.properties.component_role==='wall_piers';
        // Connected rail openings and graded deck beams have nonconvex bounds.
        // Their boxes only reject distant probes; actual triangles decide contact.
        const exactStructure=/balustrade_rails|railing_handrails|longitudinal_joists/.test(obj.id),triangles:MeshTriangle[]|undefined=exactStructure?[]:undefined;
        if(triangles)for(let i=0;i<p.length;i+=9)triangles.push(new MeshTriangle(new Vector3(p[i],p[i+1],p[i+2]).applyMatrix4(m),new Vector3(p[i+3],p[i+4],p[i+5]).applyMatrix4(m),new Vector3(p[i+6],p[i+7],p[i+8]).applyMatrix4(m)));
        const boxes:{box:Box3;matrix:Matrix4}[]=closedExterior?[]:g.collisionOBBs?.map(b=>({box:new Box3(new Vector3().fromArray(b.bounds[0]),new Vector3().fromArray(b.bounds[1])),matrix:m.clone().multiply(new Matrix4().fromArray(b.matrix))}))||g.collisionBoxes?.map(b=>({box:new Box3(new Vector3().fromArray(b[0]),new Vector3().fromArray(b[1])),matrix:m}))||[];
        if(!boxes.length){const box=new Box3();for(let i=0;i<p.length;i+=3)box.expandByPoint(local.set(p[i],p[i+1],p[i+2]));boxes.push({box,matrix:m});}
        for(const component of boxes){const{box,matrix}=component,inverse=matrix.clone().invert(),scale=new Vector3().setFromMatrixScale(matrix),bounds=box.clone().applyMatrix4(matrix);const ob={id:obj.id,inverse,bounds:box,minY:bounds.min.y,maxY:bounds.max.y,scale,triangles};
          this.insert(this.obstacles,ob,bounds.min.x-RADIUS,bounds.max.x+RADIUS,bounds.min.z-RADIUS,bounds.max.z+RADIUS);this.obstacleCount++;
        }
      }
    }
  }
  private insert<T>(grid:Map<string,T[]>,obj:T,minX:number,maxX:number,minZ:number,maxZ:number){
    for(let x=Math.floor(minX/CELL);x<=Math.floor(maxX/CELL);x++)for(let z=Math.floor(minZ/CELL);z<=Math.floor(maxZ/CELL);z++){const key=`${x},${z}`;const cell=grid.get(key);if(cell)cell.push(obj);else grid.set(key,[obj]);}
  }
  support(x:number,z:number,foot:number=Infinity,terrainOnly=false):number|null{
    const tris=this.surfaces.get(`${Math.floor(x/CELL)},${Math.floor(z/CELL)}`)||[];let best=-Infinity;
    for(const t of tris){
      if((terrainOnly&&!t.terrain)||(!terrainOnly&&!t.walkableSlope)||t.minY>foot+STEP||t.maxY<best||t.maxY<.08)continue;
      const denominator=(t.b.z-t.c.z)*(t.a.x-t.c.x)+(t.c.x-t.b.x)*(t.a.z-t.c.z);if(Math.abs(denominator)<1e-8)continue;
      const u=((t.b.z-t.c.z)*(x-t.c.x)+(t.c.x-t.b.x)*(z-t.c.z))/denominator,v=((t.c.z-t.a.z)*(x-t.c.x)+(t.a.x-t.c.x)*(z-t.c.z))/denominator;
      if(u<-.0001||v<-.0001||u+v>1.0001)continue;
      const y=u*t.a.y+v*t.b.y+(1-u-v)*t.c.y;if(y<=foot+STEP&&y>best)best=y;
    }
    return Number.isFinite(best)?best:null;
  }
  blocks(x:number,z:number,foot:number){
    const obs=this.obstacles.get(`${Math.floor(x/CELL)},${Math.floor(z/CELL)}`)||[];const p=new Vector3();
    for(const o of obs){if(o.maxY<foot+.12||o.minY>foot+EYE+.15)continue;
      for(const h of [.22,.9,1.6]){p.set(x,foot+h,z).applyMatrix4(o.inverse);const rx=RADIUS/Math.max(o.scale.x,.01),ry=RADIUS/Math.max(o.scale.y,.01),rz=RADIUS/Math.max(o.scale.z,.01);if(p.x>=o.bounds.min.x-rx&&p.x<=o.bounds.max.x+rx&&p.y>=o.bounds.min.y-ry&&p.y<=o.bounds.max.y+ry&&p.z>=o.bounds.min.z-rz&&p.z<=o.bounds.max.z+rz&&(!o.triangles||capsuleHitsTriangles(o.triangles,x,z,foot)))return true;}
    }return false;
  }
  blockingObjects(x:number,z:number,foot:number){
    const obs=this.obstacles.get(`${Math.floor(x/CELL)},${Math.floor(z/CELL)}`)||[],ids=new Set<string>(),p=new Vector3();
    for(const o of obs){if(o.maxY<foot+.12||o.minY>foot+EYE+.15)continue;for(const h of [.22,.9,1.6]){p.set(x,foot+h,z).applyMatrix4(o.inverse);const rx=RADIUS/Math.max(o.scale.x,.01),ry=RADIUS/Math.max(o.scale.y,.01),rz=RADIUS/Math.max(o.scale.z,.01);if(p.x>=o.bounds.min.x-rx&&p.x<=o.bounds.max.x+rx&&p.y>=o.bounds.min.y-ry&&p.y<=o.bounds.max.y+ry&&p.z>=o.bounds.min.z-rz&&p.z<=o.bounds.max.z+rz&&(!o.triangles||capsuleHitsTriangles(o.triangles,x,z,foot))){ids.add(o.id);break;}}}return[...ids];
  }
  canStand(x:number,z:number,foot:number):number|null{
    // A physical foot bridges narrow plank joints. Require a supported majority of
    // the capsule footprint rather than one mathematically infinitesimal ray.
    const r=RADIUS*.82,diag=r*.70710678;
    const sampleOffsets=[[0,0],[r,0],[-r,0],[0,r],[0,-r],[diag,diag],[-diag,diag],[diag,-diag],[-diag,-diag]];
    const hits=sampleOffsets.map(([dx,dz])=>this.support(x+dx,z+dz,foot)).filter((h):h is number=>h!==null&&h>=foot-MAX_DROP).sort((a,b)=>a-b);
    if(hits.length<6)return null;const median=hits[Math.floor(hits.length/2)];
    // At a stair intersection the leading foot may meet the next supported
    // tread before most of the footprint reaches it. Try that real tread only
    // within the step limit and with at least two matching contact samples.
    const candidates=[median,...hits.slice().reverse().filter(h=>h>median+.02&&h<=foot+STEP&&hits.filter(v=>Math.abs(v-h)<.04).length>=2)];
    for(const support of candidates)if(hits.filter(h=>Math.abs(h-support)<=STEP+.12).length>=6&&!this.blocks(x,z,support))return support;
    return null;
  }
  safeSpawn(wanted:Vector3):Vector3{
    for(let radius=0;radius<26;radius+=.7){for(let i=0;i<Math.max(1,Math.ceil(radius*9));i++){const angle=i*2.399963229728653,x=wanted.x+Math.cos(angle)*radius,z=wanted.z+Math.sin(angle)*radius;const y=this.support(x,z);if(y!==null&&!this.blocks(x,z,y)&&this.canStand(x,z,y)!==null)return new Vector3(x,y+EYE,z);}}
    throw new Error(`No safe walkable surface near ${wanted.x.toFixed(1)}, ${wanted.z.toFixed(1)}. Choose another destination.`);
  }
}

export class FirstPerson{
  keys=new Set<string>();yaw=0;pitch=0;active=false;paused=true;foot=0;velocityY=0;distanceWalked=0;swimming=false;
  constructor(public camera:PerspectiveCamera,public world:NavigationWorld,private canvas:HTMLCanvasElement,private onPause:()=>void,private toast:(s:string)=>void){
    window.addEventListener('keydown',this.keyDown);window.addEventListener('keyup',this.keyUp);window.addEventListener('blur',this.blur);document.addEventListener('visibilitychange',this.visibility);document.addEventListener('pointerlockchange',this.lockChange);document.addEventListener('pointerlockerror',this.lockError);document.addEventListener('mousemove',this.mouseMove);
  }
  private keyDown=(e:KeyboardEvent)=>{if(e.code==='Escape'&&this.active){e.preventDefault();this.pause();return;}if(this.active&&!this.paused){this.keys.add(e.code);if(['KeyW','KeyA','KeyS','KeyD','KeyZ','KeyQ','Space'].includes(e.code))e.preventDefault();}};
  private keyUp=(e:KeyboardEvent)=>{this.keys.delete(e.code);};
  private blur=()=>{this.keys.clear();if(this.active)this.pause();};
  private visibility=()=>{if(document.hidden)this.blur();};
  private lockChange=()=>{if(document.pointerLockElement!==this.canvas&&this.active){this.paused=true;this.keys.clear();this.onPause();}else if(document.pointerLockElement===this.canvas){this.paused=false;}};
  private lockError=()=>{this.pause();this.toast('Mouse capture was declined. Click Continue walking to try again.');};
  private mouseMove=(e:MouseEvent)=>{if(!this.active||this.paused||document.pointerLockElement!==this.canvas)return;this.yaw-=e.movementX*.002;this.pitch=Math.max(-1.48,Math.min(1.48,this.pitch-e.movementY*.002));this.updateLook();};
  updateLook(){this.camera.quaternion.setFromEuler(new Euler(this.pitch,this.yaw,0,'YXZ'));}
  spawn(location:Vector3,yaw=0){this.camera.position.copy(this.world.safeSpawn(location));this.foot=this.camera.position.y-EYE;this.yaw=yaw;this.pitch=-.06;this.velocityY=0;this.swimming=false;this.updateLook();}
  async resume(){this.active=true;this.keys.clear();try{await this.canvas.requestPointerLock();if(document.pointerLockElement===this.canvas)this.paused=false;}catch{this.lockError();}}
  pause(){this.paused=true;this.keys.clear();if(document.pointerLockElement===this.canvas)document.exitPointerLock();this.onPause();}
  stop(){this.active=false;this.paused=true;this.keys.clear();if(document.pointerLockElement===this.canvas)document.exitPointerLock();}
  update(dt:number){if(!this.active||this.paused)return;
    let x=(this.keys.has('KeyD')?1:0)-(this.keys.has('KeyA')||this.keys.has('KeyQ')?1:0),z=(this.keys.has('KeyS')?1:0)-(this.keys.has('KeyW')||this.keys.has('KeyZ')?1:0);
    const length=Math.hypot(x,z);if(length===0){this.settleEye(dt);return;}x/=length;z/=length;const fast=this.keys.has('ShiftLeft')||this.keys.has('ShiftRight');const speed=this.swimming?(fast?3:1.9):(fast?8.3:3.8);
    const totalX=(x*Math.cos(this.yaw)+z*Math.sin(this.yaw))*speed*dt,totalZ=(-x*Math.sin(this.yaw)+z*Math.cos(this.yaw))*speed*dt;
    const steps=Math.max(1,Math.ceil(Math.hypot(totalX,totalZ)/.16));
    for(let i=0;i<steps;i++){
      const p=this.camera.position,dx=totalX/steps,dz=totalZ/steps;let next=this.world.canStand(p.x+dx,p.z+dz,this.swimming?.6:this.foot);
      if(next!==null){p.x+=dx;p.z+=dz;this.foot=next;this.swimming=false;this.distanceWalked+=Math.hypot(dx,dz);}else if((this.swimming||this.foot<1.2)&&!this.world.blocks(p.x+dx,p.z+dz,-1.07)&&Math.abs(p.x+dx)<650&&Math.abs(p.z+dz)<620&&this.world.support(p.x+dx,p.z+dz,Infinity,true)===null){
        p.x+=dx;p.z+=dz;this.foot=-1.07;this.swimming=true;this.distanceWalked+=Math.hypot(dx,dz);
      }else{
        next=this.world.canStand(p.x+dx,p.z,this.foot);if(next!==null){p.x+=dx;this.foot=next;this.distanceWalked+=Math.abs(dx);}
        next=this.world.canStand(p.x,p.z+dz,this.foot);if(next!==null){p.z+=dz;this.foot=next;this.distanceWalked+=Math.abs(dz);}
      }
    }
    this.settleEye(dt);
  }
  private settleEye(dt:number){const target=this.foot+EYE;
    // Bounded gravity settles descending steps; upward step and swim transitions stay smooth.
    if(this.camera.position.y>target+.02){this.velocityY-=18*dt;this.camera.position.y=Math.max(target,this.camera.position.y+this.velocityY*dt);if(this.camera.position.y===target)this.velocityY=0;}
    else{this.velocityY=0;this.camera.position.y+=(target-this.camera.position.y)*(1-Math.exp(-dt*22));}
  }
  dispose(){window.removeEventListener('keydown',this.keyDown);window.removeEventListener('keyup',this.keyUp);window.removeEventListener('blur',this.blur);document.removeEventListener('visibilitychange',this.visibility);document.removeEventListener('pointerlockchange',this.lockChange);document.removeEventListener('pointerlockerror',this.lockError);document.removeEventListener('mousemove',this.mouseMove);this.stop();}
}
export const controllerProfile={eyeHeight:EYE,bodyRadius:RADIUS,maxStep:STEP,maxSlopeDegrees:45,maxDrop:MAX_DROP,walkSpeed:3.8,runSpeed:8.3,swimSpeed:1.9,fastSwimSpeed:3,swimEyeAboveSea:.65,gravity:18,boundedStep:.16,support:'full exported triangles, layer aware',solidCollision:'source connected-component oriented bounds; exact capsule/triangle contact for nonconvex rails and graded joists; closed-house footprints',water:'deliberate swimming at coast; high decks retain edge safety'};
