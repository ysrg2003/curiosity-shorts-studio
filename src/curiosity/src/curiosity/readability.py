"""Reject malformed narration before semantic review or media. Never repair text."""
import re


WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def validate_narration(obj, sources):
    from wordfreq import zipf_frequency
    source_words = {word.casefold() for source in sources for word in WORD.findall(source['text'])}
    checked = 0
    for index, line in enumerate(obj.get('lines', []), 1):
        text = line['text']
        if not re.search(r'[.!?]$', text):
            raise ValueError(f'Line {index} is unfinished: end a complete spoken sentence naturally.')
        unknown = sorted({word for word in WORD.findall(text) if len(word) > 3
                          and word.casefold() not in source_words
                          and zipf_frequency(word, 'en') == 0})
        if unknown:
            raise ValueError(f'Line {index} contains unrecognized or joined words: ' + ', '.join(unknown[:5]))
        checked += 1
    return {'accepted': True, 'lines_checked': checked, 'text_modified': False,
            'method': 'sentence-ending-and-wordfreq-with-source-vocabulary',
            'not_a_grammar_or_truth_guarantee': True}
