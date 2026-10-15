# Contributing to LedgerLens

Thanks for helping build LedgerLens. These rules keep our history readable and our live demo stable.

## Branches and pull requests

- `main` always deploys. Never push work that breaks the live app straight to `main`.
- Work on short-lived branches named by type and area, for example `feat/agents-ledger-reader` or
  `fix/web-upload-retry`.
- Open a pull request with a one-paragraph description of what changed and why. Add a screenshot for any
  UI change.
- We squash-merge pull requests, so each feature lands on `main` as one clear commit.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): what changed`,
in the imperative mood and under 72 characters. Add a short body when the reason isn't obvious.

| Type | Use it for | Example |
| --- | --- | --- |
| `feat` | A new capability | `feat(agents): add QRIS reader with per-field confidence` |
| `fix` | A bug fix | `fix(web): keep upload progress when the phone sleeps` |
| `test` | Tests only | `test(tools): cover cash-flow tiers in calculator` |
| `docs` | Documentation | `docs: explain how Firestore streams live progress` |
| `refactor` | Restructuring without changing behaviour | `refactor(api): move run state into a service` |
| `build`, `ci`, `chore` | Dependencies, pipelines, tooling | `build(api): pin google-genai 2.30.1` |

Scopes: `web`, `api`, `agents`, `tools`, `eval`, `data`, `infra`, `docs`.

Commit as yourself: set `git config user.email` to the email on your GitHub account so your work is
credited to you.

## Never commit

- `.env` files, service-account keys or any other credential (the `.gitignore` blocks the common ones,
  but check `git status` before every commit).
- Real personal data. All demo data in this repository is synthetic.
- Large generated files such as raw evaluation output.

## Releases

Milestones are tagged with semantic versions (`v0.1.0` skeleton, `v0.5.0` end to end, `v1.0.0`
submission) and published as GitHub Releases. History on `main` is never rewritten or force-pushed.
