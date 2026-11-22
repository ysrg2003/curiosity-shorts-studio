"""Word cues from the local voice model's phoneme durations, not letter lengths."""
from difflib import SequenceMatcher


def align_words(text, phonemes, tokenizer, lang='en-us'):
    """Map original words onto duration-backed phonemes. Never transcribe or rewrite."""
    words = text.split()
    # Spaces remain in the model's phoneme stream, including reduced function words.
    # Keep multi-part pronunciations (numbers, abbreviations) attached to their original token.
    groups, group = [], []
    for ph in phonemes:
        if ph.phoneme.isspace():
            if group: groups.append(group); group=[]
        elif ph.phoneme.isalpha(): group.append(ph)
    if group: groups.append(group)
    counts = [max(1,len(tokenizer.phonemize(w,lang).split())) for w in words]
    if len(groups)==len(words): counts=[1]*len(words)
    if sum(counts)==len(groups):
        cues, n = [], 0
        for word,count in zip(words,counts):
            cues.append({'text':word,'start':float(groups[n][0].start),
                         'end':float(groups[n+count-1][-1].end)})
            n += count
        return cues, 1.0
    expected, spans = '', []
    for word in words:
        ph = tokenizer.phonemize(word, lang)
        start = len(expected)
        expected += ph
        spans.append((start, len(expected)))
        expected += ' '
    actual = ''.join(p.phoneme for p in phonemes)
    mapping = {}
    for block in SequenceMatcher(None, expected, actual, autojunk=False).get_matching_blocks():
        mapping.update((block.a+i, block.b+i) for i in range(block.size))
    cues = []
    for word, (a, b) in zip(words, spans):
        indices = [mapping[i] for i in range(a, b) if i in mapping and expected[i].isalpha()]
        if not indices:
            cues.append(None)
            continue
        cues.append({'text':word, 'start':float(phonemes[min(indices)].start),
                     'end':float(phonemes[max(indices)].end)})
    i = 0
    while i < len(cues):
        if cues[i] is not None: i+=1; continue
        j=i+1
        while j<len(cues) and cues[j] is None: j+=1
        start=cues[i-1]['end'] if i else 0.0
        end=cues[j]['start'] if j<len(cues) else float(phonemes[-1].end)
        if end<=start: raise ValueError('No phoneme interval for reduced function words')
        for k in range(i,j):
            cues[k]={'text':words[k],'start':start+(end-start)*(k-i)/(j-i),
                     'end':start+(end-start)*(k-i+1)/(j-i),'source':'reduced-phoneme-interpolation'}
        i=j
    for i, cue in enumerate(cues):
        if cue['end'] <= cue['start'] or (i and cue['start'] < cues[i-1]['start']):
            raise ValueError('Non-monotonic model word timing')
    coverage = sum(i in mapping for i,c in enumerate(expected) if c.isalpha()) / max(1,sum(c.isalpha() for c in expected))
    if coverage < 0.72:
        raise ValueError('Insufficient phoneme alignment coverage')
    return cues, coverage


def envelope(audio, sample_rate, hz=40):
    import numpy as np
    step = max(1, round(sample_rate/hz))
    a = np.asarray(audio)
    if a.ndim > 1: a = a.mean(axis=1)
    rms = np.array([np.sqrt(np.mean(a[i:i+step]**2)) for i in range(0,len(a),step)])
    scale = max(float(np.percentile(rms,92)),1e-6)
    return [round(float(min(1.0,max(0.0,x/scale))),3) for x in rms]
