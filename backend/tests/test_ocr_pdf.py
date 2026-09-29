from io import BytesIO
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas
import pytest
from src.engines.ocr import extract,validate_document

def test_text_pdf_extracts_eight_fields_without_tesseract():
    output=BytesIO(); canvas=Canvas(output)
    for i,line in enumerate(['Purchase date: 2026-01-10','Invoice: INV-42','Product: Phone','Model: M1',
        'Serial: AB123','Retailer: Sample Store','Amount: 899.00','Warranty: 12 months']):
        canvas.drawString(30,800-i*30,line)
    canvas.save(); data=output.getvalue()
    validate_document(data,'receipt.pdf','application/pdf')
    fields={f['field']:f for f in extract(data,'application/pdf')}
    assert len(fields)==8
    assert all(f['normalized_value'] is not None for f in fields.values())
    assert fields['serial']['normalized_value']=='AB123'
    assert all(f['page']==1 for f in fields.values())

def test_encrypted_and_page_capped_pdf_denied():
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.encrypt('secret')
    output=BytesIO(); writer.write(output)
    with pytest.raises(ValueError): validate_document(output.getvalue(),'x.pdf','application/pdf')
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100); writer.add_blank_page(width=100,height=100)
    output=BytesIO(); writer.write(output)
    with pytest.raises(ValueError): validate_document(output.getvalue(),'x.pdf','application/pdf',page_cap=1)

def test_pdf_javascript_name_tree_is_denied():
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100)
    writer.add_js('app.alert("not allowed")')
    output=BytesIO(); writer.write(output)
    with pytest.raises(ValueError): validate_document(output.getvalue(),'x.pdf','application/pdf')

def test_pdf_annotation_launch_action_is_denied():
    from pypdf.generic import DictionaryObject,NameObject,TextStringObject,ArrayObject
    writer=PdfWriter(); page=writer.add_blank_page(width=100,height=100)
    action=DictionaryObject({NameObject('/S'):NameObject('/Launch'),NameObject('/F'):TextStringObject('unsafe.exe')})
    page[NameObject('/Annots')]=ArrayObject([DictionaryObject({NameObject('/A'):action})])
    output=BytesIO(); writer.write(output)
    with pytest.raises(ValueError): validate_document(output.getvalue(),'x.pdf','application/pdf')
