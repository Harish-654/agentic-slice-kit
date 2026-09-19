
## The check: a question answered in the student's own words

The student types the answer, so there are no options. Ask something whose
answer takes a sentence or two of explanation, not a single word.

- One question that tests understanding. If it is about code, the code goes in
  `code` (plain source, no fences) and the question must not depend on anything
  else. Never write "the following code" unless `code` is filled in.
- `rubric`: 2 to 4 short points a correct answer must contain. This is how the
  answer will be graded, so make each point checkable.
- `model_answer`: a good answer in two or three sentences.
- `common_mistakes`: 2 or 3 specific wrong beliefs a student might hold about
  this, each with a short kebab-case `belief` tag and the `sign` that an answer
  is holding it.

## Output

Reply with ONE JSON object and nothing else, in exactly this shape. These key
names are required; do not rename, add or nest anything else.

IMPORTANT: the question goes under the key `open`. The key `quiz` is only for
multiple choice, so here it MUST be `null`. Never put a question, a rubric or a
model answer under `quiz`.

```
{
  "covered": true,
  "explanation": "the lesson text",
  "citations": ["note-id-you-used"],
  "diagram": null,
  "quiz": null,
  "open": {
    "question": "one self-contained question",
    "code": null,
    "rubric": ["a point a correct answer contains", "another point"],
    "model_answer": "a good answer in two or three sentences",
    "common_mistakes": [
      {"belief": "kebab-case-belief", "sign": "what an answer holding it says"}
    ]
  }
}
```
