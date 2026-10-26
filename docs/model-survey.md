# Decision-model survey

Checked on 26 October 2026. Each project’s repository was cloned at the commit named below and its README, licence file and (where noted) source were read. Model weights were **not** downloaded, and no model was run, so every accuracy and latency figure here is **reported** by its authors, not measured. `make eval` is how they get measured. Three vendor sites (TypeSafe’s docs, Cloudflare’s model page and Hugging Face) did not resolve from the build environment, so what is known about the hosted API and about d1-omni-600M comes from third parties and is marked as such.

Legend for the “Checked” column: **verified** (read in the licence file, source code or a specification), **README** (stated by the project, not verified), **third party** (from an aggregator or article), **unknown**.

## Summary

| Candidate | Licence (code / weights) | Size | Runs locally on | API | Fits an MIT plugin? |
|---|---|---|---|---|---|
| Hosted TypeSafe Jev | Closed; terms of service not read | Not published | No (API only) | `POST /v1/systemone` (third party) | As an optional, user-enabled backend only; nothing is shipped |
| s1 (`jrlabs01/s1`) | Apache-2.0 / Apache-2.0 | 26B total, 4B active (MoE); int4 about 17 GB | 32 GB Apple-silicon laptop (Ollama), or a 48 GB+ GPU (vLLM) | `POST /v1/decisions` with the Jev body | Yes, as a separately installed server; too large to bundle |
| LiquidAI d1-omni-600M | LFM Open License v1.0 (third party) | About 587M parameters (third party) | Unknown; small enough for a CPU | No server API found | Not without reading the licence: it restricts commercial use above a revenue threshold (third party) |
| system-one | MIT / base-model licences | 0.6B (about 1.2 GB) or 2B 8-bit (about 2.5 GB) | Apple Silicon only (MLX) | `POST /v1/systemone` | Code yes; adapters need care (may be distilled from the hosted API) |
| OpenJev | Apache-2.0 / Apache-2.0 (DiffusionGemma) | 26B-A4B, about 18 GB download | NVIDIA GPU with 24 GB+, or Apple silicon (MLX) | `POST /v1/systemone`, `/v1/decisions`, `/v1/models` | Yes, as a separately installed server |

No candidate is small enough, permissively licensed and cross-platform enough to bundle inside the plugin today. The design therefore talks to a local server the player installs separately, over the Jev-shaped HTTP API, and keeps the keyword fallback for players with no model.

## Candidates

### Hosted TypeSafe Jev

| | |
|---|---|
| Links | <https://docs.typesafe.ai/introduction>, <https://developers.cloudflare.com/ai/models/typesafe/jev/> (neither reachable from the build environment) |
| Licence | Closed model, API only. Terms of service not read: **unknown** |
| Size | Not published |
| Local use | None |
| API shape | `POST https://api.typesafe.ai/v1/systemone`, `Authorization: Bearer <key>`, body `{model, state, questions}`, answers keyed by question name; types `choice`, `score`, `noul`; `GET /v1/models` (**third party**). The same shape is served by OpenJev, whose README says it was “checked against the live API” (**README**) |
| Models | `jev-1.13.0`, aliases `jev-latest`, `jev-preview` (**third party**, as of 30 September 2026) |
| Claims | 70 to 500 ms per request; about $0.042 per million input tokens, output free (**third party**, launch figures) |
| Harness | Backend `jev`; needs `PF_JEV_URL` (e.g. `https://api.typesafe.ai`) and `TYPESAFE_API_KEY` |
| To check | The official API reference and OpenAPI spec; terms on logging, retention and training on inputs; whether outputs may be used to tune another model |

### s1 decision model

| | |
|---|---|
| Link | <https://github.com/j-raghavan/s1-decision-model>, commit `0ec2561` (17 October 2026) |
| Licence | Code, weights and docs Apache-2.0 (`LICENSE`, `MODEL_CARD.md` front matter: **verified**). Training data “mixed-permissive”: each row keeps its source licence, including 16,670 CC-BY-SA rows that stay share-alike if redistributed (`DATA_CARD.md`: **verified**). The data is not redistributed by this project, so share-alike does not reach the plugin. The teacher for soft labels is the open Gemma 4 model, not a closed API (`DATA_CARD.md`: **verified**) |
| Base model | `google/gemma-4-26B-A4B-it` (**verified** in `MODEL_CARD.md`). The base model’s own licence was not read here: check before relying on it |
| Size | 26B parameters, 4B active; int4 Ollama build about 17 GB (**README**) |
| Local use | `ollama pull jrlabs01/s1`, then `uvicorn api.server:app` (**README**); vLLM: bf16 needs 80 GB+, FP8 48 GB (**README**) |
| API shape | `POST /v1/decisions`, body `{state, questions}` with Jev-style questions (`state` may be a JSON object); answers `{type, choice, confidence, probabilities}` for choice, `{type, score, confidence, legend, probabilities}` with probabilities keyed `"0"`, `"1"`, … for score, `{type, noul, noul_raw}` for yes/no; `usage.latency_ms` (`api/server.py`: **verified**). Questions are scored one after another, so latency grows with the number of questions (**verified** in source). Choice `confidence` is the top probability (**verified**) |
| Claims | JevBench 0.808 raw / 0.817 calibrated, ECE 0.083; 27 ms median on an RTX PRO 6000 (FP8, vLLM); about 0.8 s per decision on a 32 GB Apple-silicon laptop (**README**) |
| Harness | Backend `s1`; `PF_S1_URL` (e.g. `http://127.0.0.1:8000`), no key |

### LiquidAI d1-omni-600M

| | |
|---|---|
| Link | <https://huggingface.co/LiquidAI/d1-omni-600m> (not reachable from the build environment; not seen) |
| Licence | LFM Open License v1.0; commercial use by companies with annual revenue of $10 million or more needs separate authorisation (**third party**: search-result summaries of aggregator pages) |
| Size | About 587M parameters: a 381M trunk and decision head, a 94M vision encoder and a 112M audio encoder, built on LFM2.5-Encoder-350M (**third party**) |
| Local use | Unknown. Its size suggests CPU inference is feasible (**inferred**) |
| API shape | Typed answers in one forward pass with no output tokens; 16,384-token context; text or JSON plus an image or audio (**third party**). No HTTP server or Jev-compatible wrapper found |
| Claims | 15.95 on a third-party “Decision Index” text benchmark (**third party**); no speed figures published |
| Harness | Not wired up. It would need a small server exposing the Jev shape; ask before downloading |
| To check | The model card and the licence text itself, especially whether a free plugin distributed by an individual counts as commercial use, and whether attribution or naming terms apply |

### system-one

| | |
|---|---|
| Link | <https://github.com/mpuig/system-one>, commit `ed076ed` (23 September 2026) |
| Licence | Code MIT (`LICENSE`: **verified**). Base models keep their own licences (**README**): Qwen3-0.6B and MiniCPM5-2B, neither read here. The README warns to check “TypeSafe’s terms before distributing data or distilled weights” and describes distillation runs that call the hosted API (**README**), so some adapters may be trained on hosted-API outputs |
| Size | `system-one-qwen3-0.6b` (base about 1.2 GB, adapter in the repo); `system-one-minicpm5-2b-q8` (about 2.5 GB) (**README**) |
| Local use | Apple Silicon and `uv` only: `uv sync`, then `scripts/serve.py --model Qwen/Qwen3-0.6B --adapter … --port 8399` (**README**). Described by its author as “a research prototype, not a production-ready decision service” |
| API shape | `POST /v1/systemone`, `{state, questions}` → `{model, answers, usage}`; calibration endpoint `POST /v1/calibrations` (**README**) |
| Claims | 0.6B: 77.6 % accuracy, ECE 0.049 in-family; confident errors rise to 14 to 19 % out of family, 3 to 4 % after per-workload temperature fitting (**README**) |
| Harness | Backend `system_one`; `PF_SYSTEM_ONE_URL` (e.g. `http://127.0.0.1:8399`), no key |
| To check | Which shipped adapters, if any, were trained on hosted-API outputs, and what TypeSafe’s terms say about that |

### OpenJev

| | |
|---|---|
| Link | <https://github.com/razorback16/openjev>, commit `b4339c6` (12 October 2026), version 0.7.0 |
| Licence | Apache-2.0 (`LICENSE`: **verified**). DiffusionGemma weights Apache-2.0; bundled small models Laya and Verdict Apache-2.0 (**README**) |
| Size | DiffusionGemma 26B-A4B, about 18 GB of weights; Docker images about 8.7 GB of shared layers (**README**) |
| Local use | `docker compose up -d` on an NVIDIA GPU with 24 GB+, or `pip install -e '.[mlx]'` and `OPENJEV_BACKEND=mlx python -m openjev` on Apple silicon (**README**) |
| API shape | `POST /v1/systemone` `{model, state, questions}` → `{model, answers, usage}`; `noul` → `{noul}`; `choice` → `{choice, probabilities, confidence}`; `score` → `{score, legend, probabilities, confidence}`, probabilities keyed by level index; `confidence = 1 − H(p)/ln K`; `Server-Timing` header; also OpenAI-style `POST /v1/decisions` and `GET /v1/models` (README, and `openjev/decisions.py`: **verified**) |
| Claims | p50 about 30 ms for a 49-token state on an RTX PRO 6000; 0.2 to 0.4 s for three questions on an M3 Ultra (**README**) |
| Harness | Backend `openjev`; `PF_OPENJEV_URL` (e.g. `http://127.0.0.1:8080`), optional `PF_OPENJEV_KEY` |

### Others in the index

[awesome-open-system-one](https://github.com/PerryLink/awesome-open-system-one) lists further open reproductions. Two look relevant to a plugin that should run on a player’s CPU, and are worth evaluating next (not checked beyond the index entry):

* **jevos** (<https://github.com/feder-cr/jev>): a 1B yes/no model as GGUF, CPU-only via llama.cpp; MIT according to the index. Yes/no only, so it would cover three of the nine questions.
* **Laya** (<https://github.com/NandhaKishorM/laya>): a 421M non-autoregressive decision engine; Apache-2.0 according to OpenJev’s README, which can serve it behind the same API.

## Licence check against shipping an MIT plugin

The plugin’s own code is MIT. It will **not** bundle model weights; it talks to a server the player installs. That keeps weight and data licences out of the plugin’s distribution, but the project still should not recommend a default backend whose terms a player would break by using it.

| Component | Licence | Use here | Compatible? | Checked |
|---|---|---|---|---|
| faust-pedalkit (`pedalkit.lib`, block DSP) | MIT (code), CC-BY-4.0 (docs) | Compiled into the plugin | Yes | verified (`REUSE.toml`, `LICENSES/`) |
| Faust standard libraries (in generated C++) | Per-library licences, not checked here | Generated C++ | To check, per library used, alongside faust-pedalkit’s own record | unknown |
| CLAP headers | MIT | Build dependency | Yes | verified (`LICENSE` in the CLAP repository) |
| VST3 SDK interfaces | MIT | Build dependency | Yes | verified (`LICENSE.txt` in `vst3_pluginterfaces`) |
| LV2 headers | ISC | Build dependency | Yes | verified (`COPYING` in the LV2 repository) |
| Python standard library | PSF | Harness | Yes (not shipped) | verified |
| matplotlib | PSF-style matplotlib licence | Harness plots (dev only) | Yes (not shipped) | README |
| numpy (installed with matplotlib) | BSD-3-Clause | Dev only | Yes (not shipped) | README |
| pre-commit | MIT | Dev only | Yes (not shipped) | README |
| s1 weights | Apache-2.0 | Player-installed server | Yes | verified |
| s1 training data | Mixed permissive, some CC-BY-SA | Not used or redistributed | Not affected | verified |
| OpenJev and DiffusionGemma | Apache-2.0 | Player-installed server | Yes | verified (code) / README (weights) |
| system-one code | MIT | Player-installed server | Yes | verified |
| system-one adapters | Base-model licences plus possible hosted-API terms | Player-installed server | **Unclear**; not recommended as default until checked | README |
| d1-omni-600M | LFM Open License v1.0 | Not used yet | **Unclear**; needs the licence text | third party |
| Hosted Jev | Closed; terms not read | Optional, player-enabled | Calling it is the player’s choice; nothing is shipped. Terms must be read before it is offered in the UI | unknown |

## What was verified and how

* Repository contents and licence files: shallow clones at the commits above, read on 26 October 2026.
* API shapes for s1 and OpenJev: read from the server source (`api/server.py`, `openjev/decisions.py`), not only the README.
* The harness’s HTTP client is tested against a local stub that serves both answer shapes (`eval/tests/test_http.py`), not against any live server.
* Nothing was benchmarked. Every speed and accuracy figure above is the authors’ own, or a third party’s.
