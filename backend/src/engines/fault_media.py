"""Fault evidence is separate from invoice OCR and summary-card classification."""
from pathlib import Path


def validate_video(data, name, mime, max_bytes):
    if len(data) > max_bytes:
        raise OverflowError('Upload too large')
    if Path(name).suffix.lower() != '.mp4' or mime != 'video/mp4':
        raise ValueError('Only MP4 fault videos are supported')
    # Validate the complete ISO BMFF box envelope, not just a renamed extension.
    offset=0; boxes=[]
    while offset < len(data):
        if len(data)-offset < 8: raise ValueError('Truncated MP4')
        size=int.from_bytes(data[offset:offset+4],'big'); kind=data[offset+4:offset+8]
        header=8
        if size==1:
            if len(data)-offset < 16: raise ValueError('Truncated MP4')
            size=int.from_bytes(data[offset+8:offset+16],'big'); header=16
        elif size==0: size=len(data)-offset
        if size < header or offset+size > len(data): raise ValueError('Invalid MP4 box')
        boxes.append(kind); offset+=size
    if not boxes or boxes[0]!=b'ftyp' or not {b'moov',b'mdat'}.issubset(boxes):
        raise ValueError('Invalid MP4 container')


def media_review(document_type):
    if document_type=='fault_video':
        return {'status':'manual_review','message':'Fault video requires human review; no automated video diagnosis was performed.'}
    return {'status':'unavailable','message':'Fault image saved. A dedicated fault-image model must be configured before AI detection is available; human review is required.'}
