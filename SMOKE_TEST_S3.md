# Smoke Test — S3 hierarchical fidelity (`compare()`)

A runbook to validate the S3 hierarchical fidelity metric on **real book-scale
data** — the per-chapter arc + pacing comparison added to `compare()`. The unit
tests prove the math on synthetic curves; this checks whether the numbers *mean*
anything on an actual 6-chapter novella, and — the real goal — **calibrates the
⚠️ thresholds** (currently 60%) against measured noise instead of a guess.

Run it locally (you, or Gemini). It needs the S2-generated novella from
`SMOKE_TEST_S2.md` and the `deep` extras. The three tiers go cheap → expensive:
an identity sanity check (no LLM), a re-extraction **noise floor** (one deep
run), then the full analyze→generate→re-analyze **round-trip** (one book
generation).

---

## 0. Setup

```bash
cd literatureAnalyzer
uv sync --extra deep
# you should already have these from the S1/S2 runs:
#   ../Endless/out/novella.txt      the generated lighthouse novella (headers included)
#   novella.json                    its fresh --deep deconstruction (6 chapters)
# if not, regenerate novella.json:
uv run deconstruct ../Endless/out/novella.txt --deep --fresh -f json -o novella.json
```

Every command below writes a Markdown fidelity report (`-o fidelity*.md`); add
`-f json` on any of them to get the raw `Divergence` with exact per-chapter
numbers.

## 1. Identity sanity — the metric's floor is 100% (no LLM)

Compare the analysis against **itself**. This spends no tokens; it confirms the
hierarchy path fires on a real 6-chapter book and that identity scores perfect.

```bash
uv run deconstruct --from novella.json --compare novella.json -o fidelity_self.md
```

**Expect:** `Overall structural fidelity: 100%`. In `fidelity_self.md`, the
**Per-chapter fidelity** table lists all 6 chapters, every row `arc fidelity 100%`
and `pacing 100%`, with `beats A → B` equal on both sides. If the hierarchy block
is missing, the analysis isn't chaptered — re-check that `novella.txt` carries
`CHAPTER …` headers (the S2 orchestrator injects them in book mode).

## 2. Re-extraction noise floor — the calibration step

Deconstruct the **same novella a second time**, fresh, and compare the two
independent extractions. The text is identical, so *any* divergence here is pure
**measurement noise** — LLM nondeterminism in the arc sampling and beat grouping,
not real structural change. This is the number that tells us where to set ⚠️.

```bash
uv run deconstruct ../Endless/out/novella.txt --deep --fresh -f json -o novella_reextract.json
uv run deconstruct --from novella.json --compare novella_reextract.json -o fidelity_noise.md
```

**Read `fidelity_noise.md` carefully — this is the point of the test:**
- **Overall** should be high (≳90%). It won't be exactly 100% — that gap *is* the
  extraction noise floor.
- In the per-chapter table, note the **lowest** `arc fidelity` and `pacing` across
  the 6 chapters. That's the worst-case noise.
- **Calibration question:** does any chapter trip the ⚠️ (< 60%) on *identical
  text*? If yes, the threshold is too aggressive — noise is masquerading as drift,
  and we should lower the flag cutoff (or smooth the arc sampling). If the noisy
  floor sits comfortably above 60% (say chapters land 80–100%), the 60% cutoff is
  well-placed: a real ⚠️ in step 3 then means genuine structural drift, not noise.

Record the min per-chapter arc% and pacing% — those two numbers set the bar.

## 3. The full round-trip — the real fidelity score

Now the canonical S3 measurement: take the novella's deconstruction, regenerate a
**new** book from those same bones, deconstruct *that*, and compare. This scores
how much structure survives a whole analyze → generate → re-analyze cycle.

```bash
# emit the deconstruction as a one-file handoff, regenerate in Endless:
uv run deconstruct --from novella.json --emit-endless roundtrip.md --as-doc
cd ../Endless
uv run story --from-doc ../literatureAnalyzer/roundtrip.md --skip-preflight -o out/novella_rt.txt
# deconstruct the regeneration and compare it against the original analysis:
cd ../literatureAnalyzer
uv run deconstruct ../Endless/out/novella_rt.txt --deep --fresh -f json -o novella_rt.json
uv run deconstruct --from novella_rt.json --compare novella.json -o fidelity_roundtrip.md
```

> Orientation matters: `--from` is the **regeneration** (candidate A), `--compare`
> is the **original** (B). World/beat overlap is directional — it asks "do the
> original's characters/beats survive into the regeneration?" — so the original
> must be the `--compare` argument.

**Expect:** an `Overall structural fidelity` that is meaningfully **above the
step-2 noise floor's inverse** — i.e. the round-trip should lose more than pure
re-extraction (it's a real regeneration, not the same text), but the shared arc,
cast, and chapter structure should still score well (a passing round-trip is
roughly ≳70% overall with most chapters green). The per-chapter table shows
*where* the regeneration diverged — a chapter whose arc flipped or whose beat
count ballooned lights up with ⚠️, next to the chapters that held.

## 4. What the numbers tell us

| reading | interpretation |
|---|---|
| step 1 = 100% | metric identity holds; hierarchy fires on a real book |
| step 2 overall ≳ 90%, all chapters > 60% | noise floor is below the ⚠️ cutoff → **thresholds calibrated**, ship as-is |
| step 2 trips a ⚠️ on identical text | ⚠️ too aggressive → lower cutoff or smooth arc sampling before finishing S3 |
| step 3 overall clearly > (step-2 loss) | round-trip loses more than noise → the metric is measuring **real** structural change, as intended |
| step 3 per-chapter ⚠️ aligns with a rough patch you can see in the prose | the localization works — the number points at a real drift |

The deliverable from this run is two things: the **step-2 min per-chapter
numbers** (do they clear 60%?) and the **step-3 overall + per-chapter table**.
Together they answer "is the hierarchical metric trustworthy, and is the ⚠️
threshold right?" — the gate before we build S3 increment 3 (persistent
transposition mapping) on top of it.

---

## What a healthy run looks like

| check | healthy signal |
|---|---|
| identity | step 1 overall 100%; 6 chapters, all rows 100% |
| noise floor | step 2 overall ≳ 90%; no chapter ⚠️ on identical text |
| threshold | worst step-2 per-chapter arc/pacing sits above 60% |
| round-trip | step 3 overall ≳ 70%; cast + chapter count preserved; drift localized per chapter |
| localization | any step-3 ⚠️ chapter matches a spot the prose actually wandered |

If step 2 says the noise floor is clean and step 3 produces a believable
per-chapter fidelity picture, the hierarchical `compare()` is validated and
**S3's compare side is done** — remaining work is increment 3 (the global
entity-mapping table for transposition), the one thread that isn't about
comparison.
