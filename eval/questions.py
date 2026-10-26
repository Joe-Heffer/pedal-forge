# SPDX-FileCopyrightText: 2026 Joe Heffer
# SPDX-License-Identifier: MIT
"""The fixed question bank and the state every backend is sent.

Every backend sees exactly these questions, worded the same way, so their
answers can be compared. The keys, options, defaults and thresholds are
chosen values documented in docs/design-notes.md, section 5. Option names
follow faust-pedalkit's web/designer/blocks.js, the only machine-readable
block list that exists today.

Wording is part of the prompt: change it only with a note in the design notes,
and expect results from before and after the change not to be comparable.
"""

import json
from dataclasses import dataclass, field

# Text of the `task` field in the state. Chosen: one plain sentence naming the
# job, so the model reads the description as a request for effect blocks.
TASK = "Choose guitar or bass effect blocks for a player's description."


@dataclass(frozen=True)
class Question:
    key: str
    type: str  # "choice", "score" or "noul" (yes/no)
    instructions: str
    # choice: {option: description}; score: [level 0, level 1, ...];
    # noul: {"true": ..., "false": ...} or None.
    criteria: object
    default: object  # option, level index or bool used when confidence is low
    threshold: float  # minimum confidence (top probability) to act on
    notes: str = ""

    def options(self):
        """The answers this question allows, in order."""
        if self.type == "choice":
            return list(self.criteria)
        if self.type == "score":
            return list(range(len(self.criteria)))
        return [True, False]

    def wire(self):
        """The question as the Jev-shaped API expects it."""
        q = {"type": self.type, "instructions": self.instructions}
        if self.criteria is not None:
            q["criteria"] = self.criteria
        return q


@dataclass(frozen=True)
class Bank:
    questions: tuple = field(default_factory=tuple)

    def __iter__(self):
        return iter(self.questions)

    def __getitem__(self, key):
        for q in self.questions:
            if q.key == key:
                return q
        raise KeyError(key)

    def keys(self):
        return [q.key for q in self.questions]

    def wire(self):
        return {q.key: q.wire() for q in self.questions}


BANK = Bank(
    (
        Question(
            "instrument",
            "choice",
            "Which instrument is the player describing a sound for?",
            {
                "guitar": "Electric guitar, or no instrument named and nothing that points to bass",
                "bass": "Bass guitar, or a sound described in terms of low notes, sub "
                "or a bass part",
            },
            default="guitar",
            threshold=0.70,
            notes="Sets the DC blocker corner, the high-pass default and ranges.",
        ),
        Question(
            "in_vocabulary",
            "noul",
            "Everything the description asks for can be built from gain, distortion, "
            "filter and EQ, and clean-blend blocks, with no delay, echo, reverb, "
            "modulation, pitch shifting or looping.",
            {
                "true": "Yes, only gain, distortion, filtering, EQ and blending are needed.",
                "false": "No, it needs a time-based, modulation or pitch effect.",
            },
            default=True,
            threshold=0.70,
            notes="False means the plugin cannot build the request and says what is missing.",
        ),
        Question(
            "needs_drive",
            "noul",
            "The description asks for distortion, overdrive, fuzz, grit, crunch or saturation.",
            None,
            default=False,
            threshold=0.65,
            notes="Whether a waveshaper is used at all.",
        ),
        Question(
            "shaper",
            "choice",
            "If the sound is distorted, which kind of clipping suits it best?",
            {
                "soft": "Smooth, symmetric, rounded saturation, like a warm amplifier",
                "asym": "Asymmetric saturation with even harmonics, thick and tube-like",
                "knee": "Firm clipping with an adjustable knee, from tight to hard and buzzy",
                "softhard": "Soft on one side and hard on the other, gritty and uneven",
            },
            default="soft",
            threshold=0.50,
            notes="Waveshaper variant in blocks.js.",
        ),
        Question(
            "drive_amount",
            "score",
            "How much distortion does the description ask for?",
            [
                "Clean, no audible distortion",
                "Edge of break-up, only when played hard",
                "Moderate crunch",
                "Heavy distortion",
                "Saturated, fuzz-like, near-square",
            ],
            default=1,
            threshold=0.45,
            notes="Maps to the waveshaper's Drive (dB); mapping still to be chosen by ear.",
        ),
        Question(
            "tone_filter",
            "choice",
            "Which single filter best matches the tonal change asked for?",
            {
                "none": "No filtering needed",
                "lowpass": "Darker, smoother, less fizz or treble",
                "highpass": "Thinner or tighter, less low end or boom",
                "peak": "A boost or cut in one frequency region, such as the mids",
            },
            default="none",
            threshold=0.50,
            notes="Main filter variant in blocks.js (lp2, hp2 or peak).",
        ),
        Question(
            "brightness",
            "score",
            "How bright should the overall sound be?",
            ["Very dark", "Dark", "Neutral", "Bright", "Very bright"],
            default=2,
            threshold=0.45,
            notes="Maps to the filter's corner frequency; mapping still to be chosen by ear.",
        ),
        Question(
            "mid_shape",
            "choice",
            "What should happen to the midrange?",
            {
                "scooped": "Mids cut, for a hollow or scooped sound",
                "flat": "Mids left alone",
                "boosted": "Mids pushed forward, to cut through a mix",
            },
            default="flat",
            threshold=0.50,
            notes="Sign of the peaking EQ's gain.",
        ),
        Question(
            "keep_lows",
            "noul",
            "The player wants the low end kept clean, tight or intact underneath any distortion.",
            None,
            default=False,
            threshold=0.65,
            notes="Adds a clean low path blended back in with a mix block (bass only).",
        ),
    )
)


def state(description):
    """The state object sent with every request (design notes, section 5)."""
    return {"task": TASK, "description": description}


def state_text(description):
    """The same state, serialised for APIs that take a string."""
    return json.dumps(state(description), ensure_ascii=False)
