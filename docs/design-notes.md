# Pedal Forge: design notes

Status: draft, written before any plugin code. Date: 26 October 2026.

Every constant below carries a confidence level, as in faust-pedalkit’s `AGENTS.md`:

* **documented**: from a specification, SDK header or official documentation, linked.
* **reported**: from a README, paper or third party, not verified here.
* **inferred**: derived from other sources or measurements.
* **chosen**: a design decision, with its intent stated.

Numbers in square brackets refer to the [source list](#sources).

## 1. The idea

A player describes a sound in words: “fat, round bass drive that keeps the low end clean”, “thin, fizzy lo-fi guitar”, “just tighten the lows a little”. The plugin builds an effect chain from faust-pedalkit’s tested blocks [1], sets each block, and exposes the settings that matter on a small bank of macro controls the player can then turn by hand or automate.

What a player gets that existing tools do not give them:

* **A starting point from a description, without menu-diving.** Preset browsers need the player to know the vocabulary of the product. Here the vocabulary is the player’s own.
* **A chain they can read and trust.** The result is a list of named blocks with settings in real units (dB, Hz, %), each built from the same measured, documented DSP as faust-pedalkit’s plugins. Nothing is generated at run time, so there is no new code to review and no untested DSP.
* **Honest uncertainty.** Every decision carries a confidence value. When the model is unsure, the plugin says so and either uses a safe default or asks the player a short question (“more bass or more guitar?”) rather than guessing.
* **Offline by default.** The model runs on the player’s machine. No account, no network and no description leaves the computer unless the player enables the hosted backend.

Text-to-plugin generators exist (faust-pedalkit’s ecosystem page lists some [1, `docs/ecosystem.md`]), but they generate code or a whole plugin per request. Pedal Forge only chooses among blocks that are already tested.

## 2. Block diagram

```text
 player's description (text)
          │
          ▼
 ┌──────────────────┐   state (JSON) +    ┌───────────────────────┐
 │ question builder  │── typed questions ─▶│ decision model         │
 │ (fixed bank,      │                     │ (local server, or the  │
 │  eval/questions.py)│◀── typed answers ──│  hosted API; background│
 └──────────────────┘   + probabilities    │  thread, never audio)  │
          │                                └───────────────────────┘
          ▼
 ┌──────────────────┐  low confidence?  ┌──────────────────────────┐
 │ confidence gate   │─────────────────▶│ default, or ask the player│
 └──────────────────┘                   └──────────────────────────┘
          │ answers above threshold                 │
          ▼                                         ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ assembler (deterministic): block manifest + answers → chain     │
 │ spec (blocks, settings, macro mapping, latency), validated       │
 └────────────────────────────────────────────────────────────────┘
          │ chain spec (message passed to the audio thread, no locks)
          ▼
 ┌────────────────────────────────────────────────────────────────┐
 │ audio thread: input → [block] → [block] → … → limiter → output   │
 │ new chain fades in over the crossfade time while the old fades   │
 │ out; macro slots 1–8 drive the chain's mapped parameters         │
 └────────────────────────────────────────────────────────────────┘
```

The model sits entirely on the left of the diagram. It never sees audio and its answers are data, so the assembler can be tested exhaustively with recorded answers, and the audio path can be tested with the same offline renders faust-pedalkit uses.

## 3. The role of the model

The model is a **typed-decision model** (“System One” in the vendor’s terms [4, 18]). It receives a state (text or JSON) and a set of typed questions, and returns, in one pass and without generating text, a choice, a score or a probability for each, with a probability distribution behind it [8]. It is a classifier with a natural-language interface.

Why this fits:

* The output space is small and closed (a few block types, a few variants, a few levels), which is exactly what typed questions express.
* Every answer comes with a distribution, so the plugin can measure and act on uncertainty.
* Decisions are quick. Vendors report tens to hundreds of milliseconds [4, 6, 8]; these are reported values until `make eval` measures them on real hardware.
* There is nothing to sandbox: answers are validated against the question’s options, and anything else is an error.

### Alternatives considered

| Approach | What it would do | Why it is out of scope for the first version |
|---|---|---|
| Code-generating LLM | Write Faust (or C++) for the requested sound, compile it, load it | Generated DSP needs the same review as hand-written DSP (faust-pedalkit’s ecosystem page makes the same point [1]); compiling in a plugin needs a compiler at run time; failures can be unsafe (instability, full-scale noise); and the results cannot be tested in advance. Large models also need far more memory and time per request. |
| Generative LLM with JSON output | Produce a chain description as free text constrained to a schema | Works, but gives no calibrated per-decision confidence, needs constrained decoding to be reliable, and is slower and larger than a typed-decision model for the same closed choice. It is a reasonable fallback backend if typed-decision models fail the evaluation. |
| Neural audio (end-to-end models of a sound) | Process the audio with a network trained or conditioned on the description | Runs on the audio thread, so it costs CPU per sample and adds latency; it cannot be measured block by block; its behaviour at extreme inputs is hard to bound; and its training data would need its own licence review. It also departs from faust-pedalkit’s measured, documented DSP. |
| Rules only (keyword matching) | Map words to blocks with a hand-written table | Cheap and transparent, but brittle to phrasing. It is kept as the mock backend and as the offline fallback when no model is installed. |

## 4. The block vocabulary

The assembler can only use blocks it knows: their names, inputs, parameters with units and ranges, and latency. faust-pedalkit has two partial descriptions of its blocks today, neither of them a machine-readable manifest:

* the function table in `AGENTS.md` and `docs/development/pedalkit-lib.md` [1], which covers `pedalkit.lib` (oversamplers, shapers, `biasShift`, `tf2a`/`tf1a`, `safety`) but in prose;
* the browser designer’s palette, `web/designer/blocks.js` [3], which is machine-readable but JavaScript, covers only the designer’s blocks (gain, waveshaper with four variants, filter with five, DC blocker, mix), and carries designer-chosen ranges.

**Pedal Forge needs a manifest, and it does not exist yet.** It must be proposed to faust-pedalkit as a separate change (an issue, then a pull request there), reviewed under that repository’s rules. Nothing in this repository may assume it exists, and nothing here modifies faust-pedalkit. Until it lands, the harness uses the block and variant names from `blocks.js` as question options, which is all it needs.

### Proposed format: `blocks.json`

One JSON file, generated in faust-pedalkit from a single source (so it cannot drift from the DSP), checked by a test there, and shipped in its release tarball. Proposed fields (all **chosen**):

```json
{
  "schema": "pedalkit-blocks/1",
  "library_version": "0.1.0",
  "blocks": [
    {
      "id": "waveshaper.asym",
      "label": "Asymmetric tanh",
      "description": "Asymmetric tanh clipper; generates even-order harmonics.",
      "faust": "pk.asymTanh",
      "inputs": ["In"],
      "outputs": 1,
      "oversampled": true,
      "latency_samples": 32,
      "memoryless": true,
      "params": [
        {"key": "drive", "label": "Drive", "unit": "dB", "min": 0, "max": 40, "default": 12,
         "law": "linear", "smoothing": "si.smoo", "confidence": "chosen"},
        {"key": "pos", "label": "Positive ceiling", "unit": "dB", "min": -24, "max": 0, "default": -3,
         "law": "linear", "confidence": "chosen"}
      ]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `schema` | Format name and major version; a breaking change bumps it |
| `library_version` | faust-pedalkit version the manifest describes |
| `id` | Stable identifier, `<type>.<variant>`; never reused for a different block |
| `label`, `description` | Neutral display text (no trademarks; British English) |
| `faust` | Function or expression in `pedalkit.lib` or the Faust standard library |
| `inputs`, `outputs` | Input port labels and output count, as in `blocks.js` |
| `oversampled`, `latency_samples` | Whether the block uses `pk.oversample4`, and its reported delay (32 per `pk.os4Latency` [1]) |
| `memoryless` | Whether it may go inside an oversampler |
| `params[]` | `key`, `label`, `unit` (dB, Hz, %, oct, ms or none), `min`, `max`, `default`, `law` (`linear` or `log`), and the confidence of the range |

A JSON Schema for the file would go in faust-pedalkit with it.

## 5. The typed-question schema

### Question types

The wire format follows the Jev request shape, which OpenJev and system-one also serve [6, 7, 8] (field names verified in OpenJev’s README and s1’s server source; the hosted API’s own reference could not be reached from here, so its shape is **reported** [18]):

| Type | Request | Answer | Used for |
|---|---|---|---|
| `choice` | `criteria: {option: description}` | `choice`, `probabilities` per option, `confidence` | Block type, variant, instrument |
| `score` | `criteria: [level 0, level 1, …]` (2 to 10 levels) | `score` (expected level), `probabilities` per level, `confidence` | Amounts: drive, brightness |
| `noul` (yes/no) | optional `criteria: {true, false}` | `noul` = P(yes) | Whether to include a block; whether the request is in vocabulary |

The request also carries `model` and `state`. The state is a JSON object (**chosen**) so later versions can add context (the current chain, the instrument from a previous answer) without changing the questions:

```json
{"task": "Choose guitar or bass effect blocks for a player's description.",
 "description": "<what the player typed>"}
```

APIs that take a string state get this JSON serialised; s1’s server accepts the object as is [6].

### The question bank

The first bank has nine questions (`eval/questions.py`, whose wording is the prompt and is **chosen**), chosen to cover each decision the assembler makes with the `blocks.js` vocabulary, plus one that detects requests the vocabulary cannot meet:

| Key | Type | Decides | Default (chosen) | Threshold (chosen) |
|---|---|---|---|---|
| `instrument` | choice: guitar, bass | DC blocker corner, high-pass default, ranges | `guitar` (ask if below threshold) | 0.70 |
| `in_vocabulary` | yes/no | Whether the request needs blocks that do not exist (delay, reverb, modulation) | yes | 0.70 |
| `needs_drive` | yes/no | Whether a waveshaper is used at all | no | 0.65 |
| `shaper` | choice: soft, asym, knee, softhard | Waveshaper variant | `soft` | 0.50 |
| `drive_amount` | score: 5 levels, clean to saturated | Drive (dB) | level 1 | 0.45 |
| `tone_filter` | choice: none, lowpass, highpass, peak | Main filter | `none` | 0.50 |
| `brightness` | score: 5 levels, very dark to very bright | Filter corner frequency | level 2 | 0.45 |
| `mid_shape` | choice: scooped, flat, boosted | Peaking EQ gain sign | `flat` | 0.50 |
| `keep_lows` | yes/no | Parallel clean low path through a mix block | no | 0.65 |

Defaults are the least surprising setting: no drive, flat EQ, middle levels. Thresholds are **chosen** starting points: higher for questions that change the chain’s structure (instrument, in-vocabulary, whether to drive), lower for settings the player will adjust with the macros anyway. Choice thresholds sit above chance (0.50 against 0.25 for four options). They will be revised from the calibration results in `make eval`, and the revision recorded here.

### How confidence is used

* The harness and the plugin compute **their own** confidence from the returned probabilities: the top probability, `max(p)`, for choice and score, and `max(p, 1 − p)` for yes/no. Backends define their own `confidence` field differently (OpenJev uses `1 − H(p)/ln K` [8]; s1 returns the top probability [6]), so using it directly would make thresholds mean different things per backend. The backend’s own value is still recorded. (**chosen**)
* Calibration is measured as expected calibration error (ECE) over top-label confidence with 10 equal-width bins [16] (bin count **chosen**, the common default in [16]), plus the Brier score.
* An answer below its threshold is not used. The assembler takes the default, or, for `instrument` and `in_vocabulary`, asks the player a short question built from the same options (“Is this for guitar or bass?”). An out-of-vocabulary request gets a message naming what is missing rather than a partial chain.
* Answers are independent per question, so the assembler resolves conflicts by rule: `needs_drive = no` disables `shaper` and `drive_amount`; `tone_filter = none` disables `brightness`; `keep_lows` applies only for bass.

## 6. Consuming faust-pedalkit

| Option | For | Against |
|---|---|---|
| **Pinned git submodule** at a commit or tag | Exact source available offline; the plugin can compile the blocks with the same `pedalkit.lib`; easy to bisect; changes are explicit commits here | Contributors must `git submodule update`; ties the build to faust-pedalkit’s toolchain (Faust, its Makefile); pulls the whole repository, including docs and schematics |
| **Release tarball** with checksum | Small, versioned, signed by checksum; matches what users install; no toolchain coupling if the tarball carries the manifest and compiled blocks | faust-pedalkit releases are per-effect plugin tarballs today, not a library release, so it would need a new release type; harder to patch locally |

Recommendation (**chosen**): a pinned submodule under `vendor/faust-pedalkit/` once there is DSP to build, moving to a library release tarball if faust-pedalkit adds one alongside the manifest. Either way the pinned version is recorded in one place and the manifest’s `library_version` is checked against it. Nothing is vendored now: this session has no DSP.

## 7. Parameters the host can rely on

Hosts store automation and saved state by parameter index or ID, so the parameter set is fixed:

| Parameter | Range | Default | Confidence |
|---|---|---|---|
| Macro 1 … Macro 8 | 0 to 1 (shown as 0 to 100 %) | 0.5 | count and range **chosen** |
| Output | −24 to +12 dB | 0 dB | **chosen** |
| Mix (dry/wet) | 0 to 100 % | 100 % | **chosen** |

Eight macros (**chosen**) is enough for a six-block chain’s most useful controls (drive, ceiling, frequency, EQ gain, blend) without a wall of unlabelled knobs. Each assembled chain maps each macro to one block parameter with that parameter’s range and law; unused macros do nothing.

Renaming at run time, by format:

| Format | Can a parameter’s name change at run time? | Source |
|---|---|---|
| CLAP | Yes: `clap_host_params.rescan(CLAP_PARAM_RESCAN_INFO)` covers a name change and “takes effect immediately”. A change of `min_value`/`max_value` needs `CLAP_PARAM_RESCAN_ALL`, which is only allowed while deactivated. | **documented** [11] |
| VST3 | The plug-in can call `restartComponent(kParamTitlesChanged)`, and the host should re-read titles, units and flags. Host support is inconsistent in practice, and one wrapper also sends `kLatencyChanged` with it, which some hosts treat as a restart. | flag **documented** [13]; host behaviour **reported** [15] |
| LV2 | Port names are in the plug-in’s static Turtle data, which the host reads at discovery; the core specification has no message to rename a port. The dynamic-manifest extension lets a library generate its data at load time, but not rename ports of a running instance. | **inferred** from [14] |

So (**chosen**): the macro names stay neutral and fixed (“Macro 1”), their ranges stay 0 to 1 in every format, and the meaning of each macro is shown as value text where the format allows it (CLAP `value_to_text`, VST3 `getParamStringByValue`) and in the plugin’s own status display. CLAP may additionally rename macros through `RESCAN_INFO`; that is an optional extra, not something any feature depends on.

## 8. Latency handling

Blocks have different latencies (an oversampled waveshaper adds 32 samples [1]), so swapping chains could change the plugin’s delay. Reporting a new latency is disruptive in every format: CLAP allows a change only during `activate`, so an active plugin must call `request_restart()` [12]; VST3 needs `kLatencyChanged`, after which the host deactivates and reactivates the plug-in [13]; LV2 reports latency on a control output port (`lv2:designation lv2:latency`; the older `lv2:reportsLatency` port property is deprecated [14]), and hosts differ in how often they re-read it.

Design (**chosen**):

* The plugin reports a **fixed latency of 64 samples** at every sample rate, the cost of two oversampled runs, as in faust-pedalkit’s BassPreamp [2]. That is within faust-pedalkit’s 128-sample budget [2].
* The assembler rejects any chain with more than two oversampled runs. Waveshapers with no filter between them share one oversampler, as in faust-pedalkit [2].
* Every chain is padded with a delay to exactly 64 samples, and every dry or parallel path is aligned to the same total, so the reported latency is always true and never changes.
* Swaps crossfade: the new chain is built and primed off the audio thread, then both chains run for the crossfade time and an equal-power fade moves from old to new. Crossfade time **50 ms** (**chosen**: long enough to avoid a click on sustained notes, short enough to feel immediate; needs listening). Macro changes are smoothed inside each block (`si.smoo`), as in faust-pedalkit.
* CPU during a crossfade is up to twice one chain’s. The CPU target below allows for that.

Alternative rejected: report each chain’s own latency and restart the plugin on a swap. Restarts cause dropouts in some hosts and break the “type and hear it” loop.

## 9. Safety

* **Every assembled chain ends in a limiter**: `pk.safety(0.989)`, the same transparent-below-90 % soft limiter faust-pedalkit uses at the end of every effect [1], placed after the Output gain and the Mix. The assembler adds it; no answer can remove it.
* The assembler validates every chain spec before it reaches the audio thread: known block IDs, values within each parameter’s range, at most six blocks (**chosen**), at most two oversampled runs, latency equal to the fixed 64 samples. An invalid spec keeps the current chain and logs why.
* Model output never reaches the audio thread except as a validated, fixed-size chain spec.

Which faust-pedalkit tests apply to assembled chains [2]:

| Test | Applies? | How |
|---|---|---|
| Silence (silence in gives silence out) | Yes | For every chain the assembler can build from the evaluation set, plus random valid chains |
| Peak ≤ 0 dBFS at extreme settings | Yes | All macros at 0 and at 1, hot input; the limiter guarantees it, the test proves it |
| Recovery (below −120 dBFS in the fourth second after a hot input) | Yes | Per chain, and across a swap |
| CPU (≥ 20× real time in 64-sample blocks; tail ≤ 3× live signal) | Yes, adapted | Measured for the most expensive valid chain, and for two chains running during a crossfade |
| Zipper (≤ 6 dB above steady state above 8 kHz on a full-range jump) | Yes, extended | For each macro, and for a chain swap (the crossfade must meet the same limit) |
| Latency (reported matches measured, ≤ 128 samples) | Yes | Must equal 64 for every chain |
| Frequency response and harmonics | Per block, in faust-pedalkit | Assembled chains are combinations; targets come from the blocks’ own tests |

## 10. Measurable targets

| Target | Value | Confidence |
|---|---|---|
| Decision accuracy on the evaluation set (questions with an expected answer) | ≥ 85 % for the chosen backend | **chosen** |
| Calibration | ECE ≤ 0.10 on the evaluation set | **chosen**; s1 reports 0.083 on its own benchmark [6] |
| Low-confidence rate | ≤ 25 % of answers below threshold | **chosen** |
| Errors and refusals | 0 on the evaluation set, local backend | **chosen** |
| Decision latency, local backend, all nine questions | median ≤ 1 s, 95th percentile ≤ 2 s, on the player’s machine | **chosen**; vendors report 27 ms to 0.8 s on varying hardware [6, 7, 8] |
| Time from pressing Enter to hearing the new chain | ≤ 1.5 s median | **chosen** |
| Plugin latency | fixed 64 samples | **chosen**, §8 |
| CPU, two chains crossfading | ≥ 20× real time per instance, 64-sample blocks | **chosen**, from faust-pedalkit [2] |
| Audio-thread waits on model or network | none (checked by design review and a test that stalls the backend) | **chosen** |

## 11. Open questions

Only listening can answer:

1. Is the 50 ms equal-power crossfade inaudible on sustained notes and through high-gain chains, or does it need to be longer, or synchronised to a zero-crossing?
2. Do the defaults (no drive, flat EQ, middle levels) sound like a sensible “didn’t understand” result, or should the fallback be the dry signal?
3. Do the five levels of `drive_amount` and `brightness` map to settings players would agree with? The mapping from level to dB and Hz is still to be chosen, and needs ears.
4. Does the 64-sample fixed latency feel acceptable when monitoring live at small buffer sizes?
5. Are the macros the player most wants for each chain the ones the assembler picks?

Need measurement or a decision:

1. Which backend to ship as the default local model, given the licence results in `docs/model-survey.md` and measured latency on typical player hardware (no GPU).
2. Should low-confidence questions be asked one at a time, or as a single short form?
3. Is a small typed-decision model needed at all, or would a well-built keyword table reach the accuracy target? The mock backend’s score cannot answer this: its cues and the evaluation items were written by the same person, so it scores well on the items it was written beside (88 % on the first run). A fair comparison needs items written by someone who has not seen the cues.
4. Will faust-pedalkit accept a block manifest, and in which form (generated from `blocks.js`, or from annotations in `pedalkit.lib`)?
5. How to treat the hosted API’s terms of service (logging, retention, training on inputs) before enabling it for players.
6. The evaluation set is written by one person. How many items, from how many people, are needed before accuracy differences between backends mean anything? With 40 items, a difference of a few answers is within noise.
7. faust-pedalkit reports latency with the `lv2:reportsLatency` port property, which the LV2 core specification now marks deprecated in favour of `lv2:designation lv2:latency` [14]. Worth raising there, separately, before Pedal Forge copies the pattern.

## Sources

1. faust-pedalkit repository, commit `8da82d3`: `AGENTS.md`, `src/lib/pedalkit.lib`, `docs/ecosystem.md`. <https://github.com/Joe-Heffer/faust-pedalkit>
2. faust-pedalkit, `docs/development/feel-cpu-stability.md` (latency budget, CPU, zipper, recovery limits). <https://github.com/Joe-Heffer/faust-pedalkit/blob/main/docs/development/feel-cpu-stability.md>
3. faust-pedalkit, `web/designer/blocks.js` (designer block palette). <https://github.com/Joe-Heffer/faust-pedalkit/blob/main/web/designer/blocks.js>
4. TypeSafe, Jev documentation (not reachable from the build environment on 26 October 2026; content reported via [18]). <https://docs.typesafe.ai/introduction>
5. Cloudflare, TypeSafe Jev model page (not reachable from the build environment on 26 October 2026). <https://developers.cloudflare.com/ai/models/typesafe/jev/>
6. s1 decision model, commit `0ec2561` (README, `MODEL_CARD.md`, `DATA_CARD.md`, `api/server.py`). <https://github.com/j-raghavan/s1-decision-model>
7. system-one, commit `ed076ed` (README). <https://github.com/mpuig/system-one>
8. OpenJev, commit `b4339c6` (README, `openjev/decisions.py`). <https://github.com/razorback16/openjev>
9. LiquidAI, d1-omni-600M model card (not reachable from the build environment; details reported by aggregators). <https://huggingface.co/LiquidAI/d1-omni-600m>
10. Awesome Open System One (index of related projects). <https://github.com/PerryLink/awesome-open-system-one>
11. CLAP, `include/clap/ext/params.h`, commit `a47f6ba`. <https://github.com/free-audio/clap/blob/main/include/clap/ext/params.h>
12. CLAP, `include/clap/ext/latency.h`, commit `a47f6ba`. <https://github.com/free-audio/clap/blob/main/include/clap/ext/latency.h>
13. Steinberg VST3 SDK interfaces, `vst/ivsteditcontroller.h` (`RestartFlags`), commit `4f547e8`. <https://github.com/steinbergmedia/vst3_pluginterfaces/blob/master/vst/ivsteditcontroller.h>
14. LV2 specification, `lv2/core.lv2/lv2core.ttl` and `lv2/dynmanifest.lv2/dynmanifest.meta.ttl`, commit `3c57dae`. <https://github.com/lv2/lv2>
15. JUCE forum, “VST3 parameter name changes don’t work” (host and wrapper behaviour, reported). <https://forum.juce.com/t/vst3-parameter-name-changes-dont-work/28313>
16. Guo, Pleiss, Sun and Weinberger, “On Calibration of Modern Neural Networks”, ICML 2017. <https://arxiv.org/abs/1706.04599>
17. REUSE specification 3.3. <https://reuse.software/spec-3.3/>
18. Third-party descriptions of the hosted API (endpoint `POST https://api.typesafe.ai/v1/systemone`, Bearer token, `choice`/`score`/`noul`, up to 255 options and 2 to 10 score levels, 70 to 500 ms), seen only as web-search summaries on 26 October 2026 because the pages themselves were not reachable from the build environment. Pages returned included <https://nexos.ai/blog/what-is-jev/>, <https://www.wps.com/blog/what-is-jev-typesafe-s-system-one-model-and-its-best-use-cases/> and <https://docs.rs/typesafe-jev>. Everything taken from them is **reported** and must be checked against TypeSafe’s own API reference before use.
