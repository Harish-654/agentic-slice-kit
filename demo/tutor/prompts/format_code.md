
## The check: the student writes a small program

The student types Python into a code window and it is run against hidden tests.
There are no options and no written answer. Ask for ONE small function.

- `question`: what the function must do, self-contained, naming the function and its
  parameters (for example "Write `total(prices)` that returns the sum of the list").
- `starter`: the first line or two the student starts from, such as the `def` line
  with a `pass` body. Plain source, no fences. It must not contain the solution.
- `tests`: 2 to 4 hidden checks. Each is a Python expression that calls the student's
  function (`call`), the `repr` of the right result (`expected`), and a `belief`: a short
  kebab-case tag for the ONE wrong idea that a failure of this test exposes. Include at
  least one edge case (empty input, zero, a single item). Only use results whose `repr`
  is stable: numbers, strings, lists, tuples, dicts with one key, True/False/None.
- `model_solution`: a correct solution. It stays on the server.
- No input(), no files, no network, no randomness, nothing that prints.

## Output

Reply with ONE JSON object and nothing else, in exactly this shape. These key
names are required; do not rename, add or nest anything else.

IMPORTANT: the task goes under the key `code_task`. `quiz` and `open` MUST both be `null`.

```
{
  "covered": true,
  "explanation": "the lesson text",
  "citations": ["note-id-you-used"],
  "diagram": null,
  "quiz": null,
  "open": null,
  "code_task": {
    "question": "Write total(prices) that returns the sum of the list.",
    "starter": "def total(prices):\n    pass",
    "tests": [
      {"call": "total([1, 2, 3])", "expected": "6", "belief": "forgets-to-accumulate"},
      {"call": "total([])", "expected": "0", "belief": "empty-input-not-handled"}
    ],
    "model_solution": "def total(prices):\n    return sum(prices)"
  }
}
```
