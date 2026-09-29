from difflib import SequenceMatcher

def detect(current, others, threshold=.9):
    links = []
    for other in others:
        if current['claim_id'] == other['claim_id'] or current.get('product_id') != other.get('product_id'):
            continue
        exact = bool(set(current.get('hashes',[])) & set(other.get('hashes',[])))
        similar = bool(current.get('fault')) and SequenceMatcher(None,current['fault'].casefold(),other.get('fault','').casefold()).ratio() >= threshold
        if exact or similar:
            links.append({'other_claim_id':other['claim_id'],'kind':'exact' if exact else 'near','resolved':False})
    return links
