import pytest
from src.engines.fault_media import validate_video,media_review


def box(kind,payload=b''):
    return (8+len(payload)).to_bytes(4,'big')+kind+payload


def test_mp4_container_validation():
    data=box(b'ftyp',b'isom0000')+box(b'moov')+box(b'mdat',b'data')
    validate_video(data,'fault.mp4','video/mp4',1000)
    for invalid in (b'not a video',data[:-1],box(b'ftyp')):
        with pytest.raises(ValueError): validate_video(invalid,'fault.mp4','video/mp4',1000)
    with pytest.raises(ValueError): validate_video(data,'fault.pdf','video/mp4',1000)
    with pytest.raises(OverflowError): validate_video(data,'fault.mp4','video/mp4',1)


def test_media_cannot_fabricate_ai_diagnosis():
    assert media_review('fault_video')['status']=='manual_review'
    assert media_review('fault_image')['status']=='unavailable'


def test_fault_video_requires_review_even_with_agreeing_models():
    from src.engines.rules import run_rules,Policy
    from src.engines.decision import decide
    policy=Policy(category='mobile',version='test',coverage_months=12,reporting_days=30,grace_days=0,reminder_window=30,excluded_damage=[],required_documents=[],require_authorized_repairs=False)
    facts={'purchase_date':'2026-01-01','fault_date':'2026-02-01','submission_date':'2026-02-02','damage_type':'none','serial_status':'match','fault_media':[{'document_id':'v1','type':'fault_video'}]}
    rules=run_rules(facts,policy)
    assert any(r.rule_id=='fault_media:v1' and r.status=='MANUAL_REVIEW' for r in rules)
    result=decide({'valid':.98,'invalid':.01,'manual_review':.01},{'valid':.98,'invalid':.01,'manual_review':.01},rules,mandatory_facts_verified=True)
    assert result.recommendation=='Manual Review Required'
