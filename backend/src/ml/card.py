from PIL import Image, ImageDraw, ImageFont
from src.ml.features import build_features

def render_card(facts, variant=0):
    features = build_features(facts)
    image = Image.new('RGB',(448,448),'white')
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=14)
    draw.text((12,8),'CLAIM FACTS',fill='black',font=font)
    for i,(key,value) in enumerate(features.items()):
        # Every feature has a fixed row; variants change only a small horizontal offset.
        draw.text((12 + variant % 2, 32+i*22),f'{key}: {value}',fill='black',font=font)
    return image
