"""Assemble source-only visual evidence; reference excerpts are unretouched crops."""
from PIL import Image,ImageDraw,ImageFont,ImageOps
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REF=Image.open(ROOT/'references'/'primary_layout.png').convert('RGB')
FONT='C:/Windows/Fonts/arial.ttf'
title=ImageFont.truetype(FONT,31);body=ImageFont.truetype(FONT,21);small=ImageFont.truetype(FONT,17)
fleet=Image.open(ROOT/'renders'/'vehicle_details'/'marine_fleet.png').convert('RGB')
def opened(path):return Image.open(ROOT/'renders'/path).convert('RGB')
rows=[
 ('SUNLINE PASSENGER TRAIN',REF.crop((736,164,976,266)),opened('vehicle_details/train_front_detail.png'),opened('train_validation/upper_train_front.png'),
  'White/blue carriages follow the upper stone viaduct.',
  'Nose, glazing, doors, roof equipment and wheel assemblies.',
  'Rail contact and 14-car / 28-bogie articulation validated.'),
 ('PORTO YACHT BERTH',REF.crop((137,827,249,955)),fleet.crop((354,183,772,390)),opened('marine_validation/moored_yacht_final_berth.png'),
  'Actual harbor crop from the primary reference image.',
  'Modeled trawler-style yacht; the reference yacht is sleeker.',
  'Same editable family in scene; hull clears the west pier by 0.93 m.'),
 ('LAGOON SAILBOAT',REF.crop((806,279,876,360)),fleet.crop((528,464,851,758)),opened('marine_validation/lagoon_sailboat_detail.png'),
  'Actual lagoon sailboat crop from the one provided image.',
  'Shaped hull and rigging; sails raised versus the reference berth.',
  'Integrated source view retains the lagoon placement and heading.'),
]
W,H=1860,1690;canvas=Image.new('RGB',(W,H),(18,31,38));draw=ImageDraw.Draw(canvas)
draw.text((30,20),'MARINE & RAIL — SOURCE / REFERENCE REVIEW',font=title,fill=(238,240,232))
draw.text((30,65),'Reference excerpts are unretouched. Only one reference viewing angle is available; unseen reference views are unavailable.',font=body,fill=(181,201,205))
for j,label in enumerate(['PRIMARY REFERENCE · VISIBLE CROP','EDITABLE SOURCE · ISOLATED PROTOTYPE','EDITABLE SOURCE · INTEGRATED INSPECTION']):
    draw.text((30+j*610,108),label,font=small,fill=(226,200,147))
for row,(name,ref,isolated,integrated,c1,c2,c3) in enumerate(rows):
    y=151+row*497
    draw.text((30,y),name,font=body,fill=(238,240,232))
    for col,(im,caption) in enumerate(zip([ref,isolated,integrated],[c1,c2,c3])):
        x=30+col*610
        fitted=ImageOps.contain(im,(586,370),Image.Resampling.LANCZOS)
        canvas.paste((27,53,62),(x,y+34,x+586,y+404))
        canvas.paste(fitted,(x+(586-fitted.width)//2,y+34+(370-fitted.height)//2))
        # Explicit captions stay inside each panel without truncation.
        words=caption.split();line='';yy=y+413
        for word in words:
            trial=(line+' '+word).strip()
            if draw.textlength(trial,font=small)>580:
                draw.text((x,yy),line,font=small,fill=(193,211,213));yy+=23;line=word
            else:line=trial
        draw.text((x,yy),line,font=small,fill=(193,211,213))
draw.text((30,1650),'Prototype and integrated cameras inspect construction. They are not claimed to reproduce an unavailable reference close-up.',font=small,fill=(181,201,205))
path=ROOT/'renders'/'marine_validation'/'marine_rail_hero_reference_sheet.png';canvas.save(path)
print(path)
