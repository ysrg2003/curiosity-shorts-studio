"""Independent CPU source-entailment filter. A score is not scientific certification."""
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from urllib.request import urlopen

MODEL = 'cross-encoder/nli-deberta-v3-base'
REVISION = '6c749ce3425cd33b46d187e45b92bbf96ee12ec7'
FILES = {
    'tokenizer.json': ('5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964', 8656624),
    'onnx/model_quint8_avx2.onnx': ('36784d97274ef019db9f54fd16812f9a460e787703658b0f3b2200999692680b', 244422412),
}
THRESHOLD = 0.90


def artifact(name):
    expected, size = FILES[name]
    path = Path.home() / '.cache' / 'curiosity-nli' / REVISION / Path(name).name
    if not path.exists() or path.stat().st_size != size or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        path.parent.mkdir(parents=True, exist_ok=True)
        url = 'https://huggingface.co/' + MODEL + '/resolve/' + REVISION + '/' + name
        with urlopen(url, timeout=90) as response:
            data = response.read(size + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Independent entailment model failed pinned size/hash verification')
        temporary = path.with_suffix(path.suffix + '.download')
        temporary.write_bytes(data)
        temporary.replace(path)
    return path


@lru_cache(maxsize=1)
def engine():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tokenizer = Tokenizer.from_file(str(artifact('tokenizer.json')))
    tokenizer.enable_padding(pad_id=0, pad_token='[PAD]')
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(artifact('onnx/model_quint8_avx2.onnx')),
                                   sess_options=options, providers=['CPUExecutionProvider'])
    return tokenizer, session


def score_pairs(pairs):
    import numpy as np
    if not pairs or len(pairs) > 40:
        raise ValueError('Independent entailment requires 1 to 40 bounded sentence pairs')
    if any(not premise.strip() or not claim.strip() or len(premise) > 16000 or len(claim) > 1200
           for premise, claim in pairs):
        raise ValueError('Independent entailment received missing or oversized text')
    tokenizer, session = engine()
    encoded = tokenizer.encode_batch(pairs)
    if any(sum(item.attention_mask) > 512 for item in encoded):
        raise ValueError('Independent entailment context exceeds512tokens. No silent truncation.')
    inputs = {'input_ids': np.array([item.ids for item in encoded], dtype=np.int64),
              'attention_mask': np.array([item.attention_mask for item in encoded], dtype=np.int64)}
    logits = session.run(None, inputs)[0]
    scores = np.exp(logits - logits.max(axis=1, keepdims=True))
    scores /= scores.sum(axis=1, keepdims=True)
    rows = [{'entailment_score': round(float(row[1]), 6),
             'contradiction_score': round(float(row[0]), 6),
             'neutral_score': round(float(row[2]), 6),
             'accepted': bool(row[1] >= THRESHOLD),
             'premise_sha256': hashlib.sha256(premise.encode()).hexdigest(),
             'claim_sha256': hashlib.sha256(claim.encode()).hexdigest()}
            for row, (premise, claim) in zip(scores, pairs)]
    return {'accepted': all(row['accepted'] for row in rows), 'pairs': rows,
            'model': MODEL, 'revision': REVISION, 'threshold': THRESHOLD,
            'cpu_only': True, 'context_truncated': False, 'not_a_truth_guarantee': True}


def source_answer(question, verdict, entries):
    answer = verdict.get('answer', '')
    selected = verdict.get('answer_quote_ids', [])
    if not isinstance(answer, str) or not answer.strip() or not selected or any(key not in entries for key in selected):
        return {'accepted': False, 'reason': 'Missing complete source-supported answer or original quote IDs'}
    # A self-contained answer must mention the question, not only related vocabulary.
    filler = {'what', 'which', 'where', 'when', 'does', 'that', 'this', 'have', 'with', 'from', 'happen', 'happens', 'cause', 'causes', 'makes', 'about', 'after', 'before', 'their', 'there', 'than'}
    terms = {word.casefold().rstrip('s') for word in re.findall(r'[A-Za-z]{4,}', question) if word.casefold() not in filler}
    answer_words = {word.casefold().rstrip('s') for word in re.findall(r'[A-Za-z]{4,}', answer)}
    if not terms.intersection(answer_words):
        return {'accepted': False, 'reason': 'Proposed answer does not name the chosen question subject'}
    if not re.search(r'[.!?]$', answer):
        return {'accepted': False, 'reason': 'Proposed source-supported answer is unfinished'}
    import pysbd
    sentences = pysbd.Segmenter(language='en', clean=False).segment(answer)
    premise = '\n'.join(entries[key]['quote'] for key in selected)
    from .readability import validate_narration
    try:
        validate_narration({'lines': [{'text': answer}]}, [{'text': premise}])
    except ValueError as error:
        return {'accepted': False, 'reason': str(error)}
    return score_pairs([(premise, sentence.strip()) for sentence in sentences if sentence.strip()])


def story(obj):
    import pysbd
    segmenter = pysbd.Segmenter(language='en', clean=False)
    pairs = []
    indices = []
    # Short conversational acknowledgments contain no scientific assertion.
    acknowledgments = {'yes.', 'no.', 'right.', 'exactly.', 'correct.', 'perfect.',
                       "that's a great question.", 'good question.', 'great question.'}
    for index, line in enumerate(obj['lines'], 1):
        if line['speaker'] != 'RAY':
            continue
        premise = '\n'.join(item['quote'] for item in line['evidence'])
        for sentence in segmenter.segment(line['text']):
            sentence = sentence.strip()
            if not sentence or sentence.casefold() in acknowledgments:
                continue
            pairs.append((premise, sentence))
            indices.append(index)
    report = score_pairs(pairs)
    for row, index in zip(report['pairs'], indices):
        row['line'] = index
    groups = list(dict.fromkeys(premise for premise, _ in pairs))
    metadata = []
    for note in obj.get('uncertainties', []):
        checked = score_pairs([(premise, note) for premise in groups])
        metadata.append({'accepted': any(row['accepted'] for row in checked['pairs']),
                         'candidate_source_groups': checked['pairs']})
    report['uncertainty_checks'] = metadata
    report['accepted'] = report['accepted'] and all(item['accepted'] for item in metadata)
    return report


# Passage relevance is separate from the entailment model and its0.90gate.
RERANK_MODEL = 'cross-encoder/ms-marco-MiniLM-L6-v2'
RERANK_REVISION = '233902d25c440f23af6f7d6e94d2946bac0bee0a'
RERANK_FILES = {
    'tokenizer.json': ('d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66',711396),
    'onnx/model_quint8_avx2.onnx': ('c80a8b34256ea453093d612e3ac48d3d965a0c0a48c7906709af8b8e28461bf9',23200716),
}


def rerank_artifact(name):
    expected,size=RERANK_FILES[name]
    path=Path.home()/'.cache'/'curiosity-reranker'/RERANK_REVISION/Path(name).name
    if not path.exists() or path.stat().st_size!=size or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
        url='https://huggingface.co/'+RERANK_MODEL+'/resolve/'+RERANK_REVISION+'/'+name
        with urlopen(url,timeout=90) as response:data=response.read(size+1)
        if len(data)!=size or hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('Relevance model failed pinned size/hash verification')
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_suffix(path.suffix+'.download');temporary.write_bytes(data);temporary.replace(path)
    return path


@lru_cache(maxsize=1)
def rerank_engine():
    import onnxruntime as ort
    from tokenizers import Tokenizer
    tokenizer=Tokenizer.from_file(str(rerank_artifact('tokenizer.json')))
    tokenizer.enable_padding(pad_id=0,pad_token='[PAD]')
    # Retrieval may compare bounded passage windows. This is not the NLI engine,
    # whose evidence is never silently truncated.
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    session=ort.InferenceSession(str(rerank_artifact('onnx/model_quint8_avx2.onnx')),
                                sess_options=options,providers=['CPUExecutionProvider'])
    return tokenizer,session


def relevance_scores(question,passages):
    """Uncalibrated relevance logits for ordering only, no acceptance threshold."""
    import numpy as np
    if not passages:return []
    if len(passages)>500 or not question.strip() or len(question)>300 or any(not text.strip() or len(text)>8000 for text in passages):
        raise ValueError('Relevance requires1to500bounded nonempty passages and a bounded question')
    tokenizer,session=rerank_engine();result=[]
    for offset in range(0,len(passages),16):
        batch=passages[offset:offset+16]
        encoded=tokenizer.encode_batch([(question,text) for text in batch])
        # A retrieval window is explicit and logged. The original article text
        # remains unchanged for the later source/evidence/entailment checks.
        for item in encoded:item.truncate(512)
        width=max(len(item.ids) for item in encoded)
        ids=[];masks=[];types=[]
        for item in encoded:
            padding=width-len(item.ids)
            ids.append(item.ids+[0]*padding);masks.append(item.attention_mask+[0]*padding);types.append(item.type_ids+[0]*padding)
        inputs={'input_ids':np.array(ids,dtype=np.int64),'attention_mask':np.array(masks,dtype=np.int64),
                'token_type_ids':np.array(types,dtype=np.int64)}
        logits=session.run(None,inputs)[0].reshape(-1)
        result.extend(round(float(score),6) for score in logits)
    return result
