# Slides — How to Use PKCE OAuth

A [Marp](https://marp.app/) deck (29 slides) plus a full English speaker script,
covering the PKCE OAuth use case, the sequence, a walkthrough of `main.py`, and a
live demo.

| File | What it is |
|---|---|
| [`deck.md`](deck.md) | The deck. Marp markdown. |
| [`SPEAKER-SCRIPT.md`](SPEAKER-SCRIPT.md) | What to actually say, slide by slide, plus timing and anticipated questions. |
| [`theme/pkce.css`](theme/pkce.css) | Custom Marp theme. |
| [`assets/*.svg`](assets/) | Hand-authored diagrams — use case, loopback topology, two sequence diagrams. |
| `build/` | Render output. Not committed. |

## Build

Needs [`marp-cli`](https://github.com/marp-team/marp-cli) (`brew install marp-cli`).

```bash
cd slides

# PDF
marp deck.md --theme theme/pkce.css --html --allow-local-files \
  --pdf -o build/pkce-oauth.pdf

# PowerPoint
marp deck.md --theme theme/pkce.css --html --allow-local-files \
  --pptx -o build/pkce-oauth.pptx

# PNG per slide — the fastest way to eyeball every slide for overflow
marp deck.md --theme theme/pkce.css --html --allow-local-files \
  --images png -o build/slide.png

# Live preview while editing
marp -w -s .
```

`--html` and `--allow-local-files` are both required: the diagrams are `<img>`
tags pointing at local SVGs inside `<div>` wrappers.

## Design notes

**Slides are skeletal on purpose.** All the prose lives in `SPEAKER-SCRIPT.md`.
If you find yourself wanting to add a paragraph to a slide, add it to the script
instead.

**Overflow is the main failure mode of a Marp deck**, so the theme is built to
prevent it:

- `section` has `overflow: hidden`, so anything that would spill is obvious when
  you render PNGs rather than silently bleeding off the page.
- Base font is 22px and code is 16px, with `.tight` / `.xtight` per-slide classes
  to dial code and tables down further.
- Diagrams are SVGs with a `viewBox`, wrapped in `.diagram`, so they scale to fit
  instead of overflowing.
- Sparse slide bodies are wrapped in `<div class="grow">`, which centres them in
  the space between the title and the `.takeaway` bar.

After any edit, re-render the PNGs and look at them. That is the whole QA process.

### Two Marp gotchas baked into the theme

**Tables must be `display: table`.** Marp's bundled default theme ships
`table { display: block; overflow: auto; width: max-content }` for GitHub-style
scrollable tables. Leave that in place and your `width: 100%` stretches the block
box while the real table grid shrink-wraps inside it — painting an empty white
panel to the right of the last column.

**In SVGs, set colour overrides with `style=`, not `fill=`.** A CSS rule in the
SVG's own `<style>` block beats a presentation attribute, so
`class="lbl" fill="#fff"` silently loses to `.lbl { fill: #12233b }`. Use
`class="lbl" style="fill:#fff"`.
