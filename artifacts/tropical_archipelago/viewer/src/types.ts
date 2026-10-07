export interface AttributeRecord { offset:number; count:number; itemSize:number }
export interface GeometryRecord { id:number; hash:string; position:AttributeRecord; normal:AttributeRecord; uv?:AttributeRecord; color?:AttributeRecord; groups:{start:number;count:number;materialIndex:number}[]; materials:number[];triangles:number;collisionBoxes?:number[][][];collisionOBBs?:{matrix:number[];bounds:number[][]}[] }
export interface ObjectRecord { id:string; geometry:number; matrix:number[]; dynamic_root?:string;properties:Record<string,unknown> }
export interface RootRecord {id:string;matrix:number[];properties:Record<string,unknown>}
export interface MaterialRecord { id:number;name:string;color:number[];roughness:number;metalness:number;opacity:number;doubleSide:boolean;role:string;map?:string;map_sha256?:string }
export interface SceneData { schema:string;source_sha256:string;geometries:GeometryRecord[];objects:ObjectRecord[];materials:MaterialRecord[];dynamic_roots:RootRecord[];lighting?:{suns:{name:string;color:number[];energy:number;direction:number[];angular_diameter:number}[]};spec:Record<string,any>;stats:Record<string,any> }
export interface Landmark {id:string;label:string;position:[number,number,number];target?:[number,number,number];yaw?:number}
export interface Diagnostic { phase:string; backend:string|null; source:string|null; adapter:unknown; timings:Record<string,number>; errors:string[]; frames:number; frameTimes:number[]; cpuTimes:number[]; objects:number;triangles:number;drawCalls:number;ready:boolean }
