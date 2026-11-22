# Curiosity Shorts Studio

مشروع مستقل لتجربة إنتاج فيديوهات Pip وRay من البحث إلى ملف فيديو. عدد الفيديوهات الافتراضي **1**، ويتغير من `video_count` أو `studio.json`.

**الحالة: تجريبي. لم يُعتمد بعد تطابق جودة المواضيع الجديدة مع الفيديوهات الأصلية. النشر على YouTube متوقف، ولا توجد جدولة تلقائية.** وجود الكود أو نجاح اختبار وحدات لا يعني نجاح فيديو مستقل كامل أو صحة جميع معلوماته.

## التشغيل في GitHub Actions

افتح **Actions → Generate science videos → Run workflow**:

- `starter`: أمثلة موجودة مسبقا، لا يثبت اختيار موضوع أو بحث جديد.
- `new-topic`: موضوع وروابط اختيارية يقدمها المشغل، لا يثبت الاستقلال الكامل.
- `automatic`: يتجاهل حقول الموضوع والمصادر. يقترح النموذج أسئلة، ويتحقق من عدم تكرارها في السجل المتاح، ويسترجع نصوصا من Wikimedia ومراجع مؤسسية مقروءة، ثم يكتب الحوار وSEO واتجاهات المشاهد.
- `backend=ollama`: نموذج محلي على المعالج. يستخدم إصدار `qwen3:4b-instruct` ببصمة مثبتة، ويشترط نجاح اختبارJSONقصير مع `think=false` قبل التوليد. اسم النموذج أو غياب حقل التحكم لا يكفيان. يرفض أي خرج تفكير في استجابات الحوار والمشاهد. الاختبار القصير لا يثبت جودة التوليد أو صحة المعلومات. لا يستهلك مفتاح خدمة نموذج، لكنه بطيء وقد لا يكمل الفيديو ضمن المهلة.
- `backend=openrouter-free`: يحتاج Actions secret باسم `OPENROUTER_API_KEY`. أدخله مباشرة في إعدادات GitHub، لا في الكود أو رسائل المحادثة. يستخدم النموذج المجاني الصريح `particle-ai/particle-1:free` عبر OpenRouter، وليس الاختيار العشوائي داخل الموجه المجاني. يتحقق قبل كل طلب من السعر الصفري، ودعم المخرجات المنظمة، ودعم `reasoning_effort=none` للتوليد و`low` لفحوص الأدلة. إذا تغيرت هذه القدرات يتوقف، ولا يرجع إلى نموذج مدفوع. هذا اختيار تجريبي لم يثبت بعد نجاح فيديو كامل.
- `voice=kokoro`: صوت محلي بعد تنزيل النموذج، والأصوات تختلف عن الأصل. `edge` خيار خدمة خارجية غير مضمون التوفر.

اترك `video_count=1` للاختبار الأول. عند النجاح نزّل `video-bundles` خلال يوم. يتضمن الفيديو، الترجمة، ورقة المراجعة، فحص الوسائط، النص والمصادر والبصمات. عند الفشل قد يحتوي فقط على تشخيصات، وليس فيديو كاملا.

## مسار المواضيع الجديدة

1. اختيار سؤال آلي أو قراءة سؤال المشغل.
2. بحث محدود بالآلية والسؤال عبر Wikimedia، مع طلب HTML المراجع مرة واحدة لكل صفحة وترتيب الروابط بسياق الاقتباس والآلية، لا بترتيب URL أو شهرة الناشر. يفحص مجموعة المرشحين ضمن حد القراءة، ثم يرتب الوثائق ويختار حتى 4 مجموعات نشر، دون اعتبار الترتيب إثباتا علميا. استرجاع HTTPS يرفض الشبكات الخاصة وصفحات الموقع الرئيسية وبديل HTML لرابط PDF. يدعم استخراج HTML وبعض ملفات PDF الصغيرة.
3. قبول آلي صريح لمناسبة الموضوع لفيديو علمي قصير غير طبي، واشتراط مجموعتي نشر مقروءتين في الوضع الآلي، ثم فحص دعم السؤال نفسه والملاحظة والآلية. لا يكفي تشابه الكلمات. عند الرفض يجرب مرشحا آخر من القائمة المحدودة، ولا يخترع دليلا. هذا فحص بالنموذج، وليس إثباتا للصحة أو الإجماع. اسم الجامعة لا يكفي، ولا ينبغي عرض نص تاريخي أو نظرية قديمة كتفسير علمي حالي. يفحص كل سجل ثم يختار مجموعة صالحة، ولا يرسل السجلات المستبعدة إلى كاتب الحوار. يتحقق البرنامج من اكتمال فحص السجلات ومن عدم اختيار اقتباس من سجل مستبعد. تحفظ بداية الوثيقة منفصلة كسياق للمصدر، ضمن حد الحجم نفسه ودون دمجها في الاقتباس.
4. يستخدم pySBD لتحديد جمل أصلية كاملة داخل مقتطفات متصلة، ويختار النموذج معرفات هذه الجمل بدلا من إعادة كتابة الاقتباس. يربط البرنامج المعرف بالنص الحرفي دون اختراع أو إصلاح للدليل. تُفحص مواصفة التوليد قبل طلب الحوار: 13 خانة متناوبة تبدأ وتنتهي مع Pip، منها ثلاثة مشاهد شرح محددة مسبقا. قيود الكلمات داخل كل خانة تستهدف 176 إلى 228 كلمة. هذا تنظيم عام للحوار، وليس موضوعا أو نصا أو رسما محضرا. لا يضيف البرنامج كلمات ولا يعيد تعيين المشاهد لإصلاح خرج مخالف. تبقى فحوص الطول والأدلة كما هي، وقراءة ثانية بالنموذج تشترط أيضا حوارا إنجليزيا مترابطا وتبحث عن الادعاءات والآليات المرئية غير المدعومة. ترفض الموافقة على الأرقام العشوائية والنص غير المفهوم والحشو والتكرار، ولا يكفي اجتياز عدد الكلمات. عند إدخال روابط مصادر يدويا يُطلب فحص مناسبة الموضوع والمصادر قبل كتابة الحوار أيضا. يُفحص عقد ملف الحلقة قبل تسجيل قبول المسودة وبدء الصوت. الإخفاق يوقف المرحلة، ولا يعني قبول النموذج اعتمادا علميا بشريا.
5. توليد الصوت وتوقيت الكلمات في عملية لا ترث مفتاح النموذج أو صلاحية كتابة المستودع.
6. إعادة استخدام مكون توليد مشاهد Manim وفحصها وإصلاحها من paper2video، بدلا من كتابة مشهد يدوي لكل موضوع. الكود المولد يعمل داخل Docker بلا شبكة أو أسرار أو شجرة المستودع، بصلاحيات وموارد محدودة. لا يوجد رجوع صامت إلى شرائح ثابتة أو قالب جلد وشعرة عند فشل المشهد.
7. دمج المشاهد المحضرة مع الشخصيات والترجمة، وفحص الصورة والصوت والمدة، دون مفتاح نموذج في عملية الدمج.

الإخراج المستهدف 1080×1920،24إطارا/ثانية،H.264/AAC. تخطيط Manim عمودي أصلي9×16 مع منطقة محجوزة للترجمة. فحوص الوسائط لا تثبت دقة الرسم العلمي أو جودة القصة أو سلامة النطق، وتبقى `science_reviewed=false` للمسودات المولدة.

سجل المواضيع يستخدم ذاكرة GitHub المؤقتة المتاحة، حتى500عنوان. قد تنتهي الذاكرة أو تُحذف؛ ليست أرشيفا كاملا للقناة ولا ضمانا لعدم التكرار إلى الأبد.

## تحقق النص قبل الوسائط

مسار **Validate automatic topic and script before media** يختار الموضوع ويسترجع المصادر ويكتب الحوار بنفسه، ثم يتوقف قبل الصوت أو الفيديو. لا يأخذ موضوعا أو نصا محضرا. يستخدم المسار المحلي المجاني وحدود التنفيذ نفسها، ويحفظ التشخيصات ليوم واحد. هذا هو الاختبار التالي عند فشل قبول النص، بدلا من إنفاق وقت التصيير على نص غير مقبول.

يحافظ البرنامج على بنية JSON أثناء الاستدلال، لكنه لا يفرض حدود الكلمات حرفا بحرف على النموذج، لأن ذلك قد يجبره على دمج الكلمات عند الحد الأعلى. تبقى حدود الكلمات والبنية والطول شروط قبول في البرنامج، دون قص أو إضافة أو إصلاح للنص. فحص مستقل يرفض نهايات الجمل المبتورة والكلمات غير المعروفة، مع السماح بمفردات المصدر، باستخدام wordfreq. لا يعني ذلك فحصا لغويا كاملا.

قبل الكتابة، يجب أن يقدم فحص المصادر جوابا مباشرا كاملا عن السؤال مع معرفات اقتباساته. يفحص مكون مستقل معاد الاستخدام، `cross-encoder/nli-deberta-v3-base`، دعم الاقتباسات للجواب على المعالج المحلي. ثم يفحص جمل Ray وملاحظات عدم اليقين قبل الصوت. النموذج والمحول مثبتان بنسخة وبصمات ملفات، ولا يوجد اقتطاع صامت للسياق. هذا مرشح احتمالي محافظ، وليس إثباتا للصحة العلمية أو اكتمال كل ادعاء. تبقى المراجعة البشرية مطلوبة. راجع `THIRD_PARTY_NOTICES.md` للترخيص والنسب.

إرشادات توليد الحركة تزيل المثال الأفقي القديم قبل الاستدلال بدلا من إلحاق تعليمات عمودية متعارضة به. يرفض فحص الكود بعض العمليات التي تستخدم حواف الإطار المحجوزة للترجمة أو عرضا أفقيا مخالفا. لا يثبت ذلك غياب تداخل العناصر أو صحة الرسم، ويجب فحص الفيديو نفسه.

## الاختبار المقارن

يتيح **Inspect local model metadata or bounded response probe** فحصا تركيبيا صغيرا عند تفعيل `story_constraints`. يتحقق من خرج فعلي وحدود الكلمات على الإصدار المثبت، ولا يقدم موضوعا أو نص حلقة أو مصدرا للإنتاج. نجاحه لا يثبت جودة قصة أو صحة علمية أو نجاح فيديو كامل. تحفظ محاولات الحوار المكتملة كتشخيصات موسومة بأنها ليست حلقات معتمدة.

**Compare complete upstream animation pipeline** يشغل مسار paper2video الكامل على مقالات يقدمها المشغل، مع الصوت المحلي والتصيير المعزول. اختبار مكون، وليس قبول جودة Pip/Ray أو برهانا على اختيار موضوع مستقل. يتوقف إذا فشل توليد المشهد بعد المحاولات المحدودة، ويحتفظ بتشخيص عند الفشل.

## الحدود والتكلفة

لا يختار المشروع نموذجا مدفوعا أو يفتح ميزانية مدفوعة. حسب وثائق OpenRouter التي فُحصت أثناء البناء، لفئة النماذج المجانية حدود طلبات، منها50طلبا يوميا دون شراء رصيد و20طلبا في الدقيقة، والمحاولات الفاشلة تُحسب. راجع الشروط الحالية؛ الخدمة ليست غير محدودة أو مضمونة. قبل التوليد عبر OpenRouter يفحص البرنامج عداد الطلبات اليومي دون طباعة أرقامه أو بيانات الحساب. يطلب احتياطاً محافظاً يغطي26طلباً لكل فيديو، حسب الحدود الحالية لمحاولات اقتراح الموضوع والكتابة والمراجعة وإصلاح الحركة. إذا كان الاحتياط غير متاح أو تعذر التحقق منه يتوقف قبل الاستدلال. بقاء هذا الاحتياط لا يضمن توافر المزود. فحص الاتصال الصغير يحتفظ أيضاً بطلبين للاختبار.

المشغلات القياسية في مستودعات GitHub العامة مجانية وفق سياسة GitHub الحالية. جعل المستودع خاصا قد يستهلك الرصيد المشمول أو يؤدي إلى رسوم إذا سمحت إعدادات الفوترة بذلك. لا تفعّل مشغلا مدفوعا أو ميزانية مدفوعة. حد20فيديو في الإعدادات ومهلة90دقيقة ليسا وعدا بإنجاز20فيديو ضمن تشغيل واحد. المهلة ميزانية اختبار محدودة للمعالجة المجانية، وليست وعدا بوقت الإنجاز. رُفعت من50دقيقة بعد قياس محاولات كتابة تستغرق12إلى14دقيقة، وقبل إضافة توليد مشاهد الحركة.

المصادر أو التنزيلات أو النموذج أو كود المشهد قد تفشل. يتوقف المسار بدلا من ادعاء نجاح فيديو لم يكتمل. لا تضمن المراجعة الآلية صحة علمية كاملة. يلزم فحص الفيديو والمصادر قبل اعتماد النشر.

## الأمان والنشر

مسارا التوليد والمقارنة يطلبان `contents:read`، ويعطلان حفظ بيانات اعتماد checkout. أزيل مسار الاستيراد/الدفع القديم من التوليد العادي. مفتاح النموذج متاح لخطوة الاستدلال الموثوقة فقط، ولا يُمرر إلى العمليات الإعلامية الفرعية أو Docker. الملفات المرفقة لا تشمل `.git` أو الأسرار أو مخابئ النماذج.

كود النشر القديم محفوظ منفصلا، لكن **لا تستخدمه الآن**. لم يُعتمد فيديو مستقل ناجح بعد، ولم تُجهز هنا موافقة نشر أو جدولة. لا يستقبل مسار التوليد أسرار YouTube ولا يرفع فيديو كتأثير جانبي.

## تشغيل محلي

Python3.11،FFmpeg،espeak-ng وDocker مطلوبة للمواضيع الجديدة. تحتاج Manim إلى Cairo وPango. لمسار Ollama شغّل النموذج `qwen3:4b-instruct` أولا.

```sh
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test,local-voice,research,free-ai,motion,generated-motion]'
pytest -q
docker build -t curiosity-upstream-manim:0.20.1 -f experiments/Dockerfile.manim .
ollama pull qwen3:4b-instruct
python -m curiosity.local_ai
MODE=automatic VIDEO_COUNT=1 VOICE=kokoro CURIOSITY_LLM_BACKEND=ollama python -m curiosity.batch
```

استخدم مدير أسرار محليا إن اخترت OpenRouter، ولا تكتب قيمة المفتاح في سجل أوامر مشترك. لا يتطلب التشغيل حساب مساعد أو ملفاته الخاصة، لكن خدمات المصادر والتنزيلات تحتاج الإنترنت والموارد لها حدود.

## المكونات المعاد استخدامها

- paper2video،Apache-2.0،مثبت على `c713646c47d5ab3fc1085f733800750cfa235596`: https://github.com/edwardyen724-g/paper2video
- محول المستخدم الحقيقي من ai-provider-router،مثبت على `dae4ce4cd5a2b0bc231a58c4532cbe7c6d991be8`: https://github.com/ysrg2003/ai-provider-router
- pySBD0.3.4،MIT،لتجزئة الجمل دون تغيير النص: https://github.com/nipunsadvilkar/pySBD
- Manim Community،MIT: https://github.com/ManimCommunity/manim/
- Trafilatura،Apache-2.0،واستخراج PDF بواسطة pypdf،BSD-3-Clause.
- Kokoro،Apache-2.0،وkokoro-onnx،MIT،وخط Quicksand،OFL.

لا توجد أجزاء من مستودعات خاصة في هذه الإضافة. ظهور هذا المستودع لا يمنح تلقائيا ترخيصا مفتوحا للكود والرسوم المملوكة لصاحب المشروع؛ تراخيص المكونات الخارجية مستقلة. راجع `docs/SOURCES.md` وملفات تراخيص الخطوط.

النموذج المحلي: https://ollama.com/library/qwen3:4b-instruct وhttps://docs.ollama.com/capabilities/thinking .

مراجع الخدمة: https://openrouter.ai/openrouter/free وhttps://openrouter.ai/docs/api_reference/limits وhttps://openrouter.ai/docs/guides/routing/model-variants/free .

### Prose contracts and failure diagnostics

Native inference constrains JSON structure, not prose lengths or word boundaries. The original string limits are supplied separately to the writer and remain mandatory client checks. Failed contracts retain field paths, rules, counts and generation timing without copying generated prose into error metadata. The source-assessment stage can make at most two fresh attempts, with specific contract feedback; it does not repair text or retry a valid negative scientific verdict into approval. Source contract failure is recorded separately from insufficient evidence, and actual retrieval provenance is preserved. A valid JSON response still needs the independent evidence and story gates before any media.


### Structured source decisions and balanced discovery

Source audit reasons and remaining issues are closed reason codes, not free-form paragraphs with arbitrary audit-prose limits. Decision flags must agree with those codes. A negative source verdict may have an empty answer; a positive decision still needs a complete source-supported answer, original evidence IDs, two usable source groups and independent entailment before drafting. Spoken-word, narration-length, evidence and story gates are unchanged. Sentence candidates without ending punctuation are rejected rather than offered as complete evidence.

Both the mechanism and exact-question discovery pools are requested before article retrieval. Reference candidates are interleaved across discovered pages within the same global10article-attempt and per-page6attempt limits. The mechanism pool supplies the first usable encyclopedia introduction, rather than letting unrelated full-question results consume the whole budget. Discovery is not scientific approval. Rejected draft contracts can retain a separately labeled untrusted diagnostic response for inspection; it is never an accepted episode or a repaired script.


## Public-source transport safeguards

The public research bot uses one stable User-Agent with this repository as its contact URL, serial Wikimedia requests at least 7 seconds apart, and a bounded in-process response cache. It requests `maxlag=5`. HTTP status, numeric Retry-After and typed API errors are retained without server error bodies. HTTP 401/403/429/503 stops further requests to the affected provider for that process. A Wikimedia provider stop ends automatic selection, rather than continuing across other proposed topics. There is no identity rotation, browser impersonation or automatic retry after a provider stop.

Discovery reads rendered citation HTML once per page and ranks eligible article links using the question, mechanism and citation context. Search/query hubs are excluded. The unchanged article-attempt limits are 10 overall and 6 per discovered page. Context ranking and publisher diversity are retrieval aids, never scientific acceptance. Complete source answers, original evidence, independent entailment, narration and story gates still run before media. The transport reached source assessment in an actual GitHub Actions experiment, but no new script or video was accepted. Retrieval success is not scientific or video approval.

Primary API policies and reference:
- https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy/en
- https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits
- https://www.mediawiki.org/wiki/API:Etiquette
- https://www.mediawiki.org/wiki/Manual:Maxlag_parameter
- https://www.mediawiki.org/wiki/API:Parsing_wikitext


## Subject-first discovery and publication scope

The automatic proposer supplies a short `subject_query` as a search hypothesis, separately from the proposed mechanism. Subject, mechanism and exact-question discovery happen before reference reads. The subject phrase must overlap meaningful question vocabulary, but that is only a query-contract check. It does not validate the proposed mechanism or scientific answer. No operator-prepared topics or source URLs are injected into automatic mode.

The same 10 overall / 6 per-page article-attempt budget is collected before document selection. A first readable paper no longer suppresses later references from the same publisher. Question/subject overlap ranks the read documents, then up to four publisher groups reach the existing topic/source assessment. Ranking is not a usable-source verdict and cannot skip the later evidence, NLI, narration or story gates.

Numeric PubMed references use the documented Europe PMC publication-record API instead of relying on PubMed page chrome. Record ID, PMID and MED source must match. Only the returned abstract is used, with `abstract_only` scope, publication year and retrieval URL retained in the model source pack and research audit. It is not described as an inspected full paper. The existing 700-character text floor is unchanged, and metadata is never added to pad a short abstract. These records keep their original PubMed/NIH publisher group, so using an API mirror does not manufacture another independent source. Europe PMC reads are serial, conservatively spaced at least one second apart, and cached within the process.

API reference: https://europepmc.org/RestfulWebService
Search reference: https://www.mediawiki.org/wiki/Help:CirrusSearch


## Discovery relevance before article reads

Discovery pages, citation contexts and the read documents are ordered by the pinned CPU passage reranker `cross-encoder/ms-marco-MiniLM-L6-v2`, revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`. The quantized ONNX file and tokenizer have exact size/SHA256 checks. It compares the actual question with candidate text. Its logits only order retrieval; they are not probabilities, truth, scientific approval or evidence entailment. Up to five discovered pages reach reference discovery; lexical BM25L/Snowball pre-ranking limits citation reranking to120candidates. Article requests retain the same ten overall/six per-page caps. There is no hard word-overlap deletion of pages, which an earlier experiment showed could discard correct short titles and retain misleading longer ones.

The reranker uses explicit512-token retrieval windows. The original source text remains unchanged for later evidence checks. The separate independent NLI engine retains its no-truncation rule and0.90threshold. Topic/source acceptance, original-evidence binding, complete causal answers, narration and story checks remain mandatory before media.

Every completed source assessment retains exact original sentences selected by its generated verdict, IDs/source indices and source-excerpt hashes, including rejected selections. These are unapproved diagnostics, not accepted facts. No failed answer or quote is silently rewritten.
