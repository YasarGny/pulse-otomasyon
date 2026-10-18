# Working on PULSE

Use the existing checkout; do not create a worktree unless requested. Read
`docs/OPERATIONS.md` and run the relevant Python, JavaScript and browser checks.
Browser fixtures use synthetic audio and never require paid synthesis.

## Audio consent

The user requires explicit approval before any manual real audio generation or
regeneration, including `refresh_audio`, `expanded_issue`, local pipeline runs
and manually starting the daily-generation workflow. Ask before doing so; do not
treat approval to fix or deploy the website as audio-generation approval.
The existing authorized daily schedule is separate; do not change it silently.
Use `refresh-website.yml` for interface-only deployments: it preserves the current
news, publication identity and all four existing audio files.

PULSE must be pronounced **Pals**. Both summary and podcast use the shared
`pulse/speech.py` pronunciation copy; canonical published/reviewed text retains
the original names. Never remove that pronunciation layer or change working
Edge/Gemini voices without a specific reason and verification.
