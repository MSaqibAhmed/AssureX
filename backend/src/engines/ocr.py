"""Bounded OCR with explicit unknown values and source provenance."""
import io, re
from pathlib import Path
import cv2, numpy as np, pytesseract
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pdf2image import convert_from_bytes

PATTERNS = {
 'purchase_date':r'(?:purchase date|date)\s*[:#]?\s*([\d/-]{8,10})',
 'invoice_number':r'\binvoice(?:[ \t]+(?:number|no\.?))?[ \t]*[:#>][ \t]*([\w/-]+)',
 'product':r'product\s*:\s*([^\n]+)',
 'model':r'model\s*:\s*([^\n]+)',
 'serial':r'serial\s*(?:number|no\.?|#)?\s*[:#]?\s*([\w-]+)',
 'retailer':r'retailer\s*:\s*([^\n]+)',
 'amount':r'\b(?:total[ \t]+amount|grand[ \t]+total|amount|total)(?:[ \t]*\([A-Z]{3}\))?[ \t]*:?[ \t]*[$]?[ \t]*(\d[\d,]*(?:\.\d{2})?)',
 'warranty_duration':r'warranty[ \t]*(?:duration|period)?[ \t]*:?[ \t]*(\d+)[ \t]*months?',
}

def validate_document(data: bytes, name: str, mime: str, max_bytes=10*1024*1024, page_cap=10):
    if len(data)>max_bytes:
        raise OverflowError('Upload too large')
    ext=Path(name).suffix.lower()
    if ext=='.pdf' and mime=='application/pdf' and data.startswith(b'%PDF-'):
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('Encrypted PDF is not supported')
        if not 1 <= len(reader.pages) <= page_cap:
            raise ValueError('PDF page limit exceeded')
        # Reject active content and embedded files, not just extension mismatches.
        root=reader.trailer['/Root']
        names=root.get('/Names',{})
        if hasattr(names,'get_object'): names=names.get_object()
        if any(k in root for k in ['/OpenAction','/AA']) or any(k in names for k in ['/EmbeddedFiles','/JavaScript']):
            raise ValueError('Active or embedded PDF content is not supported')
        for page in reader.pages:
            if '/AA' in page: raise ValueError('Page actions are not supported')
            for ref in page.get('/Annots',[]):
                annotation=ref.get_object()
                if any(k in annotation for k in ['/A','/AA','/FS']):
                    raise ValueError('Annotation actions and attachments are not supported')
        return
    expected={'.png':('image/png','PNG'),'.jpg':('image/jpeg','JPEG'),'.jpeg':('image/jpeg','JPEG')}
    if ext not in expected or expected[ext][0]!=mime:
        raise ValueError('Unsupported document type')
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != expected[ext][1] or image.width*image.height>25_000_000:
                raise ValueError('Invalid image content or dimensions')
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError('Invalid image content') from exc

def prepare(image):
    gray=cv2.cvtColor(np.asarray(image.convert('RGB')),cv2.COLOR_RGB2GRAY)
    gray=cv2.createCLAHE(clipLimit=2,tileGridSize=(8,8)).apply(gray)
    binary=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)[1]
    coords=np.column_stack(np.where(binary>0))
    if len(coords)>10:
        angle=cv2.minAreaRect(coords[:,::-1].astype('float32'))[-1]
        if angle>45: angle-=90
        if abs(angle)<20:
            h,w=gray.shape
            gray=cv2.warpAffine(gray,cv2.getRotationMatrix2D((w/2,h/2),angle,1),(w,h),borderValue=255)
    return Image.fromarray(gray)

def normalize(field,raw):
    if raw is None: return None
    if field=='purchase_date':
        from datetime import date
        try: return date.fromisoformat(raw).isoformat()
        except ValueError:
            match=re.fullmatch(r'(\d{2})[-/](\d{2})[-/](\d{4})',raw)
            if match:
                first,second,year=map(int,match.groups())
                # Accept only unambiguous day/month order or equal day/month.
                if first==second or first>12:
                    try: return date(year,second,first).isoformat()
                    except ValueError: pass
            return None
    if field=='amount':
        from decimal import Decimal, InvalidOperation
        try:
            amount=Decimal(raw.replace(',',''))
            return str(amount) if amount.is_finite() and amount>=0 else None
        except InvalidOperation: return None
    return raw.strip().upper() if field=='serial' else raw.strip()

def extract(data,mime,page_cap=10,timeout=8):
    pages=[]
    if mime=='application/pdf':
        reader=PdfReader(io.BytesIO(data))
        if reader.is_encrypted or len(reader.pages)>page_cap: raise ValueError('Unsupported PDF')
        for i,page in enumerate(reader.pages):
            text=page.extract_text() or ''
            if text.strip(): pages.append((i+1,text,None))
            else:
                image=convert_from_bytes(data,first_page=i+1,last_page=i+1,dpi=150,timeout=timeout)[0]
                pages.append((i+1,None,image))
    else: pages=[(1,None,Image.open(io.BytesIO(data)))]
    results={}
    for page,text,image in pages:
        words=None
        spans=[]
        if text is None:
            words=pytesseract.image_to_data(prepare(image),config='--psm 6',output_type=pytesseract.Output.DICT,timeout=timeout)
            # Tesseract restarts line numbers in each paragraph/block. Grouping
            # by line_num alone joins unrelated fields into a single long line.
            lines={}
            for j,word in enumerate(words['text']):
                if not word.strip(): continue
                key=(words['block_num'][j],words['par_num'][j],words['line_num'][j])
                lines.setdefault(key,[]).append(j)
            text=''
            for line in lines.values():
                for j in line:
                    word=words['text'][j]
                    spans.append((len(text),len(text)+len(word),j))
                    text+=word+' '
                text=text.rstrip()+'\n'
        for field,pattern in PATTERNS.items():
            match=re.search(pattern,text,re.I)
            if field=='amount':
                totals=list(re.finditer(r'\b(?:total[ \t]+amount|grand[ \t]+total)(?:[ \t]*\([A-Z]{3}\))?[ \t]*:?[ \t]*(\d[\d,]*(?:\.\d{2})?)',text,re.I))
                if totals: match=totals[-1]
            if not match and field=='product':
                match=re.search(r'\bitem description[^\n]*\n[ \t]*(?:\d+[ \t]+)?([^\n]+)',text,re.I)
            if not match and field=='model':
                # Parenthesized alphanumeric model codes, not free-text guesses.
                match=re.search(r'\(([A-Z]{1,8}-[A-Z0-9]*\d[A-Z0-9-]*)\)',text)
            if match and field not in results:
                raw=match.group(1).strip(); bbox=[]; confidence=None
                if words:
                    start,end=match.span(1)
                    indices=[j for a,b,j in spans if a<end and b>start]
                    if indices:
                        bbox=[min(words['left'][j] for j in indices),min(words['top'][j] for j in indices),
                              max(words['left'][j]+words['width'][j] for j in indices),max(words['top'][j]+words['height'][j] for j in indices)]
                        confidence=min(float(words['conf'][j]) for j in indices)/100
                results[field]={'field':field,'raw_value':raw,'normalized_value':normalize(field,raw),'confidence':confidence,'bbox':bbox,'page':page}
        if image is not None and 'retailer' not in results:
            # Header pass preserves separated brand lines that dense layout OCR can lose.
            header=pytesseract.image_to_data(image.crop((0,0,image.width//2,int(image.height*.16))),output_type=pytesseract.Output.DICT,timeout=timeout)
            tokens=[j for j,w in enumerate(header['text']) if w.strip() and float(header['conf'][j])>=50]
            lines={}
            for j in tokens:
                key=(header['block_num'][j],header['par_num'][j],header['line_num'][j])
                lines.setdefault(key,[]).append(j)
            selected=[]
            for indices in list(lines.values())[:2]:
                value=' '.join(header['text'][j] for j in indices)
                if re.fullmatch(r'[A-Za-z][A-Za-z &.\'-]{1,60}',value) and not re.search(r'invoice|receipt|purchase|date|serial|product|model',value,re.I): selected+=indices
            if selected:
                raw=' '.join(header['text'][j] for j in selected)
                results['retailer']={'field':'retailer','raw_value':raw,'normalized_value':raw,'confidence':min(float(header['conf'][j]) for j in selected)/100,'bbox':[0,0,image.width//2,int(image.height*.16)],'page':page}
    return [results.get(field,{'field':field,'raw_value':None,'normalized_value':None,'confidence':None,'bbox':[],'page':None}) for field in PATTERNS]
