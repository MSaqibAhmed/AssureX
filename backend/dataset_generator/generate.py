import argparse, hashlib, json, random
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split
from src.ml.card import render_card

VERSION = '1.0'

def rubric(f):
    if f['missing_document_count'] or f['contradiction_count'] or f['duplicate_signal'] or f['serial_status']=='unknown':
        return 'manual_review','Missing/ambiguous evidence or unresolved risk'
    if f['warranty_remaining_days'] < 0 or f['excluded_damage'] or f['serial_status']=='mismatch' or f['authorization_status']=='unauthorized':
        return 'invalid','Verified coverage, exclusion, serial or repair hard failure'
    return 'valid','Complete evidence and covered fault without hard failure'

def generate(seed=42, output=Path('data')):
    rng = random.Random(seed)
    rows = []
    counts = {k:0 for k in ['valid','invalid','manual_review']}
    while min(counts.values()) < 500:
        f = dict(product_age_days=rng.randrange(1,1100), warranty_remaining_days=rng.randrange(-180,730),
            coverage_months=rng.choice([12,24]),reporting_delay_days=rng.randrange(0,30),repair_count=rng.randrange(0,4),
            missing_document_count=rng.choices([0,1,2],[8,1,1])[0],contradiction_count=rng.choices([0,1],[9,1])[0],
            product_category=rng.choice(['mobile','electronics','appliances']),fault_category=rng.choice(['display','battery','mechanical','audio']),
            damage_type=rng.choice(['none','liquid','accidental']),serial_status=rng.choices(['match','mismatch','unknown'],[8,1,1])[0],
            authorization_status=rng.choices(['authorized','unauthorized'],[9,1])[0],receipt_present=True,
            warranty_card_present=True,covered_fault=True,excluded_damage=False,duplicate_signal=rng.random()<.05)
        f['receipt_present'] = f['missing_document_count']==0
        f['excluded_damage'] = f['damage_type'] != 'none'
        label,rationale = rubric(f)
        if counts[label] >= 500:
            continue
        counts[label] += 1
        uid = hashlib.sha256(json.dumps(f,sort_keys=True).encode()).hexdigest()
        if any(row['group_id']==uid for row in rows):
            counts[label]-=1
            continue
        rows.append(dict(f,group_id=uid,label=label,seed=seed,generator_version=VERSION,
                         scenario_id=f'scenario-{len(rows):04d}',label_rationale=rationale))
    train, rest = train_test_split(rows,test_size=.3,stratify=[r['label'] for r in rows],random_state=seed)
    val,test = train_test_split(rest,test_size=.5,stratify=[r['label'] for r in rest],random_state=seed)
    output.mkdir(parents=True,exist_ok=True)
    for split,records in [('train',train),('validation',val),('test',test)]:
        pd.DataFrame(records).to_csv(output/f'{split}.csv',index=False)
        for row in records:
            folder = output/'cards'/split/row['label']
            folder.mkdir(parents=True,exist_ok=True)
            for variant in range(2 if split=='train' else 1):
                render_card(row,variant).save(folder/f'{row["group_id"]}-{variant}.png')
    pd.DataFrame([{k:r[k] for k in ['group_id','seed','generator_version','scenario_id','label','label_rationale']} for r in rows]).to_csv(output/'data_sources.csv',index=False)
    hashes = {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob('*.csv')}
    (output/'manifest.json').write_text(json.dumps({'seed':seed,'counts':counts,'hashes':hashes},indent=2))
    print(json.dumps({'claims':len(rows),'splits':[len(train),len(val),len(test)],'images':len(train)*2+len(val)+len(test)}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--seed',type=int,default=42); parser.add_argument('--output',type=Path,default=Path('data'))
    args=parser.parse_args(); generate(args.seed,args.output)
