# brand

SLSFC brand assets and the versioned implementation snapshot of the
**SLSFC Digital Design System**.

## Authority

- The **hosted SLSFC Digital Design System** is the authoring source of truth
  for digital visual design:
  <https://claude.ai/artifact/XJgvEM7VTUzrAbjbswy9fK>
- This folder holds a **read-only snapshot** of each approved release, so the
  website implementation and Claude Code have durable local documentation.
- Brand and design-system changes start in the hosted system. After approval,
  they are synchronized into this folder as a new release snapshot. Do not
  change design decisions by editing files here.
- WordPress/Elementor defaults, test content and legacy or exploratory
  artifacts are not brand authority.

## Current release

| Field | Value |
|---|---|
| Release | **v1.0** (approved 2026-10-02) |
| Hosted version | `1790961796-c84a` |
| Snapshot folder | [`design-system/v1.0/`](design-system/v1.0/) |
| Status | Approved; unresolved production items in [`open-items.md`](design-system/v1.0/open-items.md) |

## Layout

| Path | What it is |
|---|---|
| `design-system/v1.0/design-system.md` | Guidelines: voice, color, typography, layout, shape, crest, imagery, icons, motion |
| `design-system/v1.0/colors.md` | Brand and semantic color tokens, light (Away) and dark (Home) |
| `design-system/v1.0/typography.md` | Approved type families, styles and responsive steps |
| `design-system/v1.0/components.md` | Approved component patterns |
| `design-system/v1.0/open-items.md` | Unresolved production work (backlog) |
| `design-system/v1.0/tokens.json` | Exact copy of the hosted token file (machine-readable source) |
| `design-system/v1.0/tokens.css` | CSS custom properties (`--slsfc-*`) and type-style classes generated from `tokens.json` |
| `logos/` | Approved crest production files |

`colors.md`, `typography.md` and `tokens.css` are generated from `tokens.json`.
`design-system.md` and `components.md` copy the hosted guidelines; asset paths
are localized to this repo.

### Reserved location

`design-system/v1.0/slsfc-design-system-v1.0.pdf` is reserved for the v1.0
PDF guide. It has not been produced from the approved release yet. Add it only
as an export of the hosted v1.0 system, never as an independent recreation.

## Crest files

| File | Use | SHA-256 |
|---|---|---|
| `logos/slsfc-crest-master-rgb.ai` | Master (Adobe Illustrator, PDF-compatible). Print, embroidery, vendors. Originally `SLSFC_Crest_Master_RGB.ai`. | `a9e78a3196a14da22d00cd5b28e61bc0b7e92c4a3f635cf460fd7b494e51e8cf` |
| `logos/slsfc-crest.svg` | Web. Converted from the master, artboard trimmed to the shield. | `0c69ee39244ab46d452efdd4e226415a94e6c38e86774fd787aa5e5ccacc0935` |
| `logos/slsfc-crest-1024.png` | Transparent PNG, 1024px tall. Email, social, slides. | `60721b14faa91707e40e34b6e042401cdf5cf79c89cd8686b94feb4515186af1` |
| `logos/slsfc-crest-256.png` | Transparent PNG, 256px tall. Favicon source, small raster needs. | `9ee7e16f7617fa147150ab010e1ee731d5c3f14700d528a2ac7d0076908dabee` |

The SVG and PNG exports carry an embedded C2PA content-credentials manifest
(provenance metadata); the artwork is unchanged. Hashes are of the files as
committed here.

Use these files as supplied. Do not redraw, recolor or crop the crest. There
are no approved one-color or mono crests, wordmark or secondary marks yet; see
`open-items.md`. The concept boards stay in the hosted system as reference only
and are not copied here.

## Synchronizing a new release

1. Approve the change in the hosted design system.
2. Create `design-system/vX.Y/` beside the previous release; keep older
   releases unchanged.
3. Copy the hosted `tokens.json` exactly; regenerate `colors.md`,
   `typography.md` and `tokens.css` from it.
4. Copy the hosted guidelines and component docs; localize asset paths only.
5. Add or replace crest files only when the hosted system includes approved
   production artwork.
6. Update **Current release** above, and review the diff on a branch before
   merging through a PR.
