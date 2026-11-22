# Complete existing animation-pipeline comparison

This is a test track, not the final Pip/Ray system and not a YouTube publishing path.

The goal is to reuse a complete project that can plan different topics, rather than keep adding hand-authored topic presets. The first selected test adapts the existing **paper2video** pipeline at commit `c713646c47d5ab3fc1085f733800750cfa235596`:

https://github.com/edwardyen724-g/paper2video

Its source is Apache-2.0 licensed. Its original ingest, research, script, code-generation, lint/repair, speech-duration, mux and assembly workflow remains the base. The comparison adapter changes the inference provider to local Ollama, uses the project's already-tested local ONNX speech, runs generated Python only in an isolated no-network Docker renderer, and refuses the upstream static-slide fallback. No scene code is written by hand for either input topic.

The upstream default uses a paid model. That default is **not** used here. This experiment passes a local provider directly, has no paid API key input, and uses standard CPU Actions. A successful run still would not prove unlimited free capacity, arbitrary-topic factual accuracy or final visual quality.

## Run

Use the manual `Compare complete upstream animation pipeline` workflow. The video-count default is1 and this bounded benchmark accepts at most2 source articles. For a cross-topic test, request2. The sample sources concern lunar phases and soap chemistry. Every source goes through the same pipeline and the same generic benchmark instructions.

The benchmark intentionally makes two-scene,50-to120-word landscape videos to test topic-specific visual planning before spending more time on a production-length integration. This does not yet preserve the Pip/Ray characters or final portrait/caption design. It cannot be uploaded through the production publication workflow because that workflow only accepts its generation workflow as a source.

Only complete real videos, generated scripts/code and run evidence are retained as one-day artifacts. Full ingested articles, model caches and credentials are excluded. Inspect the actual video and source wording. A green workflow badge is not creative or scientific acceptance.

## Other complete projects inspected

| Project | Grounded finding for this task |
|---|---|
| https://github.com/TIGER-AI-Lab/TheoremExplainAgent | MIT. Planning, code generation and optional visual repair are present, but the dependency/provider stack is heavier; equivalent local CPU operation is not yet proven. |
| https://github.com/kennethbicocchi/localmotion | MIT project with a real local planning/code/check/render loop. The documented successful configuration uses a24GB GPU and27B model. Remotion has separate terms. Not evidence that the demonstrated quality fits standard CPU Actions. |
| https://github.com/AnayGarodia/sketchling | MIT drawing/animation language, CLI rendering, validation and film assembly with varied existing examples. Useful expressive-art candidate, but not an autonomous local topic-to-video planner by itself. |
| https://github.com/andreabuttarelli/feega | Apache-2.0 complete editor/studio. Current image/video/audio generation integrations need external providers. No tested free autonomous CPU path established here. |
| https://github.com/theodorebeaupre-prog/comotion | MIT project built around seven prebuilt scenes and an external coding-agent option. Its advertised zero-cost operator path is not a free standalone local planner. |

The inspected clones of `chbayah-sudo/manimator`, `suleman1412/lesson-forge` and `Bugsbunnydev2000/Math-Animation-Generator` had no license declaration or license file found at inspection. Their code is not copied into this repository.

Model options have their own licenses. The listed Qwen2.5-Coder7B and1.5B artifacts use Apache-2.0. The3B variant has different research-license terms and was not selected. Model outputs still require review.
