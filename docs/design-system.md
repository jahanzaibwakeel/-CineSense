# CineSense design system — Phase 1

## Brand promise

**Describe the feeling. Discover the film.** CineSense should feel like a premium film journal: dark, editorial, cinematic, and welcoming. Film artwork carries the emotion; violet is a restrained action accent, not a color applied to every control. Avoid dashboard styling, repetitive rounded cards, glass effects, and unsupported movie art.

## Foundations

| Role | CSS token | Value |
|---|---|---|
| Main background | `--paper` | `#09090D` |
| Secondary surface | `--surface` | `#101017` |
| Elevated surface | `--elevated` | `#171720` |
| Primary text | `--ink` | `#F4F1F8` |
| Secondary text | `--muted` | `#A5A1B0` |
| Muted text | `--quiet` | `#777383` |
| Accent | `--accent` | `#9475F5` |
| Secondary accent | `--lavender` | `#C6B8F5` |
| Divider | `--line` | `#FFFFFF20` |
| Interface type | `--sans` | DM Sans with Arial fallback |
| Editorial type | `--serif` | Playfair Display with Georgia fallback |

Tailwind v4 is configured through PostCSS and maps its CineSense color utilities to these CSS variables. Lucide React supplies interface icons. The design keeps bespoke editorial artwork in CSS rather than turning every layout decision into a utility string.

## Interaction and accessibility

- Keep a visible keyboard focus ring; use semantic links for navigation and buttons for actions.
- Respect `prefers-reduced-motion`; keep transitions short and optional.
- Do not make a feature look enabled before its data/API path works. The foundation's discovery input is disabled and labeled as a preview; mood examples are non-interactive text.
- Preserve legible body text, responsive hierarchy, consistent poster ratios, and accessible names/alternative text for sourced artwork.
- Use only source-authorized imagery. If no licensed art is available, use a designed placeholder, never a random remote image or broken URL.

## Current product surface

The landing screen establishes the brand, editorial heading, disabled discovery preview, and abstract non-film artwork. It does not imply that movie search or recommendation is available. Feature pages and component variants will be added as backend contracts become real.
