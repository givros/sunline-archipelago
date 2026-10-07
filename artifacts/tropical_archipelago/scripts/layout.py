"""Shared, reference-traced spatial definition. Blender coordinates: X east, Y north, Z up."""
import math, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
REFERENCE_SIZE = (1448, 1086)
def xy(p): return ((p[0]-724)*.65, (543-p[1])*.82)
def pixel(p): return (p[0]/.65+724,543-p[1]/.82)
ISLANDS = [
 dict(id='REG_NORTHWEST',name='Northpoint',center=[185,43],shore=[[80,55],[99,25],[145,10],[213,1],[261,18],[279,45],[238,70],[154,84],[99,73]],hills=[[187,39,28,63,37]],seed=12),
 dict(id='REG_NORTH',name='Emerald Ridge',center=[590,133],shore=[[449,62],[492,29],[552,22],[603,35],[653,24],[697,53],[737,81],[741,125],[715,167],[701,204],[665,239],[599,247],[538,228],[504,211],[496,173],[467,150],[482,112]],hills=[[585,98,49,70,63],[621,179,35,73,54],[686,80,25,37,40]],seed=23),
 dict(id='REG_NORTHEAST',name='San Aurelio',center=[1198,194],shore=[[1048,142],[1091,100],[1148,68],[1210,80],[1258,56],[1316,75],[1358,128],[1390,174],[1391,226],[1371,261],[1321,283],[1270,273],[1253,308],[1195,346],[1112,328],[1061,291],[1050,237],[1012,203]],hills=[[1227,126,67,93,61],[1314,184,49,55,67],[1106,298,27,37,31]],seed=34),
 dict(id='REG_WEST_ROCK',name='Heron Cay',center=[116,171],shore=[[40,176],[58,148],[91,136],[127,142],[157,150],[190,180],[154,195],[130,213],[79,205]],hills=[[116,169,25,45,28]],seed=45),
 dict(id='REG_WEST_LAGOON',name='Palm Crescent',center=[246,265],shore=[[162,266],[187,238],[197,214],[227,207],[272,220],[300,241],[326,264],[320,288],[285,301],[242,299],[204,294]],hills=[[248,256,17,52,32]],seed=56),
 dict(id='REG_CENTER_CAY',name='Castaway Sand',center=[656,337],shore=[[592,321],[610,305],[661,299],[707,317],[734,341],[715,370],[678,377],[636,366],[601,350]],hills=[[658,338,14,39,25]],seed=67),
 dict(id='REG_WEST_SOUTH',name='Tern Island',center=[111,479],shore=[[39,479],[62,451],[115,434],[157,448],[179,472],[158,494],[139,518],[82,523],[43,507]],hills=[[112,477,23,45,30]],seed=78),
 dict(id='REG_MAIN',name='Porto Sol',center=[360,690],shore=[[35,726],[50,665],[82,622],[120,601],[161,570],[184,548],[221,544],[252,511],[282,492],[328,477],[367,462],[415,470],[460,489],[499,510],[545,541],[578,574],[628,602],[651,643],[682,669],[678,709],[645,739],[662,779],[633,819],[590,841],[527,855],[475,852],[421,873],[369,858],[319,868],[266,851],[214,838],[163,819],[119,784],[71,771]],hills=[[399,580,56,111,83],[526,654,37,87,67],[510,775,30,57,39]],seed=89),
 dict(id='REG_CENTRAL_PALMS',name='Lagoon Junction',center=[1064,500],shore=[[982,497],[1015,473],[1049,446],[1087,462],[1121,491],[1157,519],[1144,544],[1104,564],[1060,557],[1016,542]],hills=[[1069,500,16,56,39]],seed=90),
 dict(id='REG_SOUTHEAST',name='Coral Key',center=[1080,811],shore=[[951,683],[989,656],[1038,647],[1091,673],[1137,710],[1150,754],[1194,787],[1218,834],[1230,877],[1214,908],[1175,940],[1114,951],[1060,962],[999,946],[958,921],[930,884],[900,853],[907,819],[941,796],[951,757],[931,723]],hills=[[1031,723,38,59,67],[1100,820,26,56,62]],seed=101),
]
MAIN_RAIL_PIXELS=[[169,49],[233,42],[287,35],[352,40],[430,47],[503,50],[548,62],[570,87],[552,116],[543,142],[574,163],[640,180],[735,190],[845,207],[962,232],[1051,251],[1115,281],[1160,318],[1167,351],[1132,392],[1072,444],[1000,490],[909,537],[806,578],[704,616],[604,656],[499,696],[440,724],[372,750]]
# Reference S-bend rebuilt as an engineered cubic: the original inferred 10 m
# radius was not negotiable by a 19 m train. This stays within Emerald Ridge.
def bezier_pixels(points,n=55):
 return [[(1-t)**3*points[0][k]+3*(1-t)**2*t*points[1][k]+3*(1-t)*t*t*points[2][k]+t**3*points[3][k] for k in [0,1]] for t in [j/n for j in range(n+1)]]
MAIN_RAIL_TAIL=MAIN_RAIL_PIXELS[12:]
MAIN_RAIL_PIXELS=MAIN_RAIL_PIXELS[:5]+bezier_pixels([[450,47],[605,47],[490,180],[660,180]])+MAIN_RAIL_TAIL
SOUTH_RAIL_PIXELS=[[440,724],[476,706],[513,700],[553,716],[627,755],[718,786],[817,816],[917,844],[1017,864],[1097,866],[1146,845],[1157,814],[1133,775],[1090,729],[1058,700]]
NORTH_SPUR_PIXELS=[[1051,251],[1120,267],[1189,274],[1242,258],[1280,232],[1290,207]]
PLAZAS=[dict(id='PORTO_PLAZA',center=[290,696],radius=[64,44],level=5.0),dict(id='AURELIO_PLAZA',center=[1161,231],radius=[65,31],level=7.0)]
VILLAS=[
 # Main plaza ring, harbor lane and hillside paths, hand-traced from reference.
 [157,698,0,0],[193,646,-.25,1],[247,635,.1,2],[299,647,.15,3],[348,679,-.15,4],[376,721,.7,0],[338,756,0,1],[282,769,.1,2],[227,753,-.2,3],[184,735,.1,4],
 [139,755,.3,1],[221,804,.1,0],[302,815,-.2,2],[393,800,.4,3],[442,748,.6,4],[482,790,.1,1],[538,760,-.2,0],[510,705,.3,2],
 [357,528,-.1,3],[405,515,.1,4],[447,542,.3,1],[510,546,-.2,2],[548,584,.4,0],[601,625,.5,3],[322,574,-.2,1],[387,586,.4,2],
 # Northeastern coastal village.
 [1076,186,.4,1],[1110,186,.1,3],[1134,211,-.1,4],[1092,232,.1,2],[1130,260,.25,0],[1195,259,-.1,1],[1230,239,-.4,2],[1190,204,.2,3],[1151,173,0,0],[1097,154,.5,4],
 # Coral Key woodland villas.
 [1019,686,.25,3],[1078,718,.2,4],[1096,757,.4,2],[1023,822,.1,1],[1047,874,-.1,0],[1100,885,.1,3],[1129,841,.4,4],[1005,782,-.3,2],
 # Smaller islands, hillside cabins.
 [568,60,.2,4],[682,65,-.4,3],[696,123,.2,2],[591,187,0,1],[240,261,.2,4],[180,53,.2,3],
]
for _index,_point in {18:[510,719],31:[1130,250],32:[1193,255],34:[1179,184],38:[1060,730],39:[1092,761],41:[1047,886],43:[1123,837],45:[572,54],50:[180,67]}.items():VILLAS[_index-1][0:2]=_point
STILT_DISTRICTS=[
 dict(id='STILT_NORTHWEST',hub=[409,142],shore=[492,134],houses=[[379,103],[408,99],[444,115],[458,143],[439,171],[397,177],[377,151],[364,125],[405,70]],level=3.2),
 dict(id='STILT_NORTH',hub=[773,71],shore=[690,82],houses=[[728,34],[762,40],[797,49],[823,69],[849,84],[877,79]],level=3.2),
 dict(id='STILT_WEST',hub=[239,298],shore=[243,261],houses=[[171,304],[201,323],[240,336],[278,323],[310,304],[316,238]],level=3.2),
 dict(id='STILT_LAGOON',hub=[907,462],shore=[1039,500],houses=[[823,398],[873,385],[942,389],[992,416],[961,439],[885,431],[837,451],[784,439],[747,465],[774,507],[836,506],[880,515]],level=3.2),
 dict(id='STILT_CORAL',hub=[1291,795],shore=[1166,811],houses=[[1252,758],[1299,750],[1343,783],[1353,816],[1323,845],[1300,876],[1278,908],[1222,950],[1248,978]],level=3.2),
 dict(id='STILT_CORAL_NORTH',hub=[1161,681],shore=[1093,701],houses=[[1047,624],[1122,629],[1228,671],[1266,701]],level=3.2),
]
DOCKS=[
 dict(id='DOCK_PORTO_MAIN',points=[[384,811],[410,906],[423,956]],width=6.0),
 dict(id='DOCK_PORTO_CROSS',points=[[363,946],[452,918]],width=4.8),
 dict(id='DOCK_PORTO_WEST',points=[[135,818],[222,880],[179,935]],width=4),
 dict(id='DOCK_PORTO_FISH',points=[[46,747],[50,804]],width=3.2),
 dict(id='DOCK_PORTO_EAST',points=[[469,819],[492,879]],width=3.5),
 dict(id='DOCK_TERN',points=[[152,484],[234,531],[173,570]],width=3),
 dict(id='DOCK_PALM',points=[[299,257],[379,252]],width=3),
 dict(id='DOCK_AURELIO',points=[[1191,330],[1230,395]],width=4),
 dict(id='DOCK_AURELIO_EAST',points=[[1334,315],[1428,352]],width=4),
 dict(id='DOCK_EMERALD',points=[[506,226],[475,245]],width=2.8),
 dict(id='DOCK_TERN_SHORE',points=[[234,531],[259,548]],width=3),
]
BOATS=[
 [95, 372, -0.2, 'yacht'],
 [1393, 463, -0.4, 'yacht'],
 [700, 979, 0.45, 'speed'],
 [167, 882, 1.1, 'speed'],
 [124, 907, 1.5, 'taxi'],
 [196.33234112079333, 923.6097635408728, 1.0, 'fishing'],
 [218.57829402043274, 897.2482701743522, 1.1, 'yacht'],
 [434.5584247295673, 950.1599448599467, 0, 'utility'],
 [395, 886, 1.4, 'fishing'],
 [477, 863, 1.1, 'utility'],
 [326, 882, 0.1, 'fishing'],
 [73, 797, 0, 'utility'],
 [277, 130, -0.3, 'speed'],
 [850, 334, 1.45, 'sail'],
 [582, 437, 1.35, 'sail'],
 [912, 31, 1.4, 'sail'],
 [893, 121, 1.2, 'sail'],
 [1284, 389, 1.2, 'fishing'],
 [1387, 577, -0.3, 'taxi'],
 [1369, 364, 0.1, 'utility'],
 [943, 530, -0.3, 'speed'],
 [1377, 838, 1.6, 'fishing'],
 [815, 530, 0, 'utility'],
 [488.5589036207933, 243.6765039955697, 0.4, 'utility'],
 [351, 267, 0, 'fishing'],
 [172.00302358774036, 563.9039874193145, 0.5, 'fishing'],
 [1295, 703, 0.4, 'speed'],
 [1264.4811448317307, 935.759444073933, 0.4, 'utility']]
def catmull(points,spacing=2.0):
 out=[]
 for i in range(len(points)-1):
  p0=points[max(i-1,0)];p1=points[i];p2=points[i+1];p3=points[min(i+2,len(points)-1)]
  steps=max(3,int(math.dist(p1,p2)/spacing))
  for j in range(steps):
   t=j/steps
   out.append(tuple(.5*((2*p1[k])+(-p0[k]+p2[k])*t+(2*p0[k]-5*p1[k]+4*p2[k]-p3[k])*t*t+(-p0[k]+3*p1[k]-3*p2[k]+p3[k])*t*t*t) for k in range(len(p1))))
 out.append(tuple(points[-1]));return out
def rail_world(points): return catmull([(*xy(p),18.0) for p in points],2.0)
def engineered_main():
 pre=rail_world(MAIN_RAIL_PIXELS[:5]+[[450,47]])
 bend=[(*xy(p),18.) for p in bezier_pixels([[450,47],[605,47],[490,180],[660,180]],100)]
 post=rail_world([[660,180],[685,180],[710,184]]+MAIN_RAIL_TAIL)
 return pre[:-1]+bend[:-1]+post
RAILS=[dict(id='RAIL_MAIN',name='Northpoint – Porto Sol',points=engineered_main(),open=True),dict(id='RAIL_SOUTH',name='Porto Sol – Coral Key',points=rail_world(SOUTH_RAIL_PIXELS),open=True),dict(id='RAIL_SPUR',name='San Aurelio tunnel branch',points=rail_world(NORTH_SPUR_PIXELS),open=True)]
def distance_route(x,y,points):
 return min(math.hypot(x-p[0],y-p[1]) for p in points)
def write_spec():
 spec=dict(title='The Sunline Archipelago',units='meters',axes='Blender: X east, Y north, Z up. Runtime: x, z, -y.',bounds=[[-520,-490,-20],[520,490,110]],reference=dict(file='references/primary_layout.png',pixels=list(REFERENCE_SIZE),scale_x=.65,scale_y=.82,priority='Primary layout target'),islands=ISLANDS,rail_routes=RAILS,rail_gauge=1.435,track_offsets=[-2.1,2.1],train_car_spacing=19.0,plazas=PLAZAS,villas=VILLAS,stilt_districts=STILT_DISTRICTS,docks=DOCKS,boats=BOATS,camera=dict(position=[0,-900,1180],target=[0,0,0],ortho_scale=965),navigation=dict(eye_height=1.72,player_radius=.32,step_height=.5,slope_limit=45,mode='First-person land/boardwalk walking plus swimming and island arrival points; closed building interiors.',spawn=[*xy([286,703]),6.9]),explicit_requirements=['Reference-traced multi-island composition','Continuous operational railway','Detailed villas and overwater houses','Detailed varied boats','Reefs and shallow turquoise water','Local first-person exploration'],inferred_choices=['Ten visible landforms derived from reference','Metric dimensions estimated from 19 m train car spacing','Two main shuttle lines and a northeast tunnel branch','Closed exterior architecture, no furnished interiors requested'])
 (ROOT/'scene_spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
 spec['train_car_spacing']=19
 spec['navigation']['spawn']=[*xy([286,716]),6.82]
 destinations=[('porto','Porto Sol',[286,716],5.1,[369,657]),('aurelio','San Aurelio',[1164,236],7.1,[1196,209]),('lagoon','Lagoon Village',[922,463],3.2,[907,462]),('coral','Coral Key',[1040,917],4,[1064,812]),('emerald','Emerald Ridge',[533,210],5,[590,140]),('northpoint','Northpoint',[152,61],5,[184,42]),('palm','Palm Crescent',[231,292],3.2,[247,264]),('heron','Heron Cay',[81,196],3,[118,172]),('tern','Tern Island',[82,503],3,[113,478]),('castaway','Castaway Sand',[697,352],3,[654,338])]
 spec['viewer']={'landmarks':[dict(id=id,label=label,spawn=[*xy(p),h+1.72],target=[*xy(target),h+6]) for id,label,p,h,target in destinations]}
 (ROOT/'scene_spec.json').write_text(json.dumps(spec,indent=2),encoding='utf-8')
 return spec
if __name__=='__main__':write_spec()

