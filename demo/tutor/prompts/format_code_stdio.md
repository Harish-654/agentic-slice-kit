
## The check: the student writes a small program that reads input and prints output

The student types a complete program in the language on the LANGUAGE line into a code window. It is run
against hidden inputs and its printed output is compared with the expected output. There are no options
and no written answer. Ask for ONE small program.

- `question`: what the program must do, self-contained. State exactly what it reads (its format, one item
  per line or separated by spaces) and exactly what it must print, and include ONE worked example
  ("For the input `3` it prints `9`"). Never depend on anything the student cannot see.
- `starter`: the boilerplate the student starts from in that language, with the work left for them: a
  Java `public class Main` with an empty `main`, a C++ `main` with its `#include`s, a JavaScript reader
  that has read the input but not used it, or a Python `input()` line. Plain source, no fences. It must
  not contain the solution.
- `tests`: 2 to 4 hidden checks. Each has `stdin` (the exact text the program is given, ending in a
  newline), `expected` (the exact text it must print, without the final newline), and a `belief`: a short
  kebab-case tag for the ONE wrong idea that a failure of this test exposes. Include at least one edge
  case (zero, a single item, a negative number, the empty case). The output must be fully decided by the
  input: no randomness, no timing, no floating-point that could print differently, and one correct answer.
- `model_solution`: a correct, complete program in the language and version on the LANGUAGE line. It is
  run against your own tests before the student sees the question, so its output must match `expected`
  exactly. It stays on the server.
- No files, no network, no command-line arguments. Keep it to a few lines of solution.
- `style` is always `"stdio"`, and `call` is left out.

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
    "question": "Read one integer n and print n squared. For the input `3` it prints `9`.",
    "starter": "import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n        int n = in.nextInt();\n        // print n squared\n    }\n}",
    "tests": [
      {"stdin": "3\n", "expected": "9", "belief": "forgets-to-multiply"},
      {"stdin": "0\n", "expected": "0", "belief": "zero-not-handled"},
      {"stdin": "-4\n", "expected": "16", "belief": "negative-not-handled"}
    ],
    "model_solution": "import java.util.Scanner;\n\npublic class Main {\n    public static void main(String[] args) {\n        Scanner in = new Scanner(System.in);\n        int n = in.nextInt();\n        System.out.println(n * n);\n    }\n}",
    "style": "stdio"
  }
}
```
