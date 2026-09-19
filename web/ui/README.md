# Tutor UI

The chat page for the tutor. React 19, Vite, Tailwind 4, [shadcn/ui](https://ui.shadcn.com)
components, and [assistant-ui](https://github.com/assistant-ui/assistant-ui) for the thread.

**You do not need Node to run the tutor.** The compiled app is committed in `dist/` and
`uvicorn web.student:app` serves it. Node is only for changing this UI.

```bash
npm install
npm run dev      # http://localhost:5173, proxies /api to the Python server on :8001
npm run build    # writes dist/ - commit it
```

Run the Python server too (`python -m uvicorn web.student:app --port 8001`) while developing.

## How it fits together

- `web/tutor_api.py` turns a session's history into chat messages (`GET /api/sessions/{id}`).
  The page polls it while a lesson is being written and stops when it is the student's turn.
- `src/components/tutor/TutorRuntime.tsx` maps those messages onto assistant-ui's
  `useExternalStoreRuntime`. A lesson is one assistant message; its quiz, diagram, feedback and
  end-of-session cards are tool-call parts, drawn by `cards.tsx`.
- `src/lib/api.ts` mirrors the API's shapes. If you change one side, change the other.
- The correct option is never sent to the browser until the student has answered.

## Changing components

`src/components/ui/` is shadcn's (`npx shadcn@latest add <name>`). `src/components/assistant-ui/`
is assistant-ui's markdown renderer. The rest, in `src/components/tutor/`, is ours.
