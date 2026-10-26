# AGENTS.md: working on this repository

This file is for coding agents (and humans) changing anything here. Read it before touching anything. `README.md` covers what the project is and how to run it. The rules are adapted from the sibling repository [faust-pedalkit](https://github.com/Joe-Heffer/faust-pedalkit)’s `AGENTS.md`, and where the two overlap they mean the same thing.

## What this repo is

Pedal Forge is a planned DAW plugin (LV2, VST3 and CLAP) in which a player describes a sound in words and the plugin assembles an effect chain from the prebuilt blocks in faust-pedalkit’s `src/lib/pedalkit.lib`. A typed-decision (“System One”) model answers typed questions about the description, each with a confidence value. A deterministic assembler turns the answers into a chain of blocks and settings. The model never writes code and never touches audio.

At present the repo holds the design notes (`docs/design-notes.md`), a survey of candidate models (`docs/model-survey.md`) and an evaluation harness (`eval/`) that compares those models on a hand-written set of questions. There is no plugin DSP yet.

## Hard rules

1. **Clean-room only.** Anything taken from existing hardware or software comes from public schematics, circuit analyses, measurements, reviews, manuals and published API documentation. Never decompile, disassemble or copy a proprietary plugin, binary, firmware or SDK, and don’t use one as a reference to match against. A closed model may be called through its public API; its outputs are measured, never used to train anything shipped here unless its terms allow it.
2. **No trademarks.** Effect names, UI text, prompts, evaluation items, URIs and file names must be neutral. In `docs/`, a manufacturer’s product name may appear only to identify hardware or a model, never as branding. The `no-trademarks` pre-commit hook checks file names and the contents of `eval/`, `prompts/` and `src/` against `tools/trademarks.txt`. When you write a description that a player might type, describe the sound, not the product.
3. **British English** in all documentation, comments, evaluation items and UI text: colour, behaviour, modelling, analyse, centre. The `codespell (British English)` hook checks Markdown and JSON.
4. **Say when you’re unsure, and say why a value is what it is.** Every constant, threshold, default and prompt is **documented** (from a specification or official documentation), **reported** (from a README, paper or third party, not verified here), **inferred** (derived from other sources) or **chosen** (a design decision). The notes or a comment next to the value must say which, with a link for anything sourced and the intent behind anything chosen. Treat every performance figure in a model’s README as reported until it has been measured with `make eval`. Never guess silently.
5. **Ask the user before anything destructive or system-wide.** That includes `sudo`, package installs outside `.venv/`, deleting outside `build/` and `out/`, large model downloads, and changes to the sibling repository, which this repo never modifies.
6. **You can’t listen.** Judge by measurement and structured data (accuracy, calibration, latency, levels, frequency response) and list what a human should check by ear.
7. **Open formats and machine-readable licensing.** Every file has an SPDX header (`SPDX-FileCopyrightText` and `SPDX-License-Identifier`), or an entry in `REUSE.toml` if it can’t take comments. Code is `MIT` and `docs/` is `CC-BY-4.0`. The `reuse` hook enforces this. Results are CSV in long format and plots are SVG.
8. **Licences are checked before use.** Every model, training set and dependency gets a row in `docs/model-survey.md` saying whether it can be used with, or shipped in, an MIT plugin. Nothing with an unclear or incompatible licence is bundled.

## Rules specific to the decision model

* **The audio thread never waits** on the network, the model, a lock held by either, or memory allocation. Inference runs on a background thread. A new chain is built off the audio thread and swapped in with a crossfade (`docs/design-notes.md`, “Latency handling”).
* **Offline first.** The default backend is a local model behind a Jev-compatible HTTP API on `localhost`. A hosted API is optional and off by default.
* **API keys come from the environment**, never from files in the repo, config files or logs. A backend’s config names the environment variable to read (`eval/backends.toml`).
* **Fixed parameters.** The plugin exposes a fixed bank of generic macro slots, because hosts store parameters by index or ID. Never add, remove or reorder parameters at run time.
* **Every assembled chain ends in a limiter** (`pk.safety(0.989)`, as in faust-pedalkit).
* **Low confidence falls back.** Every question has a documented default and a confidence threshold. Below the threshold the assembler uses the default or asks the player; it never acts on a low-confidence answer silently.

## Changing the design

Notes come before code. Update `docs/design-notes.md` first, then the harness or (later) the plugin. A new constant goes in the notes with its confidence level before it goes in the code.

## The evaluation harness (`eval/`)

* `make eval` runs `eval/data/items.json` against every backend in `eval/backends.toml` whose environment variables are set, plus the mock backend, and writes `out/results.csv`, `out/summary.csv` and SVG plots. Backends that are not configured are skipped with a message.
* The items are **chosen**: they are the maintainer’s judgement of the right answer, not ground truth. Each one carries its reasoning. A change to an expected answer needs a reason in its `reasoning` field.
* Questions come from the fixed bank in `eval/questions.py`, so every backend sees the same wording. Adding a question means adding it there with its default and threshold, then documenting it in the design notes.
* `make test` runs the harness’s tests and the tests for `tools/` (standard library `unittest`). Tests that need matplotlib skip without it.
* Generated files go only in `build/` and `out/`. Never commit them.

## Build mechanics

* `make help` lists the targets: `venv`, `check`, `test`, `eval`, `format`, `clean`.
* `make venv` creates `.venv/` and installs `requirements.txt` (matplotlib and pre-commit). The harness core uses only the Python standard library. Ask before adding any other dependency.
* `make check` runs `pre-commit run --all-files`, as CI does (`.github/workflows/ci.yml`). CI also runs `make test` and a mock-only `make eval` on Python 3.11 and 3.13, and uploads `out/`. CodeQL scans the Python and the workflows, Dependabot proposes updates to the pins, and pull requests get a dependency review (`.github/`).
* `make clean` removes `build/` and `out/` only.

## Reporting back

Finish any piece of work with a short summary covering:

* what works, backed by test results
* what is approximate, with references to the “chosen” values
* what the user should check by listening or on their own hardware, naming the value to adjust
