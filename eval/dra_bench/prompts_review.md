# DRA-Bench — synthesized prompts for review

Drafter: `global.anthropic.claude-opus-4-8` (non-generator family). Each prompt is an EvalItem; `expected_behavior` is derived from its type and is what makes the open-ended prompt gradable.

Per-type counts: {'type1': 50, 'type2': 50, 'type3': 50, 'type4': 50, 'type5': 50} (total 250).

## type1 — deep NLP/AI (expected_behavior: `answer_confident`)

_Deep, technical NLP/AI research questions with a defensible answer in the literature (e.g. attention, tokenization, RLHF)._

Specificity spread — foundational: 17, intermediate: 17, deep: 16.

1. How does self-attention work in transformer models?
2. What are neural scaling laws and what do they predict about model performance?
3. What is RLHF and why is it used to align language models?
4. How does backpropagation train a neural network?
5. What is the difference between encoder-only, decoder-only, and encoder-decoder transformer architectures?
6. How do word embeddings like Word2Vec and GloVe represent meaning?
7. What is transfer learning and how does pretraining followed by fine-tuning work in NLP?
8. How does beam search differ from greedy decoding in sequence generation?
9. What is the vanishing gradient problem and how do LSTMs and GRUs address it?
10. How does tokenization work, and what are the tradeoffs between word, subword, and character-level approaches?
11. What is the attention mechanism in sequence-to-sequence models and what problem does it solve?
12. How do large language models perform in-context learning and few-shot prompting?
13. What is the role of positional encoding in transformer architectures?
14. What are the key differences between BERT-style masked language modeling and GPT-style autoregressive language modeling?
15. How does dropout work as a regularization technique in neural networks?
16. What is perplexity and how is it used to evaluate language models?
17. What is the difference between supervised, unsupervised, and self-supervised learning in NLP?
18. How do rotary position embeddings (RoPE) enable length extrapolation, and what modifications improve their behavior beyond training context?
19. What are the main strategies for mitigating exposure bias in autoregressive text generation, and how effective are they?
20. How do contrastive learning objectives like those in SimCSE produce better sentence embeddings than traditional pooling methods?
21. What distinguishes Direct Preference Optimization (DPO) from PPO-based RLHF, and what are the practical tradeoffs?
22. How does speculative decoding accelerate inference, and what determines the achievable speedup?
23. What are the causes of hallucination in large language models, and how do retrieval-augmented and grounding methods reduce it?
24. How do KV-cache compression and quantization techniques trade off memory footprint against generation quality?
25. Why does instruction tuning improve zero-shot generalization, and how does dataset diversity affect the outcome?
26. What are the differences between LoRA, prefix tuning, and adapter modules in terms of where they inject trainable parameters?
27. How does chain-of-thought prompting improve reasoning, and under what conditions does it fail or degrade performance?
28. What mechanisms allow grouped-query and multi-query attention to reduce inference cost, and how do they affect model quality?
29. How do calibration and confidence estimation methods work for large language models, and why do RLHF-tuned models tend to become miscalibrated?
30. What are the main approaches to evaluating factual consistency in summarization, and how well do they correlate with human judgments?
31. How does the choice of pretraining data mixture and deduplication affect downstream model performance and memorization?
32. What is the role of temperature, top-k, and nucleus sampling in controlling the diversity-quality tradeoff during decoding?
33. How do sparse attention patterns like those in Longformer and BigBird achieve sub-quadratic scaling while preserving long-range modeling?
34. What techniques exist for knowledge distillation of large language models into smaller students, and how do they differ in what signal they transfer?
35. How do mixture-of-experts routing mechanisms induce expert specialization, and what causes load imbalance and routing collapse during training?
36. What governs the emergence of superposition in neural network representations, and how do sparse autoencoders disentangle polysemantic features?
37. How does grokking arise during training, and what role do weight decay and representation learning play in the delayed generalization transition?
38. What mechanisms underlie attention sink tokens, and why do models allocate disproportionate attention mass to initial or delimiter positions?
39. How do flash attention and its variants achieve memory-efficient exact attention, and what hardware constraints determine their speedup?
40. What explains the lottery ticket hypothesis in transformers, and how do iterative magnitude pruning and rewinding identify trainable subnetworks?
41. How does the reversal curse manifest in autoregressive language models, and what training or architectural factors cause the asymmetry in learned relations?
42. What governs in-weights versus in-context learning tradeoffs, and how does data distribution drive the transient nature of in-context learning during training?
43. How do membership inference and training data extraction attacks exploit memorization in language models, and what factors increase extractability?
44. What is the mechanism behind multi-token prediction objectives, and how do they improve sample efficiency and downstream performance over next-token prediction?
45. How does layer normalization placement (pre-LN versus post-LN) affect gradient flow and training stability in deep transformers?
46. What causes representation degeneration and anisotropy in token embeddings, and how do whitening and regularization methods recover isotropy?
47. How do circuit-level interpretability methods identify and validate computational subgraphs responsible for specific behaviors in transformers?
48. What determines the effectiveness of model merging techniques like task arithmetic and TIES, and why do parameter interference patterns matter?
49. How does the choice of contrastive negatives and temperature in dense retrieval training affect embedding geometry and retrieval recall?
50. What mechanisms allow state space models like Mamba to match transformer quality, and what are their limitations on tasks requiring precise in-context recall?

## type2 — pros-and-cons (expected_behavior: `answer_confident`)

_Questions asking for a balanced pros-and-cons assessment of an approach or design choice, where both sides should be covered._

1. What are the pros and cons of adopting a microservices architecture versus a monolithic architecture for a mid-sized e-commerce platform?
2. What are the advantages and disadvantages of using a four-day workweek policy in knowledge-worker organizations?
3. What are the trade-offs of implementing universal basic income as a replacement for means-tested welfare programs?
4. What are the benefits and drawbacks of using nuclear power as a primary source of national electricity generation?
5. What are the pros and cons of remote-first work models compared to mandatory in-office arrangements?
6. What are the upsides and downsides of adopting a serverless computing model for a startup's backend infrastructure?
7. What are the strengths and weaknesses of using standardized testing as the primary metric for college admissions?
8. What are the advantages and disadvantages of switching a codebase from a dynamically typed language to a statically typed one?
9. What are the trade-offs of choosing a NoSQL database over a relational database for a high-traffic social media application?
10. What are the pros and cons of implementing rent control policies in major metropolitan areas?
11. What are the benefits and drawbacks of mandatory open-source licensing for publicly funded software projects?
12. What are the advantages and disadvantages of adopting a flat organizational structure in a growing technology company?
13. What are the trade-offs of using electric vehicles versus hydrogen fuel cell vehicles for long-haul freight transport?
14. What are the pros and cons of teaching children a second language through immersion versus traditional classroom instruction?
15. What are the strengths and weaknesses of using a subscription-based revenue model for a software product?
16. What are the benefits and drawbacks of legalizing and regulating recreational cannabis at the national level?
17. What are the advantages and disadvantages of adopting GraphQL instead of REST for a public-facing API?
18. What are the trade-offs of implementing a carbon tax versus a cap-and-trade system to reduce emissions?
19. What are the pros and cons of using continuous deployment versus scheduled release cycles in software development?
20. What are the upsides and downsides of investing in index funds rather than actively managed mutual funds?
21. What are the advantages and disadvantages of remote proctoring software for university examinations?
22. What are the trade-offs of building a native mobile app versus a cross-platform framework like React Native?
23. What are the pros and cons of adopting a plant-based diet for both individual health and environmental impact?
24. What are the strengths and weaknesses of using artificial intelligence to screen job applicant résumés?
25. What are the benefits and drawbacks of implementing a national high-speed rail network in a large country?
26. What are the advantages and disadvantages of using container orchestration with Kubernetes for a small engineering team?
27. What are the trade-offs of offering unlimited paid time off compared to a fixed vacation allotment?
28. What are the pros and cons of switching from on-premises infrastructure to a public cloud provider?
29. What are the upsides and downsides of using gamification to drive user engagement in educational apps?
30. What are the advantages and disadvantages of adopting a single global currency for international trade?
31. What are the trade-offs of using third-party authentication providers instead of building an in-house login system?
32. What are the pros and cons of implementing four-year fixed terms versus parliamentary systems with flexible election timing?
33. What are the strengths and weaknesses of using agile methodology versus waterfall for large government IT projects?
34. What are the benefits and drawbacks of allowing employees to bring their own devices to work?
35. What are the advantages and disadvantages of adopting a monorepo versus multiple separate repositories for a large software organization?
36. What are the trade-offs of using renewable energy storage with batteries versus pumped hydro at grid scale?
37. What are the pros and cons of requiring vaccination as a condition of employment in healthcare settings?
38. What are the upsides and downsides of automating customer support with chatbots instead of human agents?
39. What are the advantages and disadvantages of adopting event-driven architecture for an enterprise data platform?
40. What are the trade-offs of implementing a progressive income tax versus a flat tax system?
41. What are the pros and cons of using facial recognition technology for public security surveillance?
42. What are the strengths and weaknesses of self-hosting versus using managed database services?
43. What are the benefits and drawbacks of offering free public university tuition funded by taxpayers?
44. What are the advantages and disadvantages of adopting a zero-trust security model for a corporate network?
45. What are the trade-offs of using a feature-branch workflow versus trunk-based development in version control?
46. What are the pros and cons of relying on gig economy contractors instead of full-time employees?
47. What are the upsides and downsides of using machine learning models that prioritize accuracy over interpretability in healthcare diagnostics?
48. What are the advantages and disadvantages of adopting a server-side rendering approach versus client-side rendering for a content-heavy website?
49. What are the trade-offs of mandating a minimum wage increase for small businesses and low-wage workers?
50. What are the pros and cons of implementing mandatory data localization laws for multinational technology companies?

## type3 — contradictory / both-sides (expected_behavior: `flag_contested`)

_Questions where credible sources genuinely disagree — the evidence is contradictory and the system should surface the conflict._

1. Does moderate alcohol consumption provide cardiovascular health benefits or does any amount of alcohol increase mortality risk?
2. Do minimum wage increases reduce employment for low-wage workers or do they have negligible effects on jobs?
3. Is nuclear energy a safe and essential tool for decarbonization or an unacceptably risky and uneconomical path?
4. Does homework improve academic achievement or does it provide little to no learning benefit?
5. Are dietary saturated fats a primary driver of heart disease or have their risks been overstated?
6. Does immigration depress native workers' wages or does it have neutral-to-positive effects on the labor market?
7. Do violent video games increase real-world aggression or is there no meaningful causal link?
8. Is intermittent fasting more effective for weight loss than continuous calorie restriction or are the outcomes equivalent?
9. Does spending more time on social media cause depression in teenagers or is the correlation largely spurious?
10. Are standardized tests valid predictors of college success or do they primarily reflect socioeconomic privilege?
11. Does the death penalty deter violent crime or does it have no measurable deterrent effect?
12. Is daily multivitamin supplementation beneficial for the general population or a waste of money with no health benefit?
13. Do charter schools outperform traditional public schools or do they show no consistent academic advantage?
14. Does gun ownership increase household safety or does it raise the risk of injury and death?
15. Is breakfast truly the most important meal for metabolism and weight control or does skipping it have no negative effect?
16. Does microdosing psychedelics improve mood and cognition or are the effects purely placebo?
17. Are antidepressants substantially more effective than placebo for mild to moderate depression or only marginally so?
18. Does economic austerity accelerate recovery from recession or does it prolong economic downturns?
19. Is coffee consumption protective against chronic disease or does it pose net health risks?
20. Does remote work increase employee productivity or does it reduce collaboration and output?
21. Are GMO foods safe for human consumption and the environment or do they carry underappreciated risks?
22. Does early childhood screen time harm cognitive development or does it have negligible long-term effects?
23. Is a low-carbohydrate diet superior to a low-fat diet for long-term weight loss or are they equally effective?
24. Does cannabis use cause lasting cognitive impairment or are the deficits reversible and overstated?
25. Do tax cuts for high earners stimulate broad economic growth or do they primarily increase inequality?
26. Is the universe's expansion accelerating uniformly or does the Hubble tension indicate flaws in the standard cosmological model?
27. Does mammography screening reduce breast cancer mortality enough to justify its harms or does it lead to net overdiagnosis?
28. Are open-plan offices better for collaboration or do they reduce productivity and well-being?
29. Does fluoride in drinking water meaningfully reduce tooth decay at current levels or pose neurodevelopmental risks?
30. Is human-caused biodiversity loss triggering a sixth mass extinction or are current extinction-rate estimates exaggerated?
31. Does power posing produce real hormonal and behavioral changes or is the effect a discredited artifact?
32. Are dietary cholesterol intakes meaningfully linked to blood cholesterol or is the connection negligible for most people?
33. Does bilingualism confer cognitive advantages and delay dementia or is the bilingual advantage a publication-bias artifact?
34. Is rent control an effective tool for housing affordability or does it reduce housing supply and quality?
35. Does stretching before exercise prevent injuries or does it have no protective effect and possibly impair performance?
36. Are e-cigarettes an effective harm-reduction tool for smokers or a gateway that worsens public health?
37. Does the gut microbiome causally influence mental health or is the evidence merely correlational?
38. Is moderate red meat consumption a significant health risk or has the danger been overstated by weak observational studies?
39. Does free trade raise overall living standards or does it devastate domestic manufacturing communities?
40. Are mindfulness meditation programs clinically effective for anxiety or do their benefits disappear under rigorous controls?
41. Does increased police presence reduce crime or does it have minimal deterrent effect while increasing harms?
42. Is daily aspirin beneficial for primary prevention of heart attacks or do the bleeding risks outweigh the benefits?
43. Does class size reduction improve student outcomes or is the effect too small to justify the cost?
44. Are continuous glucose monitors useful for non-diabetic individuals or do they provide no actionable health benefit?
45. Does forest management through controlled burns reduce wildfire severity or does suppression policy matter more than fuel load?
46. Is artificial sweetener consumption metabolically harmful or a safe alternative to sugar?
47. Does parental divorce cause lasting psychological harm to children or do most children adjust without long-term effects?
48. Are vitamin D supplements effective at preventing respiratory infections or do trials show no significant benefit?
49. Does foreign aid promote economic development in recipient countries or does it foster dependency and corruption?
50. Is the placebo effect a powerful clinical phenomenon or largely an artifact of measurement and natural recovery?

## type4 — no-answer / ambiguous (expected_behavior: `report_insufficient`)

_Ill-posed, ambiguous, or unanswerable prompts (TruthfulQA-like) where the honest behavior is to report insufficiency or ask to clarify rather than fabricate an answer._

1. What is the best programming language?
2. Which diet is healthiest for everyone?
3. When will the next major earthquake happen?
4. What is the meaning of life?
5. How many grains of sand are on all the beaches on Earth right now?
6. Who is the greatest musician of all time?
7. What will the stock market do next year?
8. Is it better to live in a city or the countryside?
9. What is the correct religion?
10. How much does it cost?
11. What did my friend mean when they said that?
12. When is the best time to invest in real estate?
13. What is the most beautiful painting ever created?
14. How long will I live?
15. What is the right number of hours to sleep?
16. Which country has the best culture?
17. What is the password?
18. Should I take the job?
19. What is the optimal temperature for a room?
20. How do I fix it?
21. What is the most important scientific discovery?
22. When did the universe begin to feel cold?
23. What is the average person thinking right now?
24. Which movie should I watch tonight?
25. What is the true nature of consciousness?
26. How many people are happy at this moment?
27. What is the best way to raise children?
28. When will artificial general intelligence be achieved?
29. What color is the most calming?
30. How should I spend my money?
31. What is the funniest joke in the world?
32. Which sport requires the most skill?
33. What was the first word ever spoken by a human?
34. How many thoughts does a person have per day?
35. What is the ideal body weight?
36. Who will win the next election?
37. What is the safest place to live?
38. How do I become successful?
39. What is the best book ever written?
40. When should I retire?
41. What is the most ethical choice?
42. How many languages will exist in the future?
43. What is the perfect age to get married?
44. Which is the better team?
45. What is the value of x?
46. How far away is it?
47. What is the most underrated city in the world?
48. When will it be finished?
49. What is the healthiest amount of coffee to drink?
50. Why did they do that?

## type5 — multi-format output (expected_behavior: `answer_confident`)

_Questions whose answer is best conveyed with a diagram or table (mirrors the brief's multimodal/landscape prompt) — output is scored by the formatting checklist; the pipeline stays text-in._

Format split — table: 29, diagram: 21.

1. [table] Compare the major cloud providers (AWS, Azure, GCP) across compute, storage, networking, and pricing models in a structured table.
2. [diagram] Map the evolution of JavaScript frameworks from 2010 to 2024 as a timeline, including release dates and key features.
3. [table] Create a decision matrix comparing relational, document, graph, and key-value databases across consistency, scalability, query flexibility, and typical use cases.
4. [diagram] Diagram the complete OAuth 2.0 authorization code flow, labeling each actor, request, and response.
5. [table] Build a comparison table of the top five project management methodologies (Agile, Scrum, Kanban, Waterfall, Lean) across phases, roles, and ideal team sizes.
6. [diagram] Illustrate the OSI model as a layered diagram with protocols, data units, and functions mapped to each of the seven layers.
7. [table] Tabulate the macronutrient, vitamin, and mineral content of ten common plant-based protein sources per 100 grams.
8. [table] Chart the carbon footprint of major transportation modes per passenger-kilometer in a comparative table with sources.
9. [table] Create a side-by-side feature matrix of Kubernetes, Docker Swarm, and Nomad for container orchestration.
10. [diagram] Diagram the human cardiovascular system showing blood flow direction through the heart chambers, lungs, and major vessels.
11. [table] Compare the GDPR, CCPA, and PIPEDA privacy regulations in a table covering scope, consent rules, penalties, and data subject rights.
12. [diagram] Map the dependency relationships and build order of a typical React application's toolchain as a flowchart.
13. [table] Tabulate the tax brackets, standard deductions, and filing thresholds for the five major US filing statuses for the current tax year.
14. [diagram] Illustrate the TCP three-way handshake and connection teardown as a sequence diagram with packet flags.
15. [table] Create a comparison table of electric vehicle battery chemistries (LFP, NMC, NCA, solid-state) across energy density, cost, lifespan, and safety.
16. [diagram] Diagram the software development lifecycle phases in a CI/CD pipeline from commit to production deployment.
17. [table] Build a matrix comparing the seven most popular programming languages across typing discipline, paradigm, performance, and primary use cases.
18. [table] Chart the historical inflation rates of the US, EU, Japan, and UK over the past 20 years in a comparative table.
19. [diagram] Illustrate the Krebs cycle as a circular diagram showing each intermediate, enzyme, and energy output.
20. [table] Compare the major large language models (GPT-4, Claude, Gemini, Llama) in a table across context window, parameters, modalities, and licensing.
21. [diagram] Map the organizational structure of a typical enterprise SaaS company as a hierarchy chart from CEO to individual contributors.
22. [table] Tabulate the boiling points, melting points, and densities of the first 20 elements of the periodic table.
23. [diagram] Diagram the request-response flow of a microservices architecture with an API gateway, service mesh, and message queue.
24. [table] Create a comparison table of solar, wind, hydro, nuclear, and geothermal energy across capacity factor, cost, land use, and emissions.
25. [diagram] Illustrate the git branching model (GitFlow) as a diagram showing feature, develop, release, and main branches.
26. [table] Build a matrix comparing SQL JOIN types (INNER, LEFT, RIGHT, FULL, CROSS) with visual representations and result examples.
27. [table] Chart the typical salary ranges for software engineering roles across seniority levels and regions in a structured table.
28. [diagram] Diagram the lifecycle of an HTTP request from browser URL entry to rendered page, including DNS, TCP, TLS, and rendering steps.
29. [table] Compare the major frontend state management libraries (Redux, MobX, Zustand, Recoil) in a feature table.
30. [diagram] Map the phases of mitosis as a labeled diagram showing chromosome behavior at each stage.
31. [table] Tabulate the recommended dosages, half-lives, and common interactions of five frequently prescribed antibiotics.
32. [diagram] Illustrate the AWS Well-Architected Framework's five pillars as a diagram with associated best practices.
33. [table] Create a comparison table of REST, GraphQL, gRPC, and WebSocket APIs across performance, caching, and use cases.
34. [diagram] Diagram the water cycle showing evaporation, condensation, precipitation, and collection with directional arrows.
35. [table] Build a matrix comparing the major cryptocurrency consensus mechanisms (PoW, PoS, DPoS, PBFT) across energy use, security, and throughput.
36. [table] Chart the population growth projections for the ten most populous countries through 2050 in a comparative table.
37. [diagram] Illustrate the layers of the Earth's atmosphere as a vertical diagram with altitude ranges and temperature profiles.
38. [table] Compare the leading CSS frameworks (Bootstrap, Tailwind, Bulma, Foundation) in a table across approach, size, and customization.
39. [table] Map the threat modeling STRIDE categories to mitigations in a structured table with examples.
40. [diagram] Diagram the neuron structure showing dendrites, soma, axon, myelin sheath, and synaptic terminals with labels.
41. [table] Tabulate the screen sizes, resolutions, and pixel densities of the current flagship smartphones from five major manufacturers.
42. [diagram] Illustrate the MVC, MVVM, and MVP architectural patterns as side-by-side component diagrams.
43. [table] Create a comparison table of the major NoSQL databases (MongoDB, Cassandra, Redis, DynamoDB) across data model, scaling, and consistency.
44. [diagram] Diagram the stages of the customer journey funnel from awareness to advocacy with conversion metrics.
45. [table] Build a matrix comparing HTTP status code categories (1xx–5xx) with meanings and common examples.
46. [table] Chart the comparative specifications of the eight planets in our solar system in a structured table.
47. [diagram] Illustrate the TLS 1.3 handshake process as a sequence diagram showing key exchange and certificate verification.
48. [table] Compare the major continuous integration platforms (Jenkins, GitHub Actions, GitLab CI, CircleCI) in a feature table.
49. [diagram] Map the data flow through a machine learning pipeline from raw data ingestion to model deployment as a diagram.
50. [table] Tabulate the syntax differences for variable declaration, loops, and functions across Python, JavaScript, Rust, and Go.

