# Repository maintenance

Keep this repository clean, easy to use, and low-maintenance.

- Make focused commits with clear, descriptive commit messages.
- After completing and verifying a significant feature or bug fix, commit it and push it to `origin`.
- Do not push unfinished or known-broken work.
- Never force-push or rewrite shared history unless explicitly requested.
- Never commit credentials, secrets, generated caches, or machine-specific files.
- Keep `.gitignore` current.
- Before committing, review the diff and run the relevant available checks.
- Leave unrelated user changes untouched.
- Keep the working tree clean after completing a task whenever practical.

# Documentation

Treat `README.md` as the user-facing source of truth.

Update it whenever a change affects:

- installation or prerequisites;
- startup and usage;
- configuration;
- supported behavior;
- troubleshooting;
- project structure relevant to users.

Prefer simple setup steps and minimize ongoing maintenance requirements.
Do not add documentation churn for internal changes that do not affect users.
