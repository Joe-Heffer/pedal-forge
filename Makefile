# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
# Pedal Forge: design notes and the decision-model evaluation harness. There
# is no plugin DSP yet (see docs/design-notes.md).
#
#   make venv         create .venv and install requirements.txt into it
#   make check        run every pre-commit hook on every file (as CI does)
#   make test         run the evaluation harness's own tests
#   make eval         run the evaluation set against every configured backend, writing out/
#   make format       fix Python lint and formatting with ruff
#   make clean        remove build/ and out/ (never a custom OUT)
#   make help         list these targets
#
# Variables: PYTHON and PRE_COMMIT (default: the ones in .venv if it exists),
# OUT (default out), EVAL_ARGS (extra arguments for `python -m eval.run`, e.g.
# EVAL_ARGS="--backend mock --repeat 3").

PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)
PRE_COMMIT ?= $(if $(wildcard .venv/bin/pre-commit),.venv/bin/pre-commit,pre-commit)
OUT ?= out
EVAL_ARGS ?=

.PHONY: help venv check test eval format clean

help:
	@sed -n 's/^#   make /make /p' $(firstword $(MAKEFILE_LIST))

venv:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

check:
	$(PRE_COMMIT) run --all-files

test:
	$(PYTHON) -m unittest discover -s eval/tests -t . -v

eval:
	$(PYTHON) -m eval.run --out $(OUT) $(EVAL_ARGS)

# Uses the ruff pinned in .pre-commit-config.yaml, so the result matches CI.
# pre-commit exits non-zero whenever a hook changes a file, so only the last
# run decides the status.
format:
	@$(PRE_COMMIT) run ruff-check --all-files || true
	@$(PRE_COMMIT) run ruff-format --all-files || true
	$(PRE_COMMIT) run ruff-check --all-files

clean:
	rm -rf build out
