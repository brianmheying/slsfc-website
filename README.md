# slsfc-website

Official website implementation and approved production brand assets for St. Louis Squirrel Football Club (SLSFC).

The live site, [slsfc.org](https://slsfc.org), runs on WordPress with Elementor
and is hosted on SiteGround.

## Sources of truth

- **Visual design:** the hosted SLSFC Digital Design System is authoritative
  for digital visual-design decisions.
- **This repository** is canonical for SLSFC-controlled website
  implementation, version-controlled design-system release snapshots,
  approved production assets stored here, source copy, documentation,
  tooling, and exported reusable WordPress/Elementor assets.
- `brand/design-system/v1.0/` is a frozen implementation snapshot of the
  approved hosted release, not an independent design authority.
  `brand/logos/` holds approved production assets that implementation may
  consume. See [brand/README.md](brand/README.md).
- **WordPress runtime state** is not generally canonical to the repo.
  WordPress itself remains authoritative for site state that lives only
  there, such as published content, media, settings, and plugin data.

## Layout

| Path                   | Purpose                                            |
|------------------------|----------------------------------------------------|
| `docs/`                | Architecture notes, runbooks, decision records     |
| `brand/`               | Approved crest files, design-system snapshots      |
| `content/`             | Source copy in Markdown                            |
| `wordpress/elementor/` | Exported Elementor templates and global kit (JSON) |

## Security

- No credentials, Application Passwords, API keys, or `.env` files are ever
  committed. WordPress credentials are stored in macOS Keychain.
- Every change to the live WordPress site requires explicit approval.

See [CLAUDE.md](CLAUDE.md) for the full working rules.
