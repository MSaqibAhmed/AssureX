"""Shared AssureX PDF layout and immutable claim report renderer."""
from datetime import datetime, timezone
from html import escape
from io import BytesIO
from pathlib import Path
import reportlab
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.utils import ImageReader

NAVY = colors.HexColor('#082c36')
TEAL = colors.HexColor('#007c91')
PALE = colors.HexColor('#e7f6f8')
BORDER = colors.HexColor('#dfe8ec')
LOGO = Path(__file__).resolve().parents[1] / 'assets' / 'assurex-logo.png'
WIDTH = A4[0] - 88
FONT_DIR = Path(reportlab.__file__).parent / 'fonts'
pdfmetrics.registerFont(TTFont('AXRegular', str(FONT_DIR / 'Vera.ttf')))
pdfmetrics.registerFont(TTFont('AXBold', str(FONT_DIR / 'VeraBd.ttf')))
STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name='AXBody', fontName='AXRegular', fontSize=9, leading=14, textColor=NAVY, spaceAfter=7, wordWrap='CJK'))
STYLES.add(ParagraphStyle(name='AXTitle', parent=STYLES['AXBody'], fontName='AXBold', fontSize=26, leading=31, spaceAfter=14))
STYLES.add(ParagraphStyle(name='AXSection', parent=STYLES['AXBody'], fontName='AXBold', fontSize=13, leading=18, textColor=TEAL, spaceBefore=17, spaceAfter=10, keepWithNext=True))
STYLES.add(ParagraphStyle(name='AXSmall', parent=STYLES['AXBody'], fontSize=8, leading=11, textColor=colors.HexColor('#637681')))


def value(item):
    if item is None or item == '':
        return 'Not recorded'
    if isinstance(item, bool):
        return 'Yes' if item else 'No'
    if isinstance(item, datetime):
        return item.strftime('%d %b %Y, %H:%M UTC')
    if isinstance(item, (list, tuple)):
        return ', '.join(value(v) for v in item) or 'None recorded'
    if isinstance(item, dict):
        return '; '.join(f'{k.replace("_", " ")}: {value(v)}' for k, v in item.items()) or 'None recorded'
    return str(item)


def para(text, style='AXBody'):
    return Paragraph(escape(value(text)).replace('\n', '<br/>'), STYLES[style])


def section(title):
    return para(title, 'AXSection')


def table(headers, rows, widths=None):
    data = [[para(h) for h in headers]] + [[para(c) for c in row] for row in rows]
    result = Table(data, colWidths=widths or [WIDTH / len(headers)] * len(headers), repeatRows=1, hAlign='LEFT', splitInRow=1)
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PALE), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), .4, BORDER),
    ]))
    return result


def facts_table(rows):
    return table(['Detail', 'Recorded value'], rows, [155, WIDTH - 155])


def draw_logo(canvas, path, box, x, y, width):
    image = ImageReader(str(path))
    image_width, image_height = image.getSize()
    left, top, right, bottom = box
    scale = width / (right - left)
    height = (bottom - top) * scale
    canvas.saveState()
    clip = canvas.beginPath(); clip.rect(x, y, width, height)
    canvas.clipPath(clip, stroke=0)
    canvas.drawImage(image, x - left * scale, y - (image_height - bottom) * scale,
                     width=image_width * scale, height=image_height * scale, mask='auto')
    canvas.restoreState()


def build_document(story, title, reference='AssureX'):
    output = BytesIO()
    def page_frame(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(TEAL)
        canvas.rect(0, A4[1] - 8, A4[0], 8, fill=1, stroke=0)
        draw_logo(canvas, LOGO.parent / 'aptech-original.png', (248, 522, 886, 812), 44, A4[1] - 78, 100)
        draw_logo(canvas, LOGO, (154, 287, 1628, 608), 242, A4[1] - 67, 112)
        draw_logo(canvas, LOGO.parent / 'techwiz-original.png', (18, 25, 1522, 982), A4[0] - 139, A4[1] - 86, 95)
        canvas.setStrokeColor(BORDER); canvas.line(44, 46, A4[0] - 44, 46)
        canvas.setFont('AXRegular', 8); canvas.setFillColor(NAVY)
        canvas.drawString(44, 32, str(reference)[:75])
        canvas.drawRightString(A4[0] - 44, 32, f'Page {doc.page}')
        canvas.restoreState()
    document = SimpleDocTemplate(output, pagesize=A4, rightMargin=44, leftMargin=44, topMargin=100, bottomMargin=62, title=title, author='AssureX')
    document.build(story, onFirstPage=page_frame, onLaterPages=page_frame)
    return output.getvalue()


def claim_report(claim, revision, evaluation, review=None):
    facts = revision.get('facts_json', {})
    snapshot = revision.get('report_snapshot', {})
    product = snapshot.get('product', {})
    warranty = snapshot.get('warranty', {})
    reference = claim.get('public_claim_id') or claim['_id']
    story = [para('CLAIM ASSESSMENT', 'AXSmall'), para('Your claim, explained.', 'AXTitle'),
             para(f'{reference} | Submission revision {revision["revision_number"]}'),
             para('This report records the selected evaluation and, when included, its selected human review. Automated recommendations are advisory; they are not an approval or a warranty certificate.', 'AXSmall'),
             facts_table([('Advisory recommendation', evaluation.get('recommendation')), ('Human decision', review.get('after') or review.get('action') if review else 'No human review selected'), ('Submitted', revision.get('submitted_at')), ('Evaluation completed', evaluation.get('completed_at')), ('Report generated', datetime.now(timezone.utc))]),
             section('01 / Assessment summary')]
    story.extend(para(reason) for reason in evaluation.get('reasons', []))
    story.extend([section('02 / Product and purchase'), para('Product details are taken from the submission snapshot. Older submissions may not contain all fields.', 'AXSmall'), facts_table([
        ('Product name', product.get('name')), ('Brand / model', ' / '.join(filter(None, [product.get('brand'), product.get('model')]))),
        ('Category', product.get('category') or facts.get('product_category')), ('Registered serial number', product.get('serial')),
        ('Claim serial number', facts.get('serial')), ('Purchase date', facts.get('purchase_date')), ('Retailer', product.get('retailer')),
        ('Purchase amount', product.get('amount')), ('Currency', 'Not recorded by the product form'), ('Invoice number', facts.get('invoice_number'))]),
        section('03 / Reported issue'), facts_table([('Fault date', facts.get('fault_date')), ('Fault category', facts.get('fault_category')), ('Damage type', facts.get('damage_type')), ('Description', facts.get('description'))]),
        section('04 / Warranty and policy'), facts_table([('Provider', warranty.get('provider')), ('Recorded coverage starts', warranty.get('start_date')), ('Recorded coverage ends', warranty.get('expiry_date')), ('Pinned policy version', revision.get('policy_version_id'))])])
    policy_fields = [('Coverage months', 'coverage_months'), ('Reporting deadline (days)', 'reporting_days'), ('Grace period (days)', 'grace_days'), ('Required documents', 'required_documents'), ('Covered fault categories', 'covered_fault_categories'), ('Excluded damage', 'excluded_damage'), ('Authorized repairs required', 'require_authorized_repairs')]
    story.append(facts_table([(label, revision.get('policy', {}).get(key)) for label, key in policy_fields]))
    story.extend([section('05 / Independent model comparison'), para('Probabilities below are the saved model outputs, not a guarantee of eligibility.', 'AXSmall')])
    rows = []
    for family, label in [('python', 'Python / structured data'), ('gtm', 'GTM / summary card')]:
        prediction = evaluation.get('predictions', {}).get(family)
        rows.append([label] + ([f'{prediction[k]:.1%}' for k in ('valid', 'invalid', 'manual_review')] if prediction else ['Unavailable'] * 3))
    story.append(table(['Model', 'Valid', 'Invalid', 'Manual review'], rows, [185, 95, 95, WIDTH - 375]))
    comparison = evaluation.get('comparison', {})
    story.append(para(f'Consistency: {value(comparison.get("status"))} | Difference: {comparison["difference"]:.1%}' if comparison.get('difference') is not None else f'Consistency: {value(comparison.get("status"))} | Difference: unavailable'))
    for family, error in evaluation.get('model_errors', {}).items():
        story.append(para(f'{family}: {error}'))
    story.append(section('06 / Policy checks'))
    rules = evaluation.get('rule_results', [])
    if not rules:
        story.append(para('No rule results recorded.'))
    for rule in rules:
        story.append(para(f'{rule.get("rule_id", "Check")} | {rule.get("status", "Unknown")}', 'AXSection'))
        story.append(para(rule.get('explanation')))
        story.append(para(f'Severity: {value(rule.get("severity"))} | Verified: {value(rule.get("verified"))}', 'AXSmall'))
        story.append(para(f'Facts checked: {value(rule.get("facts_used"))}', 'AXSmall'))
        story.append(para(f'Evidence references: {value(rule.get("evidence_ids"))}', 'AXSmall'))
    story.extend([section('07 / Evidence and service record'), facts_table([
        ('Document types', facts.get('document_types')), ('Evidence references', facts.get('evidence_ids')),
        ('Missing document count', facts.get('missing_document_count')), ('Unverified evidence fields', facts.get('unverified_evidence_fields')),
        ('Evidence contradictions', facts.get('evidence_contradictions')), ('Contradiction count', facts.get('contradiction_count')),
        ('Duplicate signal', facts.get('duplicate_signal')), ('Serial check', facts.get('serial_status')), ('Repair count', facts.get('repair_count')), ('Repair authorization', facts.get('authorization_status'))])])
    for document in snapshot.get('documents', []):
        story.append(facts_table([(label, document.get(key)) for label, key in [('Evidence file', 'name'), ('Document type', 'type'), ('Format', 'mime'), ('Size (bytes)', 'size'), ('Evidence reference', '_id'), ('SHA-256', 'sha256')]]))
    for field in facts.get('ocr_fields', []):
        story.append(para(f'{field.get("field", "Evidence field")}: {value(field.get("normalized_value"))} | Corrected: {value(field.get("corrected", False))} | Confidence: {value(field.get("confidence"))}', 'AXSmall'))
    for repair in facts.get('repairs', []):
        story.append(facts_table([(label, repair.get(key)) for label, key in [('Service date','date'), ('Authorized','authorized'), ('Notes','notes'), ('Parts','parts'), ('Outcome','outcome'), ('Cost','cost')]]))
    story.append(section('08 / Human review'))
    if review:
        story.append(facts_table([('Review reference', review.get('_id')), ('Reviewer reference', review.get('reviewer_id')), ('Decision', review.get('after') or review.get('action')), ('Reviewed at', review.get('timestamp')), ('Reason', review.get('reason'))]))
    else:
        story.append(para('No human review was selected for this report. Check the claim workspace for its current status and any requested information.'))
    story.extend([section('09 / Traceability'), facts_table([('Claim reference', claim['_id']), ('Revision reference', revision.get('_id')), ('Evaluation reference', evaluation.get('_id')), ('Model and policy versions', evaluation.get('versions')), ('Input hash', evaluation.get('input_hash')), ('Evaluation version hash', evaluation.get('evaluation_input_version_hash'))]), para('AssureX records existing warranty coverage. This report does not issue coverage, certify receipt authenticity, or replace the recorded human decision. Original uploaded evidence is downloaded separately without modification.', 'AXSmall')])
    return build_document(story, f'AssureX claim report - {reference}', reference)
