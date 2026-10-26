# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""Decision-model backends: the interface, a mock and a Jev-shaped HTTP client.

A backend takes a player's description and the question bank and returns one
Answer per question. Probabilities are normalised to the question's own
options, and confidence is computed here from them (the top probability, or
max(p, 1 - p) for yes/no), because backends define their own `confidence`
field differently (docs/design-notes.md, section 5). The backend's own value
is kept as `backend_confidence`.

API keys are read from the environment only, from the variable a backend's
config names. Nothing here reads keys from files.
"""

import json
import math
import os
import re
import socket
import time
import tomllib
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from eval.questions import state, state_text

DEFAULT_CONFIG = Path(__file__).with_name("backends.toml")

# Answer statuses. "ok" answers are scored; the others count as errors.
OK, ERROR, TIMEOUT, INVALID = "ok", "error", "timeout", "invalid"


@dataclass
class Answer:
    value: object = None  # option name, level index or bool
    probabilities: dict | None = None  # option -> probability, summing to 1
    backend_confidence: float | None = None
    status: str = OK
    error: str = ""

    @property
    def confidence(self):
        """Top-label confidence, or None if the backend gave no distribution."""
        if not self.probabilities:
            return None
        return max(self.probabilities.values())


@dataclass
class Response:
    answers: dict = field(default_factory=dict)  # question key -> Answer
    latency_ms: float = 0.0
    status: str = OK
    error: str = ""


class Backend:
    """Base class. Subclasses set `name` and implement `ask`."""

    name = "backend"
    description = ""

    def available(self):
        """(True, "") if the backend can be called, else (False, reason)."""
        return True, ""

    def ask(self, description, bank):
        raise NotImplementedError


def failed(bank, status, error, latency_ms=0.0):
    """A Response in which every question failed the same way."""
    answers = {q.key: Answer(status=status, error=error) for q in bank}
    return Response(answers, latency_ms, status, error)


# ---------------------------------------------------------------------------
# Answer normalisation (shared by every HTTP backend)


def _renormalise(probs):
    total = sum(probs.values())
    if not math.isfinite(total) or total <= 0:
        return None
    return {k: v / total for k, v in probs.items()}


def _prob(x):
    try:
        p = float(x)
    except (TypeError, ValueError):
        return None
    return p if math.isfinite(p) and 0.0 <= p <= 1.0 else None


def _choice_probs(raw, options):
    """Accept {option: p} or [{value, probability}]; keep known options only."""
    if isinstance(raw, list):
        raw = {d.get("value"): d.get("probability") for d in raw if isinstance(d, dict)}
    if not isinstance(raw, dict):
        return None
    probs = {}
    for opt in options:
        p = _prob(raw.get(opt, 0.0))
        if p is None:
            return None
        probs[opt] = p
    return _renormalise(probs)


def _score_probs(raw, levels):
    """Accept {"0": p, ...}, [p0, p1, ...] or [{value, probability}]."""
    if isinstance(raw, list) and raw and all(isinstance(d, dict) for d in raw):
        raw = {str(d.get("value")): d.get("probability") for d in raw}
    if isinstance(raw, list):
        raw = {str(i): p for i, p in enumerate(raw)}
    if not isinstance(raw, dict):
        return None
    probs = {}
    for i in range(levels):
        p = _prob(raw.get(str(i), raw.get(i, 0.0)))
        if p is None:
            return None
        probs[i] = p
    return _renormalise(probs)


def normalise(question, data):
    """Turn one raw answer object into an Answer, checking it against the question."""
    if not isinstance(data, dict):
        return Answer(status=INVALID, error="answer is not an object")
    conf = _prob(data.get("confidence"))
    if question.type == "noul":
        p = _prob(data.get("noul", data.get("probability")))
        if p is None:
            return Answer(status=INVALID, error="no yes/no probability")
        return Answer(p >= 0.5, {True: p, False: 1.0 - p}, conf)
    if question.type == "choice":
        options = question.options()
        probs = _choice_probs(data.get("probabilities"), options)
        value = data.get("choice")
        if value is None and probs:
            value = max(probs, key=probs.get)
        if value not in options:
            return Answer(status=INVALID, error=f"choice {value!r} is not an option")
        return Answer(value, probs, conf)
    if question.type == "score":
        levels = len(question.criteria)
        probs = _score_probs(data.get("probabilities"), levels)
        if probs:
            # The most likely level, not the rounded expected value: the
            # expected value can land on a level the model gives little mass.
            value = max(probs, key=probs.get)
        else:
            s = data.get("score")
            if not isinstance(s, int | float) or not 0 <= s <= levels - 1:
                return Answer(status=INVALID, error=f"score {s!r} out of range")
            value = round(s)
        return Answer(value, probs, conf)
    return Answer(status=INVALID, error=f"unknown question type {question.type!r}")


# ---------------------------------------------------------------------------
# Jev-shaped HTTP backend


class JevHTTPBackend(Backend):
    """Client for any server speaking the Jev request shape.

    POST <base_url><path> with {model, state, questions}; the answers come back
    keyed by question name. Hosted Jev, OpenJev and system-one use the path
    /v1/systemone, s1 uses /v1/decisions with the same body
    (docs/model-survey.md).
    """

    def __init__(
        self,
        name,
        base_url_env,
        path="/v1/systemone",
        model=None,
        api_key_env=None,
        key_required=False,
        state_format="text",
        timeout_s=10.0,
        description="",
        env=None,
    ):
        self.name = name
        self.description = description
        self.base_url_env = base_url_env
        self.path = path
        self.model = model
        self.api_key_env = api_key_env
        self.key_required = key_required
        self.state_format = state_format
        self.timeout_s = timeout_s
        self.env = os.environ if env is None else env

    @property
    def base_url(self):
        return (self.env.get(self.base_url_env) or "").rstrip("/")

    def _key(self):
        return self.env.get(self.api_key_env) if self.api_key_env else None

    def available(self):
        if not self.base_url:
            return False, f"{self.base_url_env} is not set"
        if self.key_required and not self._key():
            return False, f"{self.api_key_env} is not set"
        return True, ""

    def body(self, description, bank):
        s = state(description) if self.state_format == "object" else state_text(description)
        body = {"state": s, "questions": bank.wire()}
        if self.model:
            body["model"] = self.model
        return body

    def ask(self, description, bank):
        data = json.dumps(self.body(description, bank)).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        key = self._key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(self.base_url + self.path, data, headers, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = resp.read()
        except urllib.error.HTTPError as e:
            ms = (time.perf_counter() - t0) * 1000
            return failed(bank, ERROR, f"HTTP {e.code}", ms)
        except TimeoutError:
            return failed(bank, TIMEOUT, f"no answer in {self.timeout_s} s", self.timeout_s * 1000)
        except urllib.error.URLError as e:
            ms = (time.perf_counter() - t0) * 1000
            if isinstance(e.reason, TimeoutError | socket.timeout):
                return failed(bank, TIMEOUT, f"no answer in {self.timeout_s} s", ms)
            return failed(bank, ERROR, f"connection failed: {e.reason}", ms)
        ms = (time.perf_counter() - t0) * 1000
        try:
            answers = json.loads(payload)["answers"]
            if not isinstance(answers, dict):
                raise TypeError
        except (ValueError, KeyError, TypeError):
            return failed(bank, INVALID, "response has no answers object", ms)
        out = {}
        for q in bank:
            if q.key in answers:
                out[q.key] = normalise(q, answers[q.key])
            else:
                out[q.key] = Answer(status=INVALID, error="question not answered")
        return Response(out, ms)


# ---------------------------------------------------------------------------
# Mock backend

# Keyword cues per question and option. Chosen: a plain reading of common
# words players use, written to exercise the harness, not to compete with a
# model. Each matching cue adds MOCK_WEIGHT to its option's logit.
MOCK_CUES = {
    "instrument": {
        "bass": ["bass", "low string", "sub", "five-string", "4-string", "fingerstyle"],
        "guitar": ["guitar", "lead", "solo", "chord", "riff", "strum"],
    },
    "in_vocabulary": {
        False: [
            "delay",
            "echo",
            "reverb",
            "chorus",
            "flanger",
            "phaser",
            "tremolo",
            "vibrato",
            "octave",
            "pitch",
            "loop",
            "shimmer",
            "slapback",
            "wah",
            "rotary",
        ],
    },
    "needs_drive": {
        True: [
            "drive",
            "overdriv",
            "distort",
            "fuzz",
            "grit",
            "crunch",
            "satur",
            "dirt",
            "gain",
            "growl",
            "break-up",
            "breakup",
            "fizz",
            "hairy",
            "aggress",
            "heavy",
        ],
        False: ["clean", "pristine", "transparent", "no distortion"],
    },
    "shaper": {
        "soft": ["warm", "smooth", "round", "creamy", "amp", "gentle"],
        "asym": ["tube", "valve", "even harmonic", "thick", "fat"],
        "knee": ["tight", "hard", "buzz", "modern", "aggress", "metal"],
        "softhard": ["gritty", "uneven", "broken", "sputter", "lo-fi", "ragged"],
    },
    "tone_filter": {
        "lowpass": ["dark", "smooth", "mellow", "less fizz", "muffled", "woolly", "warm"],
        "highpass": ["thin", "tight", "less boom", "telephone", "tighten", "no mud"],
        "peak": ["mid", "honk", "nasal", "presence"],
        "none": ["natural", "as it is", "neutral"],
    },
    "mid_shape": {
        "scooped": ["scoop", "hollow", "mid cut", "less mid"],
        "boosted": ["mid boost", "midrange", "cut through", "honk", "push the mids", "mid hump"],
        "flat": ["flat", "natural"],
    },
    "keep_lows": {
        True: [
            "keep the low",
            "low end clean",
            "clean low",
            "tight low",
            "keep the bottom",
            "lows intact",
            "clean blend",
            "low end intact",
            "lows kept",
        ],
    },
}
# Cues for the two scores: each cue votes for a level.
MOCK_LEVEL_CUES = {
    "drive_amount": {
        0: ["clean", "pristine", "no distortion"],
        1: ["edge of break-up", "slight", "touch of", "a little", "subtle", "light"],
        2: ["crunch", "moderate", "medium", "overdriv"],
        3: ["heavy", "high gain", "distortion", "aggress", "metal"],
        4: ["fuzz", "saturated", "square", "wall of", "extreme", "maximum"],
    },
    "brightness": {
        0: ["very dark", "muffled", "woolly"],
        1: ["dark", "mellow", "smooth", "warm"],
        2: ["neutral", "natural", "balanced"],
        3: ["bright", "crisp", "presence", "sparkl"],
        4: ["very bright", "piercing", "fizzy", "glassy", "telephone"],
    },
}
MOCK_WEIGHT = 1.5  # chosen: one cue moves a two-option question to about 0.82
MOCK_PRIOR = 0.0  # chosen: options with no cue start level


def _softmax(logits):
    m = max(logits.values())
    exps = {k: math.exp(v - m) for k, v in logits.items()}
    total = sum(exps.values())
    return {k: v / total for k, v in exps.items()}


def _count(text, cues):
    return sum(1 for c in cues if re.search(r"(?<![a-z])" + re.escape(c), text))


class MockBackend(Backend):
    """Deterministic keyword heuristic. Runs anywhere, needs nothing.

    It exists so the harness, metrics and plots can be tested end to end. Its
    scores say nothing about any model.
    """

    name = "mock"
    description = "Keyword heuristic (no model); exercises the harness"

    def __init__(self, latency_ms=0.0):
        self.latency_ms = latency_ms

    def _answer(self, q, text):
        if q.key in MOCK_LEVEL_CUES:
            cues = MOCK_LEVEL_CUES[q.key]
            logits = {i: MOCK_PRIOR + MOCK_WEIGHT * _count(text, cues.get(i, [])) for i in cues}
            if not any(logits.values()):
                logits[q.default] += MOCK_WEIGHT / 3
        else:
            cues = MOCK_CUES.get(q.key, {})
            logits = {
                o: MOCK_PRIOR + MOCK_WEIGHT * _count(text, cues.get(o, [])) for o in q.options()
            }
            if q.type == "noul" and not any(logits.values()):
                logits[q.default] += MOCK_WEIGHT / 2
        probs = _softmax(logits)
        value = max(probs, key=lambda k: (probs[k], k == q.default))
        return Answer(value, probs, max(probs.values()))

    def ask(self, description, bank):
        t0 = time.perf_counter()
        text = description.lower()
        answers = {q.key: self._answer(q, text) for q in bank}
        ms = (time.perf_counter() - t0) * 1000 + self.latency_ms
        return Response(answers, ms)


# ---------------------------------------------------------------------------
# Configuration


def load(path=DEFAULT_CONFIG, env=None):
    """Build every backend listed in the config, in file order."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    backends = []
    for name, spec in cfg.get("backends", {}).items():
        kind = spec.get("kind")
        if kind == "mock":
            backends.append(MockBackend())
        elif kind == "http":
            backends.append(
                JevHTTPBackend(
                    name,
                    spec["base_url_env"],
                    path=spec.get("path", "/v1/systemone"),
                    model=spec.get("model"),
                    api_key_env=spec.get("api_key_env"),
                    key_required=spec.get("key_required", False),
                    state_format=spec.get("state_format", "text"),
                    timeout_s=float(spec.get("timeout_s", 10.0)),
                    description=spec.get("description", ""),
                    env=env,
                )
            )
        else:
            raise ValueError(f"backend {name!r}: unknown kind {kind!r}")
    return backends
