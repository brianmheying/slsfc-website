# CLAUDE.md — SLSFC Website

Guidance for Claude Code working in this repository.

## Project

Source-controlled workspace for **slsfc.org**, the website of the St. Louis
Squirrel Football Club (SLSFC).

- **CMS/runtime:** WordPress + Elementor, hosted on SiteGround.
- **Sources of truth:**
  - **Visual design:** the hosted SLSFC Digital Design System is
    authoritative for digital visual-design decisions (see
    [Design system authority](#design-system-authority)).
  - **This repository** is canonical for SLSFC-controlled website
    implementation, version-controlled design-system release snapshots,
    approved production assets stored here, source copy, documentation,
    tooling, and exported reusable WordPress/Elementor assets.
  - `brand/design-system/v1.0/` is a frozen implementation snapshot of the
    approved hosted release, not an independent design authority.
    `brand/logos/` holds approved production assets that implementation may
    consume.
  - **WordPress runtime state** is not generally canonical to the repo.
    Content, settings, media, users, and plugin data in WordPress may exist
    only there. Do not assume the repo reflects the live site, and do not
    overwrite WordPress state to match the repo without approval.
- **Remote access:** authenticated WordPress REST API using a dedicated
  Application Password.
- **Environment:** `slsfc.org` is the only WordPress environment currently in
  use. There is no staging site, and the site is under construction.

## Design system authority

- **Visual-design authority:** the hosted **SLSFC Digital Design System** is
  the source of truth for digital visual design (current release: v1.0). See
  `brand/README.md`.
- **This repo:** the version-controlled implementation target. `brand/`
  holds a read-only snapshot of each approved release (`brand/design-system/`)
  and the approved crest files (`brand/logos/`).
- **Direction of change:** brand and design-system changes start in the
  hosted system. After approval they are deliberately synchronized into
  `brand/` as a release snapshot. Do not change design decisions by editing
  the snapshot.
- **No silent overrides:** implementation (CSS, Elementor globals, templates,
  copy) must not redefine or override approved design-system decisions. If an
  implementation need conflicts with the system, stop and raise it.
- **Not brand authority:** WordPress/Elementor defaults, the factory Elementor
  Kit, test or placeholder content, and legacy or exploratory artifacts.
- **Open items stay open:** items in
  `brand/design-system/v1.0/open-items.md` are resolved only in the hosted
  system with real artwork or decisions; never recreate missing assets here.
- The security rules, approval requirements and WordPress/Elementor write
  restrictions below are unchanged and still apply.

## Security rules (non-negotiable)

1. **Never commit secrets.** No credentials, API keys, Application Passwords,
   tokens, `.env` files, or private keys in the repo, in commit messages, or
   in GitHub issues or PRs.
2. **Never expose secrets.** Do not print, echo, log, or paste credential
   values into output, documentation, or commands whose output is shown.
   WordPress credentials are stored in **macOS Keychain**. Scripts must read
   them at runtime, and Claude must never read or display the value.
3. **Every WordPress write requires explicit approval.** Before any `POST`,
   `PUT`, `PATCH`, or `DELETE` to slsfc.org, state exactly what will change
   (endpoint, object ID, fields) and wait for a clear "yes". An approval may
   cover either one specifically described action or an explicitly defined
   batch of actions, with every action in the batch listed. Approval never
   extends beyond that stated scope. Anything not covered, including retries
   with different parameters, follow-up fixes, or newly discovered changes,
   needs a new approval.
4. **Out of bounds without explicit approval:** WordPress users, roles,
   authentication, Application Passwords, plugins, themes, site settings,
   SiteGround hosting configuration, DNS, and any production infrastructure.
5. **Prefer reversible changes.** Create content as `draft` before
   publishing. Export or snapshot the current state of anything before
   changing it. Never permanently delete; move to trash only with approval.
6. **Read before write.** Use read-only (`GET`) requests to inspect current
   state before proposing a change.

## Git workflow

- Do not commit to `main` directly. Work on a branch and merge through a PR.
- Do not commit, push, or open a PR until the user approves it.
- Never force-push.
- Run `git status` / `git diff` before committing and check that no secrets
  or backup files are staged.

## Repository layout

| Path                   | Purpose                                                  |
|------------------------|----------------------------------------------------------|
| `docs/`                | Architecture notes, runbooks, decision records           |
| `brand/`               | Approved crest files and design-system release snapshots |
| `content/`             | Source copy in Markdown for site pages                   |
| `wordpress/elementor/` | Exported Elementor templates and global kit (JSON)       |

Only add a new top-level directory (child theme, scripts, snapshots, and so
on) when there is real content for it. Do not create directories speculatively.

## Conventions

- Use lowercase kebab-case for file and directory names.
- Use Markdown for documentation and site copy.
- Commit Elementor exports as pretty-printed JSON so diffs are readable.
