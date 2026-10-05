from framecore.campaign import create_campaign, SCENES
from framecore.store import Store
from framecore.model import validate
from framecore.library import catalog

def test_campaign_has_exact_pacing_and_distinct_motion(tmp_path):
    state=create_campaign(Store(tmp_path/'projects'))
    p=state['project'];validate(p)
    assert p['duration']==30
    assert [(s['start'],s['duration']) for s in p['scenes']]==[(i*5,5) for i in range(6)]
    titles=[e for e in p['elements'] if e.get('text') in [s[0] for s in SCENES] and e['type']=='text']
    assert len(titles)==6
    assert len({e['motion']['id'] for e in titles})==6
    assert len([e for e in p['elements'] if e['type']=='audio'])==1
    assert len(catalog('scene'))==3
