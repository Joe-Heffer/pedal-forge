# Pedal Forge

A planned DAW plugin for guitar and bass that builds an effect chain from a description in words. You type “warm, slightly broken-up bass with the lows kept tight”, and the plugin picks blocks from the [faust-pedalkit](https://github.com/Joe-Heffer/faust-pedalkit) library (waveshapers, filters, gain, blend), sets them, and maps the settings that matter to a fixed bank of macro controls you can automate.

The choice is made by a small typed-decision model (a “System One” model). It reads the description and answers typed questions (pick one of these blocks, place this on a scale, yes or no), each with a confidence value. It does not write code and does not process audio. A deterministic assembler turns its answers into the chain, falls back to safe defaults when the model is unsure, and always ends the chain in a limiter.

## Status

Early design. There is no plugin yet. This repository holds:

* [`docs/design-notes.md`](docs/design-notes.md): the idea, the architecture, the question schema, latency and safety handling, measurable targets and open questions.
* [`docs/model-survey.md`](docs/model-survey.md): candidate decision models, their licences, sizes, APIs and what was verified.
* [`eval/`](eval/): a harness that runs one set of typed questions against several model backends and reports accuracy, calibration, low-confidence rate and latency.

The plugin itself will target LV2, VST3 and CLAP on Linux, like faust-pedalkit.

## Quick start

```sh
make venv     # .venv with matplotlib and pre-commit (the harness core is standard library only)
make test     # the harness's tests and the tests for the pre-commit checks
make eval     # run the evaluation set; with nothing configured, only the mock backend runs
make check    # every pre-commit hook, as CI runs them
```

`make eval` writes `out/results.csv` (one row per backend, item and question), `out/summary.csv` (one row per backend and metric) and SVG plots. The mock backend is a keyword heuristic that exists to exercise the harness; its scores say nothing about any model.

### Adding a real backend

Backends are listed in [`eval/backends.toml`](eval/backends.toml). Each one is skipped unless the environment variable holding its base URL is set. API keys are read from the environment only. For example, with a local [OpenJev](https://github.com/razorback16/openjev) server on port 8080:

```sh
export PF_OPENJEV_URL=http://127.0.0.1:8080
make eval EVAL_ARGS="--backend openjev"
```

The hosted API needs `PF_JEV_URL` and `TYPESAFE_API_KEY`. See [`docs/model-survey.md`](docs/model-survey.md) for what each backend needs, and ask before downloading any model weights: the open candidates range from about 1 GB to 18 GB.

## Layout

| Path | Contents |
|---|---|
| `docs/` | Design notes and model survey (CC-BY-4.0) |
| `eval/` | Evaluation harness, backends, metrics, plots and tests |
| `eval/data/items.json` | The hand-written evaluation set (chosen values, with reasoning) |
| `tools/` | Pre-commit checks (trademarks, workflow permissions) and their tests |
| `.github/` | CI, CodeQL, Dependabot, dependency review, and the pull request and issue templates |
| `out/` | Generated results (not committed) |

## Licence

Code is MIT ([`LICENSE`](LICENSE)); documentation under `docs/` is CC-BY-4.0. Licensing is machine-readable ([REUSE](https://reuse.software/)): see `REUSE.toml` and `LICENSES/`.

Contributors and coding agents: read [`AGENTS.md`](AGENTS.md) first.
