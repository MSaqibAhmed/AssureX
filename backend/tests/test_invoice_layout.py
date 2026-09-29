from io import BytesIO
from reportlab.pdfgen.canvas import Canvas
from src.engines.ocr import extract, normalize

def test_invoice_table_labels_and_no_title_as_invoice_id():
    output=BytesIO(); canvas=Canvas(output)
    lines=['SALES INVOICE','Invoice No : TEST-908','Purchase Date : 01-01-2026',
        'Item Description Model Qty Unit Price Total','Example Device Z9','(ZX-900B)',
        'Subtotal 123,456','Total Amount (PKR) 123,456','Warranty Period : 18 Months']
    for i,line in enumerate(lines): canvas.drawString(30,800-i*30,line)
    canvas.save()
    fields={f['field']:f['normalized_value'] for f in extract(output.getvalue(),'application/pdf')}
    assert fields['invoice_number']=='TEST-908'
    assert fields['purchase_date']=='2026-01-01'
    assert fields['product']=='Example Device Z9'
    assert fields['model']=='ZX-900B'
    assert fields['amount']=='123456'
    assert fields['warranty_duration']=='18'
    assert fields['serial'] is None

def test_dates_remain_conservative():
    assert normalize('purchase_date','01-01-2026')=='2026-01-01'
    assert normalize('purchase_date','28/09/2026')=='2026-09-28'
    assert normalize('purchase_date','03/04/2026') is None
    assert normalize('purchase_date','31/02/2026') is None
