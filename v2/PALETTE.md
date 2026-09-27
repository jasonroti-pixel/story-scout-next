# Story Scout Next v2 — Peak Arcade palette

The whole v2 look comes from **six owner colours**. Every other tone is a mix of two of them, or one of them darkened toward black or lightened toward white. No hue from outside the family is added, so every surface, shadow and pixel of scenery stays in harmony.

Source of truth: `tools/palette.py` (used by the pixel-art generator) ⇄ `css/style.css` `:root` (used by the UI). Keep both in sync.

## The six base colours

| Role | Name | Hex | Job |
|---|---|---|---|
| Dark base | Deep Space Blue | `#012641` | Page background, night skies, the "ink" family |
| Secondary dark | Burgundy | `#90202C` | Danger/junk, barns, bandana stripes, shadows under hot accents |
| Mid tone | Indigo Velvet | `#432371` | Borders, category tags, evening editions, mountains, loadout banner |
| Light surface | Antique White | `#F7E6D2` | Night-mode text, day-mode background, stars, highlights |
| Warm accent | Sandy Brown | `#FAAE7B` | Headings, morning editions, lit windows, the sun, "in loadout" |
| Hot accent | Raspberry Red | `#EE005A` | Primary action (START, Save, + Loadout), scores, beacons, the ball |

## Expanded ramps

The `(mix)` column shows how each tone is derived.

### Space (dark base)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--void` | `#000B14` | space × black 70% | Outlines, hard drop shadows, sprite ink |
| `--space-950` | `#00111D` | space × black 55% | Night panels, title-screen field, upper night sky |
| `--space-900` | `#011B2E` | space × black 30% | Cards inside panels, inputs, Nico's coat |
| `--space-800` | `#012641` | **BASE** | Page background, night sky |
| `--space-700` | `#12254D` | space × indigo 25% | Default buttons, coat highlight |
| `--space-600` | `#2D495B` | space × antique 18% | Day-mode dim text, muzzle sheen |
| `--space-500` | `#576974` | space × antique 35% | Nose glint, rare mid-grey |

### Indigo (mid tone)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--indigo-900` | `#1F2557` | indigo × space 55% | Far skylines, button undershade |
| `--indigo-800` | `#2F2463` | indigo × space 30% | Upper dusk sky, rooftop edges |
| `--indigo-700` | `#432371` | **BASE** | Panel borders, category tags, evening button, loadout banner |
| `--indigo-600` | `#634682` | indigo × antique 18% | Strong borders, bevel highlight, Nico's rim light, clouds |
| `--indigo-500` | `#826793` | indigo × antique 35% | Day-mode borders, snowcaps |
| `--indigo-300` | `#AF98AB` | indigo × antique 60% ("haze") | Night-mode dim text, secondary stars |

### Burgundy (secondary dark)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--burg-900` | `#3A2439` | burgundy × space 60% | Pier, fence, danger undershade, Nico's inner ear and eyes |
| `--burg-800` | `#652232` | burgundy × space 30% | Mouth interior, barn planks |
| `--burg-700` | `#90202C` | **BASE** | Danger buttons, CA tag, barn walls, plaid stripe, day headings |
| `--burg-600` | `#B1153C` | burgundy × raspberry 35% | Danger bevel highlight |

### Raspberry (hot accent)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--rasp-700` | `#C80D48` | raspberry × burgundy 40% | Primary button fill, score pills, bandana base, day hot text |
| `--rasp-600` | `#EE005A` | **BASE** | Checkbox on, medallion ring, beacons, sun's bottom stripes, ball |
| `--rasp-400` | `#F1457E` | raspberry × antique 30% | Night hot text (links, kickers), primary bevel |
| `--rasp-200` | `#F48FA4` | raspberry × antique 62% | Nico's tongue |

### Sandy (warm accent)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--sandy-800` | `#C06050` | sandy × burgundy 55% | Warm undershade, trail, eye iris, day Daily Goods heading (large text only) |
| `--sandy-700` | `#DA8363` | sandy × burgundy 30% | Trail edge, farmhouse trim |
| `--sandy-600` | `#FAAE7B` | **BASE** | Night headings, warning/morning buttons, toast, lit windows, sun |
| `--sandy-400` | `#F9C49E` | sandy × antique 40% | Sun highlight, Daily Goods night heading |
| `--sandy-200` | `#F8D5B8` | sandy × antique 70% | Warm button bevel |

### Antique (light surface)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--ant-25` | `#FEFCFA` | antique × white 90% | Day cards/inputs (one step above day panels) |
| `--ant-50` | `#FBF4EB` | antique × white 55% | Day panels, text on hot/dark buttons, sprite glints |
| `--ant-100` | `#F7E6D2` | **BASE** | Night body text, day page background, stars |
| `--ant-200` | `#F8D8BC` | antique × sandy 25% | Day default buttons, day sky |
| `--ant-300` | `#D7C3C1` | antique × indigo 18% | Day bevel shade, day far skyline |

### Scene bridges (for scenery depth only)
| Token | Hex | Mix | Use |
|---|---|---|---|
| `--dusk` | `#871568` | indigo × raspberry 40% | Horizon glow, sunset hills |
| `--mauve` | `#6A224E` | indigo × burgundy 50% | Mid hills, dumpster |
| `--ember` | `#C56754` | burgundy × sandy 50% | Warm eye reflections |

## Usage rules

1. **Dark base.** Night pages sit on `space-800`. Panels step darker (`space-950`) and cards step up (`space-900`), so depth reads from colour, not blur.
2. **Secondary dark.** Burgundy means *destructive or backstage*: JUNK, Clear, Remove, the offline badge, barns and piers. It is never a primary action.
3. **Mid tone.** Indigo carries structure: every border (`indigo-700` at 3px), category tags, and "evening". It is also the rim light that keeps black Nico readable on dark scenes.
4. **Light surface.** Antique White is text on dark and the surface itself in day mode. Pure `#FFFFFF` is never used; the brightest tone is `ant-25`, and only for day-mode cards.
5. **Warm accent.** Sandy is for attention without alarm: headings, morning, the toast, selected ("in loadout") cards. One warm focal point per component.
6. **Hot accent.** Raspberry is the single call to action per group (START, Save, + Loadout) plus scores. Base raspberry is never used for small text on dark: use `rasp-400` (night) or `rasp-700` (day).
7. **Shadows are hard and one colour.** Use `--void` (night) or `space-800` (day), offset 4px, with no blur and no glow.
8. **Bevels.** Buttons take a highlight 1–2 steps lighter on top and a shade 1–2 steps darker below, always from the same ramp as the fill.
9. **Scenery stays behind solid plates.** Scene art may use any token, but text never sits directly on scenery. It sits on a panel or plate (`--surface`).

## Text / background pairings (WCAG contrast)

| Text | Background | Ratio | Where |
|---|---|---|---|
| `ant-100` | `space-950` | 15.7 : 1 | Night body text on panels |
| `ant-50` | `space-950` | 17.5 : 1 | Night card titles |
| `indigo-300` | `space-950` | 7.2 : 1 | Night dim/meta text |
| `sandy-600` | `space-950` | 10.4 : 1 | Night headings |
| `rasp-400` | `space-950` | 5.4 : 1 | Night kickers, links |
| `ant-50` | `rasp-700` | 5.3 : 1 | Primary buttons, score pills |
| `space-800` | `sandy-600` | 8.4 : 1 | Warning/morning buttons, toast |
| `ant-50` | `indigo-700` | 11.2 : 1 | Success/evening buttons, tags |
| `ant-50` | `burg-700` | 7.9 : 1 | Danger buttons |
| `space-800` | `ant-50` | 14.2 : 1 | Day body text |
| `space-600` | `ant-50` | 8.7 : 1 | Day dim text |
| `burg-700` | `ant-50` | 7.9 : 1 | Day headings |
| `rasp-700` | `ant-50` | 5.3 : 1 | Day kickers, links |
| `sandy-800` | `ant-50` | 3.8 : 1 | Day Daily Goods heading, **large text only** |

Every pairing used for body-size text meets WCAG AA (4.5 : 1).

## Nico (character art)

Nico is **not drawn by the generator**. Every Nico sprite is sampled from the owner's approved art in `assets/src/` by `tools/extract_nico.py`, then re-mapped onto this palette:

| Source | Coat ramp (dark → light) | Why |
|---|---|---|
| `nico-closeup.jpg` (hero, badge, banner, footer, tab icon) | `void` → `space-950` → `space-900` → `indigo-900` → `space-600` → `indigo-600` → `indigo-300` | The close-up's charcoal has a warm lilac-grey sheen |
| `nico-sprite-sheet.jpg` (poses, credits, gallery, eggs) | `void` → `space-950` → `space-900` → `space-700` → `space-600` → `space-500` → `indigo-300` | The sheet's black is neutral with cool grey gloss |

- **Coat:** tones are assigned by luminance rank inside each sprite, so the source's shading structure is preserved exactly.
- **Tongue and gums:** `rasp-200` / `rasp-400` / `rasp-700`.
- **Mouth, lips and ear leather:** `burg-800` / `burg-900` / `mauve` / `ember`.
- **Teeth and catch-lights:** `ant-50` / `ant-200`.
- **Ball:** the source orange sits outside the palette, so it maps to the most saturated warm tones available (`sandy-600` / `sandy-700` / `ember` / `sandy-800`). The blue seam maps to `indigo-500` / `indigo-600` / `indigo-700`.
- **Bandana (added, from the brief):** red tartan with a `rasp-700` field, `burg-700`/`burg-800` bands, `sandy-800` pinstripe, a `rasp-600` lit hem and a `burg-900` shadow hem.

## Scenes

Scene SVGs paint with *role* classes (`s-sky0`, `s-far`, `s-win`…), not colours. `css/scenes.css` maps each role to a token twice: once for night and once for day. The same pixel art therefore re-lights with the theme, and every scene pixel stays on this palette.
