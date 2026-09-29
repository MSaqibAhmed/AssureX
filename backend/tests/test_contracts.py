import io
import pytest
from pydantic import ValidationError
from PIL import Image
from src.schemas.requests import ClaimCreate,Review,Register
from src.engines.ocr import validate_document,normalize
from src.ml.features import build_features,FEATURES

def test_browser_cannot_send_model_scores_or_role():
    with pytest.raises(ValidationError): ClaimCreate(product_id='p',facts={},confidence=.99)
    with pytest.raises(ValidationError): Register(name='Name',email='a@example.com',password='password123',role='admin')
    with pytest.raises(ValidationError): Review(version=1,status='Manual Review',action='approve',reason='   ',evaluation_id='e')

def test_feature_allowlist():
    result=build_features({'claim_id':'secret','label':'valid','reviewer_result':'Approved'})
    assert set(result)==set(FEATURES)
    assert result['receipt_present']=='unknown'

def test_upload_content_not_extension():
    with pytest.raises(ValueError): validate_document(b'<script>bad</script>','image.png','image/png')
    data=io.BytesIO(); Image.new('RGB',(20,20)).save(data,format='PNG')
    validate_document(data.getvalue(),'image.png','image/png')
    with pytest.raises(OverflowError): validate_document(data.getvalue(),'image.png','image/png',max_bytes=1)

def test_ambiguous_date_stays_unknown():
    assert normalize('purchase_date','01/02/2026') is None
    assert normalize('purchase_date','2026-02-01')=='2026-02-01'

@pytest.mark.parametrize('value',['NaN','Infinity','-Infinity','-1','not money'])
def test_invalid_amount_correction_stays_unknown(value):
    assert normalize('amount',value) is None
