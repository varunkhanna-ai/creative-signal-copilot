# Data Governance — CreativeSignal

**v1 — W0.4.** License fields below were read from each dataset's Hugging Face card at download time (2026-08-28), per the standing rule "record at Week 0, don't assume" (implementation.md §0.1). Where a card declares no license, that is recorded as *undeclared* — **not** as permissive.

Reproduce the Tier-1/Tier-2 snapshot with:

```bash
make download
```

## Tier summary

| Tier | Source | Rows available | Rows in corpus | License as declared on the card |
|---|---|---|---|---|
| Tier-1 | `PeterBrendan/AdImageNet` | — (gated) | 0 | `mit` |
| Tier-2 | `smangrul/ad-copy-generation` | 1000 | 11 (skincare filter) | **none declared** |
| Tier-2 | `jaykin01/advertisement-copy` | 1141 | 13 (skincare filter) | `unknown` (declared literally as "unknown") |
| Tier-3 | Meta Ad Library, hand-curated | — | 0 — **not yet curated** | per-record `rights_note` |

## Tier-1 — `PeterBrendan/AdImageNet`

- **License on card:** `mit`.
- **Access:** the dataset is **gated** as of this run — `load_dataset` raises `DatasetNotFoundError: gated dataset ... must be authenticated`. The MIT declaration governs the content; the gate is a separate access control on the files, and accepting it is a per-account action.
- **Status:** not in the corpus. Off the critical path (ad images, no ad copy). See decision-log B4.
- **If ingested later:** MIT permits redistribution with attribution. Even so, images are not redistributed from this repo — `data/raw/` is gitignored and rebuilt by `make download`.

## Tier-2 — the two ad-copy datasets

Both are synthetic/generated ad copy, not observed live ads. This matters for the README's real-vs-simulated section: **Tier-2 carries no provenance** — no advertiser, no ad-library URL, no observation date, no run duration. Rows enter the corpus with `source_url = None` and a `rights_note` that says so.

### `smangrul/ad-copy-generation`
- **License on card:** none declared (the card has no `license` field at all).
- **Shape:** single `content` column, Llama-2 instruction format — the product, description, and ad are packed into one string and are parsed apart at load time.
- **Treatment:** undeclared license is **not** permission to redistribute. Used locally for retrieval only; not republished. Not redistributed in this repo.

### `jaykin01/advertisement-copy`
- **License on card:** declared literally as `unknown`.
- **Shape:** `product`, `description`, `ad` columns (plus an empty `Unnamed: 3` artifact column, dropped at load).
- **Treatment:** same as above — local use only, not redistributed.

**Governance finding (W0.4):** two of the three HF datasets carry no usable license declaration. Under the "don't assume" rule this constrains the project to local, non-redistributive use of Tier-2 — which is consistent with how the repo already works (`data/raw/` gitignored, corpus rebuilt from source by the grader). It does mean **Tier-2 text should not be reproduced verbatim in the README, the demo video, or any published artifact**; cite it by row id and characterize it instead.

## Tier-3 — Meta Ad Library, hand-curated

**Not yet curated (W0.3 outstanding — decision-log B1).** The intended treatment, unchanged:

- Metadata + ad copy stored per record; **screenshots only where Ad Library terms permit**.
- Every record carries its own `rights_note` — this is why `rights_note` is a required, non-null field on `Creative` rather than a tier-level constant.
- Provenance per record: `ad_library_url`, `advertiser`, `platform`, `date_observed`, `start_date`.
- F1 longevity-proxy fields (`days_active`, `variant_count`, `proxy_bucket`) are computed deterministically from `start_date` / `date_observed` and stay in `creatives`, per decision-log Entry #3.
- Public commercial ads in the Ad Library expose no engagement data (no spend, impressions, or CTR for non-political ads) — which is exactly why the label is a longevity proxy (F1) and why all wording around it stays descriptive.

## Secrets

`ANTHROPIC_API_KEY` is the only secret and the only vendor key on any path. It comes from `.env` locally and `st.secrets` when deployed. Both `.env` and `.streamlit/secrets.toml` are gitignored. Retrieval runs with no key at all.

## What is *not* collected

No scraping, no live Meta/TikTok API calls, no user data, no PII. `sources/live_stubs.py` stays `NotImplementedError` by design — it exists to prove the `CreativeSource` interface generalizes, not to work.
