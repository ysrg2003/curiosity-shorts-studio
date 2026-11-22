# Sources and component limits

Checked 2026-11-22. Policies and model availability can change. Model outputs are drafts, not source evidence.

| Source | Used for |
|---|---|
| https://docs.github.com/en/actions/concepts/billing-and-usage | Standard public runners and self-hosted runners are free; private runs draw on included compute, with possible overage. |
| https://docs.github.com/en/billing/reference/product-usage-included | Current plan allowances and storage are separate from an unlimited-compute claim. |
| https://docs.github.com/en/actions/reference/limits | Runtime and storage limits. |
| https://developers.google.com/youtube/data/reference/rest/v3/videos/insert | Upload API, OAuth scopes, explicit privacy, current upload quota, and no current blanket private-only restriction on unverified projects. |
| https://developers.google.com/youtube/data/guides/quota_and_compliance_audits | API quotas and audit process for increases. |
| https://developers.google.com/identity/protocols/oauth2/native-app | Installed-application OAuth. |
| https://github.com/rany2/edge-tts | Independent wrapper around the online Edge speech service. No service availability or commercial-rights guarantee is inferred from the wrapper license. |
| https://pypi.org/project/edge-tts/ | Current package version inspected for compatibility. |
| https://github.com/hexgrad/kokoro/ | Open-weight local speech, Apache-2.0 model. |
| https://github.com/thewh1teagle/kokoro-onnx/ | MIT inference package and local ONNX workflow. |
| https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0 | Speech model and voice asset lineage. Runtime downloads model-files-v1.1 with pinned hashes in voice-models.json. |
| https://raw.githubusercontent.com/thewh1teagle/kokoro-onnx/main/examples/save.py | Current v1.1 model download names and API example. |
| https://ollama.com/library/qwen3:4b | 4.02B parameter local drafting model, approximately 2.5GB quantized weights. |
| https://ollama.com/library/qwen3:4b/blobs/d18a5cc71b84 | Apache-2.0 license. |
| https://docs.ollama.com/api/generate | JSON-schema generation API and generation options. |
| https://docs.ollama.com/linux | Linux runtime installation. The workflow downloads a versioned release, not a remote install shell script. |
| https://docs.github.com/en/github-models | GitHub Models retired July 30, 2026. Old free-inference examples are not a supported dependency here. |
| https://github.com/google/fonts/blob/main/ofl/quicksand/OFL.txt | SIL OFL redistribution terms, supplied beside the bundled unmodified fonts. |

## Starter science checked for the first demo

- https://www.scientificamerican.com/article/why-does-your-stomach-gro/ : peristaltic contractions move gas, food and fluid; fasting contractions and why sounds can be louder when empty.
- https://www.nature.com/articles/nrgastro.2012.57 : review article, cyclic fasting MMC in stomach and small bowel, interrupted by feeding.

The demo's finale is qualified: feeding pauses the fasting cleaning pattern, not all gut movement or all rumbling. Other inherited starter packs are marked science_reviewed=false until checked again.

## Quality boundaries

1. Kokoro voices are not the Ana/Andrew voices. The present local timing adapter estimates word spans. It is not a forced aligner.
2. Bespoke rigs preserve the drawing style and narrative structure. Arbitrary new topics use animated causal cards, not a promise of a custom anatomical simulation.
3. A small local model can invent or overstate a claim even with source text. Read research records and source indices; contested mechanisms must remain qualified.
4. One complete free render does not establish unlimited free scale or YouTube publication success. OAuth, upload quota, processing and platform checks are separate.
5. Internet, hardware, electricity and account allowance are finite. No paid API is configured, and no paid resource is intentionally selected.
