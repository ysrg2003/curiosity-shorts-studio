import copy
import pytest
from curiosity.storyboard import validate_story,source_pack


def story():
    sources=[{'url':'https://example.org/demo-a','text':'A small motor moves a lever and the lever raises a flag in this demonstration.'},
             {'url':'https://example.net/demo-b','text':'This demonstration uses a moving lever to turn the motor motion into a visible raised flag.'}]
    lines=[]
    for i in range(13):
        ray=i%2==1
        lines.append({'speaker':'RAY' if ray else 'PIP','beat':'explain' if i in [1,5,9] else 'dialogue',
            'text':'In this demonstration, a small motor moves a lever, and that lever raises the flag you see.' if ray else 'So our little machine turns one movement into another, and that flag becomes the visible result?',
            'diagram':['Motor starts','Lever moves','Flag rises'],'visual_type':'flow','visual_title':'Simple mechanism',
            'evidence':[{'source_index':(i//2)%2,'quote':sources[(i//2)%2]['text']}] if ray else []})
    return {'lines':lines},sources


def test_balanced_source_supported_story():
    obj,sources=story();checks=validate_story(obj,sources)
    assert checks['words']>=155 and checks['explanation_beats']==3


def test_rejects_actual_short_outline_failure():
    obj,sources=story()
    for line in obj['lines']:line['text']='Just a tiny label.'
    with pytest.raises(ValueError,match='words'):validate_story(obj,sources)


def test_rejects_actual_all_explanation_failure():
    obj,sources=story()
    for line in obj['lines']:line['beat']='explain'
    with pytest.raises(ValueError,match='explanation'):validate_story(obj,sources)


def test_rejects_invented_quote():
    obj,sources=story();obj['lines'][1]['evidence'][0]['quote']='An invented sentence that the supplied source never actually contained.'
    with pytest.raises(ValueError,match='invented'):validate_story(obj,sources)


@pytest.mark.parametrize('qualifier,error',[('Researchers studied mice and found that','animal-study'),('Researchers proposed the hypothesis that','uncertainty')])
def test_preserves_source_limits(qualifier,error):
    obj,sources=story();quote=qualifier+' a small motor moves a lever and raises a flag.'
    sources[0]['text']=quote
    for line in obj['lines']:
        if line['evidence'] and line['evidence'][0]['source_index']==0:line['evidence'][0]['quote']=quote
    with pytest.raises(ValueError,match=error):validate_story(obj,sources)


def test_anatomical_template_cannot_illustrate_unrelated_claim():
    obj,sources=story();obj['lines'][1]['visual_type']='skin_hair'
    with pytest.raises(ValueError,match='skin_hair'):validate_story(obj,sources)


def test_relevant_excerpt_keeps_neighboring_qualification():
    sources=[{'url':'https://example.org','text':'Unrelated opening. Goosebumps involve tiny muscles. This result was observed in mice. Unrelated ending.'}]
    assert 'observed in mice' in source_pack('Why goosebumps?',sources)[0]['text']
