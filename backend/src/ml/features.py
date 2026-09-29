"""Shared allowlist. IDs, labels, reviewer decisions and scores cannot enter either model."""
NUMERIC = ['product_age_days','warranty_remaining_days','coverage_months','reporting_delay_days','repair_count','missing_document_count','contradiction_count']
CATEGORICAL = ['product_category','fault_category','damage_type','serial_status','authorization_status']
TRISTATE = ['receipt_present','warranty_card_present','covered_fault','excluded_damage','duplicate_signal']
FEATURES = NUMERIC + CATEGORICAL + TRISTATE
CLASSES = ['valid','invalid','manual_review']

def build_features(facts):
    result = {}
    for name in NUMERIC:
        value = facts.get(name)
        result[name] = float(value) if value is not None else None
    for name in CATEGORICAL:
        result[name] = str(facts[name]).lower() if facts.get(name) is not None else 'unknown'
    for name in TRISTATE:
        value = facts.get(name)
        result[name] = 'yes' if value in (True,'yes') else 'no' if value in (False,'no') else 'unknown'
    return result
