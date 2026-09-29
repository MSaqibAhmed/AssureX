import io,json,shutil,time
from pathlib import Path
import pytest
from PIL import Image,ImageDraw,ImageFont,ImageFilter
from src.engines.ocr import extract,validate_document

def receipt_image():
    image=Image.new('RGB',(1600,1100),'white')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',40)
    draw=ImageDraw.Draw(image)
    lines=['Purchase date: 2026-01-10','Invoice: INV-42','Product: Phone','Model: M1',
        'Serial: AB123','Retailer: Sample Store','Amount: 899.00','Warranty: 12 months']
    for i,line in enumerate(lines): draw.text((100,100+i*100),line,font=font,fill='black')
    return image

def test_real_tesseract_clean_rotated_blurry():
    if not shutil.which('tesseract'): pytest.skip('Tesseract executable required')
    original=receipt_image()
    expected={'purchase_date':'2026-01-10','invoice_number':'INV-42','product':'Phone','model':'M1',
        'serial':'AB123','retailer':'Sample Store','amount':'899.00','warranty_duration':'12'}
    results={}
    for name,image in [('clean',original),('rotated',original.rotate(7,expand=True,fillcolor='white')),
                       ('blurry',original.filter(ImageFilter.GaussianBlur(1.2)))]:
        data=io.BytesIO(); image.save(data,format='PNG')
        validate_document(data.getvalue(),name+'.png','image/png')
        started=time.perf_counter()
        fields={f['field']:f['normalized_value'] for f in extract(data.getvalue(),'image/png')}
        matches=sum(fields[k]==v for k,v in expected.items())
        results[name]={'correct_fields':matches,'total_fields':8,'fields':fields,'elapsed_ms':(time.perf_counter()-started)*1000}
    Path('reports/ocr-images.json').write_text(json.dumps(results,indent=2))
    assert all(r['correct_fields']>=7 for r in results.values()), results
