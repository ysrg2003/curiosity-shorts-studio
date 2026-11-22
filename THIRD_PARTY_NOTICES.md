# Additional reused components

## Independent entailment model

`cross-encoder/nli-deberta-v3-base`, revision `6c749ce3425cd33b46d187e45b92bbf96ee12ec7`.

Source and model card: https://huggingface.co/cross-encoder/nli-deberta-v3-base

The model card declares Apache-2.0. It is trained on SNLI and MultiNLI using Sentence Transformers. This project downloads the pinned ONNX CPU quantization and tokenizer, with exact size and SHA256 checks. The weights are not included in this repository. Model scores are an automated filter, not scientific certification.

## wordfreq

wordfreq3.1.1, by Robyn Speer and contributors: https://github.com/rspeer/wordfreq

Code: Apache-2.0. Included frequency data has separate attribution and Creative Commons Attribution-ShareAlike4.0 terms described in the project's README and packaged license notices. Credit includes Marc Brysbaert and the SUBTLEX authors, including Boris New and Emmanuel Keuleers. SUBTLEX is freely available data. The data also includes material from Google Books Ngrams, Wikipedia, the Leeds Internet Corpus, ParaCrawl and OPUS OpenSubtitles2018/OpenSubtitles. See the upstream README for full source credits and citations. This repository installs the package rather than copying or modifying its wordlists.

The language-frequency snapshot is not a complete or current dictionary. The narration filter permits terms present in the source text and never silently rewrites unknown words.


## Lexical retrieval ranking

rank-bm25 0.2.2 by D. Brown and contributors, Apache-2.0: https://github.com/dorianbrown/rank_bm25 and https://pypi.org/project/rank-bm25/ . This project installs the package and uses BM25L to rank its small discovery/citation/document collections. No source-code fork or scientific claim is implied.

snowballstemmer 3.1.1 by the Snowball Developers, BSD-3-Clause: https://pypi.org/project/snowballstemmer/3.1.1/ . English stemming is applied consistently to query/candidate text. The package is installed, not copied. Stems and relevance scores are retrieval aids, never truth or evidence-entailment decisions.
