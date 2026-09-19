"""Pictures, made safe. Two jobs, both pure functions with no model:

1. concept_map(): the student's plan as a Mermaid flowchart and a mind map, coloured by what they
   know. It is built in code from the plan and the learner model, never written by a model, so its
   syntax cannot be wrong and its colours cannot be talked into anything.
2. safe_diagram(): the gate every model-written diagram passes before it reaches a browser. Only
   diagram kinds on an allow-list get through, and nothing that can carry script or change how
   Mermaid itself is configured.
"""
from __future__ import annotations

import re

from . import learner
from .schema import LearnerModel

# The kinds a lesson may draw. Each earns its place: classes for inheritance and relationships,
# sequences for who calls whom, states for lifecycles, flowcharts for decisions and steps.
ALLOWED_DIAGRAMS = ("flowchart", "graph", "classDiagram", "sequenceDiagram", "stateDiagram-v2",
                    "stateDiagram", "mindmap")
MAX_DIAGRAM_CHARS = 3000
LABEL_CHARS = 36                # long enough to read, short enough for a narrow side panel

_FENCE = re.compile(r"^\s*```(?:mermaid)?\s*|\s*```\s*$", re.I)
_DANGEROUS = re.compile(r"%%\{|<\s*/?\s*(?:script|iframe|object|embed|img|svg|style)|javascript:|"
                        r"<[^>]*\bon\w+\s*=|^\s*(?:click|callback)\s", re.I | re.M)


def safe_diagram(source: str | None) -> str | None:
    """The diagram if it is safe to show, else None. The page also parse-checks it, and drops one
    that does not parse; this decides what is allowed to be tried at all."""
    if not source or not source.strip():
        return None
    text = _FENCE.sub("", source.strip()).strip()
    if not text or len(text) > MAX_DIAGRAM_CHARS:
        return None
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("%%")]
    if not lines or lines[0].split()[0] not in ALLOWED_DIAGRAMS:
        return None
    return None if _DANGEROUS.search(text) else text


# ------------------------------------------------------------------ the concept map

def label(name: str) -> str:
    """A concept id made into text that is safe inside a Mermaid label: words only, no quotes,
    brackets or other syntax, and a length that fits."""
    words = re.sub(r"[^\w\s.,+&/-]", "", name.replace("-", " ").replace("_", " "))
    words = re.sub(r"\s+", " ", words).strip()
    return (words[:1].upper() + words[1:])[:LABEL_CHARS].strip() or "Topic"


def state(m: LearnerModel, concept: str) -> str:
    """known: at the bar. shaky: seen but not there yet. unknown: not started."""
    if concept not in m.mastery:
        return "unknown"
    return "known" if learner.effective_mastery(m, concept) >= learner.MASTERY else "shaky"


def _edges(prereqs: list[str], parts: list[str], target: str) -> list[tuple[str, str]]:
    """What leads to what: prerequisites in order, the last of them into every part, every part into
    the topic. With no parts the prerequisites lead straight to the topic."""
    chain = [*prereqs]
    out = list(zip(chain, chain[1:]))
    middle = parts or [target]
    if chain:
        out += [(chain[-1], p) for p in middle]
    if parts:
        out += [(p, target) for p in parts]
    return out


def concept_map(plan: dict, m: LearnerModel, current: str | None = None) -> dict:
    """{"flowchart": ..., "mindmap": ...} for a guided plan. `current` is the concept being taught or
    asked right now; it gets a heavy outline."""
    target, prereqs, parts = plan["target"], plan.get("prereqs", []), plan.get("subtopics", [])
    order = [*prereqs, *parts, target]
    ids = {c: f"n{i}" for i, c in enumerate(order)}          # n0..nk: never derived from text

    lines = ["flowchart TD"]
    for c in order:
        lines.append(f'  {ids[c]}["{label(c)}"]:::{state(m, c)}')
    lines += [f"  {ids[a]} --> {ids[b]}" for a, b in _edges(prereqs, parts, target)]
    lines += ["  classDef known fill:#d1fae5,stroke:#059669,color:#064e3b",
              "  classDef shaky fill:#fef3c7,stroke:#d97706,color:#78350f",
              "  classDef unknown fill:#f3f4f6,stroke:#9ca3af,color:#374151",
              "  classDef current stroke:#2563eb,stroke-width:4px"]
    if current in ids:
        lines.append(f"  class {ids[current]} current")

    def named(c: str) -> str:
        seen = c in m.mastery
        return f"{label(c)} {round(learner.effective_mastery(m, c) * 100)}%" if seen else label(c)

    mind = ["mindmap", f"  root(({named(target)}))"]
    if prereqs:
        mind += ["    Prerequisites", *[f"      {named(c)}" for c in prereqs]]
    if parts:
        mind += ["    Parts", *[f"      {named(c)}" for c in parts]]
    return {"flowchart": "\n".join(lines), "mindmap": "\n".join(mind)}
