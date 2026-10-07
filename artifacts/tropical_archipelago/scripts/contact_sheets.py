import sys
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
label=sys.argv[1] if len(sys.argv)>1 else 'pass_01'
names=['overview','plan','porto_village','church_approach','lagoon_boardwalk','sunline_viaduct','working_harbor','aurelio_arrival','coral_overwater']
sheet=Image.new('RGB',(1920,1536),'#123941');d=ImageDraw.Draw(sheet)
for i,name in enumerate(names):
 p=ROOT/'renders'/f'{label}_{name}.png'
 if not p.exists():continue
 im=Image.open(p).convert('RGB');im.thumbnail((640,480));x=(i%3)*640;y=(i//3)*512;sheet.paste(im,(x,y+32));d.text((x+14,y+10),name.replace('_',' ').upper(),fill='#f5e9ca')
sheet.save(ROOT/'comparisons'/f'{label}_nine_views.png')
# The grid comparison uses only the one supplied reference, never fabricated reverse views.
ref=Image.open(ROOT/'references/primary_layout.png').convert('RGB');current=Image.open(ROOT/'renders'/f'{label}_overview.png').convert('RGB').resize(ref.size)
for im in [ref,current]:
 dr=ImageDraw.Draw(im)
 for j in [1,2]:
  dr.line([(1448*j/3,0),(1448*j/3,1086)],fill='#f8e5a7',width=2);dr.line([(0,1086*j/3),(1448,1086*j/3)],fill='#f8e5a7',width=2)
grid=Image.new('RGB',(2896,1122),'#123941');grid.paste(ref,(0,36));grid.paste(current,(1448,36));dr=ImageDraw.Draw(grid);dr.text((14,12),'PRIMARY REFERENCE • MATCHED 3 × 3 GRID',fill='white');dr.text((1462,12),label.upper()+' • ACTUAL BLENDER GEOMETRY',fill='white');grid.save(ROOT/'comparisons'/f'{label}_reference_grid.png')
