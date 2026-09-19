
## The check: multiple choice

- One question that tests understanding, not recall of a phrase.
- The student sees ONLY the question, the `code` field and the options. If the
  question is about code, the code goes in `code` (plain source, no fences) and
  the question must not depend on anything else. Never write "the following
  code" unless `code` is filled in.
- 3 or 4 options. Exactly one is correct, and `correct` is its index.
- Every wrong option represents ONE specific, plausible wrong belief, named in
  its `misconception` as a short kebab-case tag (e.g. `default-is-copied`). Wrong
  options that are merely silly teach us nothing.
- The correct option has `misconception` null.
- `why` explains the right answer in one or two sentences.

## Output

Reply with ONE JSON object and nothing else, in exactly this shape. These key
names are required; do not rename, add or nest anything else. Leave `open` null.

```
{
  "covered": true,
  "explanation": "the lesson text",
  "citations": ["note-id-you-used"],
  "diagram": null,
  "open": null,
  "code_task": null,
  "quiz": {
    "question": "one self-contained question",
    "code": null,
    "options": [
      {"text": "the correct option", "misconception": null},
      {"text": "a wrong option", "misconception": "kebab-case-belief"},
      {"text": "another wrong option", "misconception": "another-belief"}
    ],
    "correct": 0,
    "why": "one sentence on why the correct option is right"
  }
}
```

`correct` is the index in `options` of the option whose `misconception` is null.
Put the correct option in a varied position, not always first.
