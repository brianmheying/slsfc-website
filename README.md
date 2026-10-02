# slsfc-website

Official website and digital brand assets for St. Louis Squirrel Football Club (SLSFC).

The live site, [slsfc.org](https://slsfc.org), runs on WordPress with Elementor
and is hosted on SiteGround. This repository is the canonical source for
SLSFC-controlled code, brand assets, documentation, source copy, and exported
reusable WordPress/Elementor assets. WordPress itself remains the
authoritative runtime for site state that lives only there, such as published
content, media, settings, and plugin data.

## Layout

| Path                   | Purpose                                            |
|------------------------|----------------------------------------------------|
| `docs/`                | Architecture notes, runbooks, decision records     |
| `brand/`               | Logos, colors, typography, brand guidelines        |
| `content/`             | Source copy in Markdown                            |
| `wordpress/elementor/` | Exported Elementor templates and global kit (JSON) |

## Security

- No credentials, Application Passwords, API keys, or `.env` files are ever
  committed. WordPress credentials are stored in macOS Keychain.
- Every change to the live WordPress site requires explicit approval.

See [CLAUDE.md](CLAUDE.md) for the full working rules.
