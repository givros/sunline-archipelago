"""Arrange supplied reference and read-only source inspection views."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'comparisons/architecture_audit'
FONT='C:/Windows/Fonts/segoeui.ttf'
def font(n):return ImageFont.truetype(FONT,n)
for family,title,reference in [('villa','Coastal architecture | reference and constructed source','reference_villa_crop.png'),('stilt','Overwater houses | reference and constructed source','reference_stilt_crop.png')]:
 W,H=2130,1860;sheet=Image.new('RGB',(W,H),(22,31,37));d=ImageDraw.Draw(sheet)
 d.text((28,17),title,font=font(34),fill=(243,237,215))
 d.text((28,66),'One supplied aerial reference. Front and rear reference views are unavailable.',font=font(22),fill=(178,197,203))
 for col,label in enumerate(['PRIMARY REFERENCE','ISOLATED EDITABLE ASSET','INTEGRATED ENVIRONMENT']):d.text((25+col*705,107),label,font=font(23),fill=(213,229,227))
 for row,view in enumerate(['aerial','front','rear']):
  y=149+row*545
  for col in range(3):
   x=20+col*705;box=(x,y,x+690,y+500);d.rectangle(box,fill=(37,49,57))
   if col==0 and row>0:
    d.text((x+50,y+185),'REFERENCE VIEW UNAVAILABLE',font=font(28),fill=(183,197,197))
    d.text((x+50,y+233),'No side/rear image was supplied.',font=font(23),fill=(150,170,176))
   else:
    path=OUT/reference if col==0 else OUT/f'{family}_{view}_{"isolated" if col==1 else "integrated"}.png'
    image=Image.open(path).convert('RGB');image=ImageOps.contain(image,(690,500));sheet.paste(image,(x+(690-image.width)//2,y+(500-image.height)//2))
   label='Aerial reference crop' if col==0 and row==0 else 'Unseen geometry is interpreted' if col==0 else f'{view.title()} view | matched angle and framing'
   d.text((x+8,y+507),label,font=font(20),fill=(195,213,214))
 d.text((28,1797),'Walls, recessed openings, roof structure, foundations, decks and supports remain individually editable meshes.',font=font(22),fill=(195,213,214))
 sheet.save(OUT/f'{family}_hero_comparison.png')
print('Architecture and stilt hero comparison sheets saved.')
