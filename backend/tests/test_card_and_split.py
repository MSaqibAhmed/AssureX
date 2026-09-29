import json
from pathlib import Path
import pytest
from src.ml.card import render_card

def test_card_never_renders_prediction_or_id():
    baseline=render_card({'product_category':'mobile'})
    poisoned=render_card({'product_category':'mobile','claim_id':'valid','label':'invalid','confidence':.99,'final_decision':'Rejected'})
    assert baseline.tobytes()==poisoned.tobytes()

def test_generated_groups_disjoint_and_balanced():
    if not Path('data/train.csv').exists(): pytest.skip('Generate dataset first')
    import pandas as pd
    splits={k:pd.read_csv(f'data/{k}.csv') for k in ('train','validation','test')}
    assert [len(splits[k]) for k in splits]==[1050,225,225]
    sets=[set(v.group_id) for v in splits.values()]
    assert not sets[0]&sets[1] and not sets[0]&sets[2] and not sets[1]&sets[2]
    assert len(set.union(*sets))==1500
    for name,df in splits.items():
        assert df.label.value_counts().nunique()==1
        assert len(list(Path(f'data/cards/{name}').rglob('*.png')))==len(df)*(2 if name=='train' else 1)
