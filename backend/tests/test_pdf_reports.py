from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from pypdf import PdfReader
from src.services.pdf_reports import claim_report


def report_data():
    stamp = datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc)
    claim = {'_id': 'sample-claim', 'public_claim_id': 'AX-SAMPLE-REPORT'}
    revision = {'_id': 'revision-1', 'revision_number': 1, 'submitted_at': stamp, 'policy_version_id': 'electronics-1.0',
        'report_snapshot': {'product': {'name': 'Example laptop', 'brand': 'Example', 'model': 'Notebook 14', 'category': 'electronics', 'serial': 'SAMPLE-001', 'retailer': 'Example retailer', 'amount': '899.00'}, 'warranty': {'provider': 'Example warranty provider', 'start_date': '2026-01-15', 'expiry_date': '2027-01-14'}, 'documents': [{'_id':'evidence-1','name':'example-receipt.pdf','type':'receipt','mime':'application/pdf','size':24000,'sha256':'c'*64}]},
        'policy': {'coverage_months': 12, 'reporting_days': 30, 'grace_days': 0, 'required_documents': ['receipt', 'serial_photo'], 'covered_fault_categories': ['power'], 'excluded_damage': ['liquid'], 'require_authorized_repairs': True},
        'facts_json': {'product_category': 'electronics', 'purchase_date': '2026-01-15', 'serial': 'SAMPLE-001', 'invoice_number': 'INV-001', 'fault_date': '2026-09-20', 'fault_category': 'power', 'damage_type': 'none', 'description': 'Sample data for design preview only. Device does not power on after charging.', 'document_types': ['receipt', 'serial_photo'], 'evidence_ids': ['evidence-1', 'evidence-2'], 'missing_document_count': 0, 'unverified_evidence_fields': [], 'evidence_contradictions': [], 'contradiction_count': 0, 'duplicate_signal': False, 'serial_status': 'match', 'repair_count': 0, 'authorization_status': 'authorized', 'ocr_fields': [{'field':'serial','normalized_value':'SAMPLE-001','confidence':.98,'corrected':False}]}}
    evaluation = {'_id': 'evaluation-1', 'completed_at': stamp, 'recommendation': 'Manual Review Required', 'reasons': ['Automated assessment completed. A human reviewer must confirm the evidence and decision.'], 'predictions': {'python': {'valid': .85, 'invalid': .05, 'manual_review': .1}, 'gtm': {'valid': .8, 'invalid': .05, 'manual_review': .15}}, 'comparison': {'status': 'Strong Match', 'difference': .05}, 'rule_results': [{'rule_id':'coverage','status':'PASS','severity':'info','verified':True,'explanation':'The reported fault date falls inside the policy coverage window.','facts_used':{'purchase':'2026-01-15','fault':'2026-09-20'},'evidence_ids':['evidence-1']}], 'versions': {'python':'python-1.0','gtm':'gtm-1.0','policy':'electronics-1.0'}, 'input_hash':'a'*64, 'evaluation_input_version_hash':'b'*64}
    review = {'_id':'review-1','reviewer_id':'sample-reviewer','after':'Approved','action':'approve','timestamp':stamp,'reason':'Sample decision only. Purchase evidence, serial number and reported fault were reviewed.'}
    return claim, revision, evaluation, review


def test_report_preserves_snapshot_and_embeds_logo():
    data = report_data()
    original = deepcopy(data)
    pdf = PdfReader(BytesIO(claim_report(*data)))
    text = '\n'.join(p.extract_text() for p in pdf.pages)
    assert 'Example laptop' in text and '85.0%' in text
    assert 'example-receipt.pdf' in text
    assert 'Approved' in text and 'sample-reviewer' in text
    assert 'input' in text.lower() and 'evidence-1' in text
    assert sum(len(p.images) for p in pdf.pages) >= len(pdf.pages)
    assert data == original


def test_legacy_and_unavailable_models_are_explicit():
    claim, revision, evaluation, _ = report_data()
    revision.pop('report_snapshot')
    evaluation['predictions'] = {'python': None, 'gtm': None}
    evaluation['comparison'] = {'status':'Uncertain Result','difference':None}
    pdf = PdfReader(BytesIO(claim_report(claim, revision, evaluation)))
    text = '\n'.join(p.extract_text() for p in pdf.pages)
    assert 'Not recorded' in text and 'Unavailable' in text
    assert 'No human review' in text and 'Example laptop' not in text


def test_long_and_markup_text_paginates_safely():
    data = report_data()
    data[1]['facts_json']['description'] = '<b>literal & text</b> ' + 'Long issue description. ' * 170
    data[3]['reason'] = 'Review reason with detail. ' * 150
    pdf = PdfReader(BytesIO(claim_report(*data)))
    text = '\n'.join(p.extract_text() for p in pdf.pages)
    assert '<b>literal & text</b>' in text
    assert '09 / Traceability' in text
    assert len(pdf.pages) > 3


if __name__ == '__main__':
    target = Path(__file__).resolve().parents[2] / 'output/pdf/AssureX-Claim-Report-Sample.pdf'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(claim_report(*report_data()))
    print(target)
