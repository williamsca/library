## Design Direction: The Catalog of a Drowned Library

### Atmosphere

The site should feel like consulting an index that has existed far longer than the internet—longer, perhaps, than the books it contains. Not a *dark mode* website, but a *dim* one. The sense that you've descended stone stairs to reach this terminal. Institutional, but the institution predates any you've heard of.

### Typography

**Body text:** An old-style serif with humanist bones. EB Garamond or Cormorant Garamond—something with the irregularity of metal type, not the clinical precision of modern revivals. Text should feel *set*, not displayed.

**Headers/Labels:** Small caps, generously letter-spaced. Categories and metadata rendered in the manner of archival accession records: `AUTHOR · MCMXCII · PROVIDENCE`

**The search field:** A single monospaced input, like querying a mainframe. No placeholder text—just a blinking cursor and perhaps a simple glyph or sigil beside it.

### Color

Not parchment-cute. Think:
- **Background:** A warm, dim off-white—the color of paper that has spent decades in controlled humidity. `#f4f1ea` or darker.
- **Text:** Not pure black. A sepia-black, `#2c2416`, the color of iron gall ink.
- **Accent (sparingly):** A single institutional color. Deep burgundy `#5c1a1a` or verdigris `#3a5a4a`. Used only for the rarest emphasis—a sigil, a link underline on hover.

### Layout

**The search bar:** Centered and alone at the top of the page. No navigation, no header. Just the field. Perhaps above it, a single line in small caps: the name of the collection, or a Latin epigraph.

**Results:** A dense vertical list. No cards, no images (unless requested). Each entry is a single block of information, separated by a thin rule or simply by whitespace:

```
MCCARTHY, CORMAC
Blood Meridian, or The Evening Redness in the West
1985 · Knopf · United States

    "Whatever in creation exists without my knowledge
     exists without my consent."
```

The hierarchy is clear through typography alone: author in small caps, title in italic, metadata in a smaller size. Notes or quotes indented and set in a slightly lighter weight.

### Texture

Resist the temptation for obvious paper textures or "old book" clichés. Instead:
- Subtle vertical hairline rules as dividers
- Generous margins, as if the content is set within a larger, invisible page
- Perhaps a single decorative element: an engraved ornament, a seal, a printer's mark—placed once, at the top or bottom of the page, not repeated

### Interaction

**Almost none.** 
- Links are underlined in the classical manner; on hover, the underline simply disappears or shifts to the accent color
- No transitions. State changes are immediate—as if the page is being *redrawn* rather than animated
- The search should feel like incantation: type a query, press Enter, the list reforms

### The Map (Future)

When you add the map feature, consider:
- An engraved or etched cartographic style—counties as simple outlined regions, not filled polygons
- A decorative cartouche containing the legend
- Time period selection via a discrete slider or simple dropdown, perhaps labeled with centuries in Roman numerals (XIV–XV, XVI–XVII)
- Hovering over a county reveals its name in a small, quiet tooltip—no pop-up cards

### Sample HTML Structure (Conceptual)

```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│         CATALOGUS LIBRORUM WILLIAMS                  │
│              ━━━━━━━━━━━━━━━━━━━━━                        │
│                                                          │
│                    [ _____________ ]                      │
│                                                          │
│  ─────────────────────────────────────────────────────── │
│                                                          │
│  BORGES, JORGE LUIS                                      │
│  Ficciones                                               │
│  1944 · Buenos Aires                                     │
│                                                          │
│  ─────────────────────────────────────────────────────── │
│                                                          │
│  LOVECRAFT, HOWARD PHILLIPS                              │
│  At the Mountains of Madness                             │
│  1936 · Astounding Stories · Providence                  │
│                                                          │
│  ─────────────────────────────────────────────────────── │
│                                                          │
│                        ❧                                 │
└──────────────────────────────────────────────────────────┘
```