# CreativeSignal — case study

## The problem

Creative teams in performance marketing decide what to make next from a mix of instinct, whatever competitor ads they happened to see, and a deck someone made last quarter. The obvious AI product here is "tell me what creative works." That product cannot be built honestly, because **the data to support it does not exist publicly**: the Meta Ad Library exposes no spend, impressions, or CTR for ordinary commercial ads.

So the product question became: *what is genuinely useful, and truthful, given only what can be observed?*

The answer CreativeSignal commits to: **traceable prevalence**. Not "this converts," but "this pattern appears in 22 of 34 retrieved ads, here are their IDs and source links, and here is what that does and does not tell you." Every output is a hypothesis with its evidence attached.

## The decision that shaped everything

The honesty rule appears verbatim in the UI, the README, and every generated report:

> Every insight is traceable to examples; every recommendation is a hypothesis, not a performance claim.

The important part was refusing to let it be prompt wording. Prompts drift, and a model told to be careful is still a model. So it is enforced structurally in four places:

1. **Citation self-check** — a concept citing evidence it wasn't given is *dropped*, not flagged with a caveat.
2. **Coverage floor** — below 3 retrieved examples the agent reports the coverage gap instead of producing patterns. The honest failure mode is a first-class output.
3. **Insight rules** — rendered through a function whose output a test forbids from containing *performs, works, converts, wins, best, effective*.
4. **MCP payloads** — the honesty rule and coverage statement travel inside the JSON, because that is the one surface where output leaves our UI and there is no footer to rely on.

A test suite can't verify honesty. It can verify that the specific mechanisms which make dishonesty easy are closed.

## What I'd do with production data

The gap between this and a real product is data, not architecture.

- **Real engagement data changes the label, not the framing.** With spend and impressions, `proxy_bucket` becomes an actual outcome variable — but the correct language stays correlational, because ad performance is confounded by budget, targeting, and seasonality. I'd resist the pressure to relabel "prevalence" as "performance" the moment a number appears; the honest version is "among ads with comparable spend and audience."
- **The two-stage annotator is where the cost story lives.** LR-first with LLM escalation only below a confidence threshold is a real lever: at 10k creatives, the difference between a 20% and a 60% escalation rate is most of the annotation budget. The threshold table exists to make that a business decision rather than a default.
- **The golden set is the highest-leverage artifact and the least glamorous.** Everything downstream — weight tuning, the similarity floor, whether hybrid actually beats keyword — is unmeasurable without it. I'd build it first next time, before writing retrieval code.
- **The corpus needs provenance, not size.** 200 ads with ad-library URLs, advertisers, and run durations beat 5,000 scraped strings. Tier-3 is the whole product; Tier-2 turned out to be near-useless (see below).

## What went wrong, and what it taught me

**The corpus collapsed from 300 to 9.** The plan assumed ~300 rows. Filtering two Hugging Face ad-copy datasets to skincare yielded 24. Reading the actual rows — rather than trusting the count — showed that 4 were false positives (clothes irons and garment steamers matched on *"wrinkle"*; hair serum on *"serum"*), and that the two "independent" datasets overlapped almost entirely, many rows byte-identical. **9 unique ads.**

That number invalidated every eval in the plan. The choice at that point was to generate 100–200 plausible Meta Ad Library records and proceed, or to stop and report. I stopped. Fabricating advertisers, ad-library URLs, and observation dates would have made every downstream citation trace to invented data — in a project whose entire thesis is traceability. **The blocker is more valuable than the fake result would have been**, and a capstone that publishes numbers it can't defend teaches the wrong lesson.

**Reading data beats counting it.** The row count looked fine at 24. Every real problem was visible only in the rows. This is the same discipline as the L1 "failure reading" habit the eval plan schedules — and it applies to ingest, not just eval.

**Two bugs that would have shipped.** Both were invisible in normal use:
- A **segfault** killed the server on the first search — no traceback, nothing in the logs. The plausible diagnosis (PyTorch in a thread) was wrong and cost a fix attempt. The macOS crash report named the real culprit in one step: PyArrow's mimalloc allocator. Lesson: a segfault produces no Python traceback, so read the native one instead of guessing from symptoms.
- **BM25's IDF goes negative** for terms appearing in more than half the corpus. Filtering on `score > 0` silently discarded valid matches — and the bug got *worse* as the corpus got smaller, which is exactly backwards. It surfaced three layers up, as an agent coverage-check failure. A guard built for honesty caught a correctness bug.

**Pinning direct dependencies is not pinning dependencies.** Twice, a *shared transitive* dependency broke a subsystem far from where it was chosen — once taking down the entire test suite at collection time (Phoenix registers a pytest plugin, so its import health is everyone's problem), once making the MCP server unimportable. Both surfaced as "the new module is broken" rather than "the pin is wrong." A lockfile is now a deliverable.

## Model routing: what actually differed

The plan routed judgment work to Claude Code and mechanical work to a cheaper backend. Executing most of it on one tier, the split that actually mattered was not model quality — it was **which decisions can be made without data**.

The tasks that genuinely needed judgment were the ones where the correct answer was *"refuse, and say why"*:

- Not fabricating Tier-3 data.
- Refusing to train the classifier and the tree, rather than fitting on 9 rows and reporting a meaningless accuracy.
- Declining to add a similarity floor tuned on three hand-picked queries — a floor set slightly too high silently returns nothing, which is worse than returning weak results with an honest coverage statement.
- Leaving three constants explicitly uncalibrated, each with the procedure for setting it written down.

A cheaper model would very likely have produced the tempting version of each: plausible synthetic ads, a 100%-accuracy tree (trained on features that *are* the label), a tuned threshold. Every one of those looks like progress in a diff and is worse than nothing. **The expensive judgment wasn't writing the code — it was knowing which code not to write.**

The mechanical/judgment split in the plan holds, but the boundary is better drawn as: *does this task have a defensible answer given the data that exists?* If not, it is a judgment task regardless of how routine it looks.

## Status, honestly

Built and tested: retrieval, agent, reviewer, MCP server, four-page app, 214 tests, deploy config.

Not done: the corpus (Tier-3 curation, ~2h of human work), the golden set, and therefore every number. The LLM generation paths are built but were never executed — no API key was reachable during the build.

The architecture is finished. The measurement isn't started. Both statements are in the README, because a reader who installs this deserves to know which is which before they run it.
