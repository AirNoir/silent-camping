"""Assemble the four actual Blender renders into a review contact sheet."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parent.parent
dest=ROOT/'assets/source/camper_sculpt'
font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',26)
small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
sheet=Image.new('RGB',(1800,640),'#e9e5dc')
d=ImageDraw.Draw(sheet)
d.text((28,17),'MALE CAMPER | sculpted model / four views',font=font,fill='#493d34')
for i,(key,label) in enumerate([('front','FRONT'),('q34','3/4'),('side','SIDE'),('back','BACK')]):
    im=Image.open(dest/f'male_{key}.png').convert('RGB').resize((450,550),Image.Resampling.LANCZOS)
    sheet.paste(im,(i*450,61))
    d.text((i*450+22,612),label,font=small,fill='#493d34')
sheet.save(dest/'male_turnaround.png')

# The supplied reference is shown separately, with no retouching or generated detail.
ref=Image.open('/Users/a01-0220-0077/Downloads/森林露營角色設定板.png').convert('RGB').crop((27,75,153,345))
model=Image.open(dest/'male_front.png').convert('RGB')
compare=Image.new('RGB',(1050,1100),'#e9e5dc')
d=ImageDraw.Draw(compare)
d.text((32,22),'SUPPLIED REFERENCE',font=font,fill='#493d34')
d.text((545,22),'ACTUAL 3D SCULPT',font=font,fill='#493d34')
ref=ref.resize((467,1000),Image.Resampling.LANCZOS)
compare.paste(ref,(23,78))
compare.paste(model.resize((818,1000),Image.Resampling.LANCZOS).crop((151,0,669,1000)),(527,78))
compare.save(dest/'reference_compare.png')
