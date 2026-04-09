# V3 Glassmorphism Redesign Spec -- Vitreon Legal Chat UI

> Reference: [chatgpt-dark-glassmorphism](https://github.com/gastonmorixe/chatgpt-dark-glassmorphism)
> Target: `.design-v3.dark` scope only (light mode untouched for now)
> Files to modify: `globals.css` (CSS vars + utility classes), `chat/page.tsx` (structural), `chat-input.tsx`, `chat-message.tsx`, `sources-panel.tsx`

---

## 0. Design Philosophy

The reference uses **pure black (#000) background** with translucent panels floating on top. Every surface is transparent with blur -- nothing is opaque. The aesthetic is:

- **Background**: True black with no aurora animation (or optional extremely subtle aurora)
- **Panels**: `rgba(9,9,9,0.73)` with `backdrop-filter: blur(10px)` and layered inset + drop shadows
- **Input areas**: `rgba(19,19,19,0.64)` with `backdrop-filter: blur(15px)`
- **Borders**: Dual-layer inset glow (`inset 0 0px 2px 1px #dedede38`) creating the "frosted edge" illusion
- **Navigation**: Transparent with gradient fade-to-black (not a solid bar)
- **Text**: High-contrast white at ~87% opacity (`oklch(0.87 0 0 / 0.9)`)

The reference is **achromatic** -- no brand colors on surfaces. Accent color is minimal. This spec adapts that to Vitreon's iris palette by using iris as a *trace accent*, not a surface color.

---

## 1. Color Palette

### Current V3 Dark
```css
--background: #07091A;          /* near-black indigo */
--v3-iris: #8B6FD4;             /* bright iris accent */
--v3-aurora: #38BDF8;           /* sky blue */
--v3-teal: #2DD4BF;             /* mint teal */
```

### Target Glassmorphism Dark
```css
/* Page canvas -- true black, not dark-indigo */
--background: #000000;

/* Surface palette -- achromatic with near-invisible warmth */
--gm-surface-0: rgba(9, 9, 9, 0.73);       /* Main panel (sidebar, chat) */
--gm-surface-1: rgba(19, 19, 19, 0.64);     /* Nested elements (input, cards) */
--gm-surface-2: rgba(30, 30, 30, 0.50);     /* Hover states */
--gm-surface-3: rgba(50, 50, 50, 0.21);     /* Subtle hover on list items */

/* Accent -- iris at ultra-low opacity for trace presence */
--gm-accent: #8B6FD4;
--gm-accent-glow: rgba(139, 111, 212, 0.12);
--gm-accent-border: rgba(139, 111, 212, 0.20);

/* Text -- pure white at varying opacity */
--gm-text-primary: oklch(0.87 0 0 / 0.90);
--gm-text-secondary: oklch(0.87 0 0 / 0.60);
--gm-text-tertiary: oklch(0.87 0 0 / 0.40);
--gm-text-quaternary: oklch(0.87 0 0 / 0.22);

/* Border system -- the key to glassmorphism */
--gm-border-outer: rgba(222, 222, 222, 0.22);       /* #dedede38 */
--gm-border-inner-glow: rgba(222, 222, 222, 0.14);  /* subtle inner catchlight */
```

---

## 2. Glass Tier System

Three tiers, each with specific blur/opacity/shadow combos.

### Tier 1: Structural Panels (Sidebar, Chat Container)
```css
.gm-glass-structural {
  background: rgba(9, 9, 9, 0.73);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid rgba(222, 222, 222, 0.22);
  border-radius: 16px;
  box-shadow:
    0 10px 14px 4px rgba(0, 0, 0, 0.23),
    0 10px 19px 1px rgba(0, 0, 0, 0.27),
    inset -2px 0 10px 10px rgba(67, 67, 67, 0.15),
    inset 0 0 2px 1px rgba(222, 222, 222, 0.22);
}
```

### Tier 2: Interactive Surfaces (Input, Cards, Source Chips)
```css
.gm-glass-interactive {
  background: rgba(19, 19, 19, 0.64);
  backdrop-filter: blur(15px);
  -webkit-backdrop-filter: blur(15px);
  border: 1px solid rgba(222, 222, 222, 0.14);
  border-radius: 12px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 4px 16px rgba(0, 0, 0, 0.30);
}
```

### Tier 3: Minimal Surfaces (List Items, Hover States)
```css
.gm-glass-minimal {
  background: rgba(50, 50, 50, 0.21);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 8px;
  box-shadow: none;
}
```

---

## 3. Component Specifications

### 3.1 Page Background

**Current** (`.design-v3.dark`):
```css
--background: #07091A;

/* aurora-bg-static::before gradient with oklch violet/blue/teal blobs */
/* filter: blur(60px); animation: aurora-drift */
```

**Target**:
```css
--background: #000000;
```

The aurora is **removed** or made extremely subtle (10% opacity max). The reference uses a flat pure black. If aurora is kept, reduce to:

```css
.design-v3.dark .aurora-bg-static::before {
  background:
    radial-gradient(ellipse 60% 40% at 20% 30%, rgba(139, 111, 212, 0.04) 0%, transparent 60%),
    radial-gradient(ellipse 50% 60% at 75% 50%, rgba(56, 189, 248, 0.03) 0%, transparent 55%),
    #000000;
  filter: blur(100px);
}
```

Or for the purest glassmorphism look, set the pseudo-element to `display: none`.

---

### 3.2 Chat Container (Main Panel)

**Current** (`makeGlassPanel(isV3)` in page.tsx):
```css
background: var(--v3-glass-elevated-bg);         /* rgba(255,255,255,0.09) */
backdrop-filter: blur(40px) saturate(200%) brightness(106%);
border: 1px solid rgba(255,255,255,0.14);
border-radius: 28px;
box-shadow: 0 12px 48px rgba(0,0,0,0.50), 0 2px 8px rgba(0,0,0,0.30),
            inset 0 1px 0 rgba(255,255,255,0.10);
```

**Target** -- Tier 1 structural glass:
```css
background: rgba(9, 9, 9, 0.73);
backdrop-filter: blur(10px);
-webkit-backdrop-filter: blur(10px);
border: 1px solid rgba(222, 222, 222, 0.22);
border-radius: 16px;
box-shadow:
  0 10px 14px 4px rgba(0, 0, 0, 0.23),
  0 10px 19px 1px rgba(0, 0, 0, 0.27),
  inset -2px 0 10px 10px rgba(67, 67, 67, 0.15),
  inset 0 0 2px 1px rgba(222, 222, 222, 0.22);
overflow: hidden;
```

**Key changes**:
- Background: `0.09 white -> 0.73 near-black` (reference's sidebar opacity)
- Blur: `40px -> 10px` (reference uses lighter blur on darker surfaces)
- Saturate/brightness filters removed (not needed on near-black)
- Border: white at 14% -> #dedede at 22% (slightly warmer, more visible edge)
- Shadow: completely new layered shadow system from reference
- Border-radius: 28px -> 16px (less bubbly, more serious)

**Implementation**: Update `makeGlassPanel(isV3)` in `page.tsx` to use new CSS vars. Alternatively, define `.gm-glass-structural` in globals.css and apply it via className in V3+dark context.

---

### 3.3 Top Nav Bar (Chat Header)

**Current** (inline styles in page.tsx chat header):
```css
border-bottom: 0.5px solid var(--dt-glass-border-subtle);    /* rgba(255,255,255,0.05) */
background: var(--dt-glass-bg-subtle);                        /* rgba(255,255,255,0.02) */
```

**Target** -- gradient fade like the reference `#page-header`:
```css
background: linear-gradient(180deg, rgba(0, 0, 0, 0.60) 0%, transparent 100%);
border-bottom: 1px solid rgba(222, 222, 222, 0.08);
box-shadow: none;
```

The header should **not** have a hard border or solid background. It fades from slightly darkened at top to transparent, letting the chat content scroll underneath. This creates the depth illusion of content going behind the header.

**Alternative** (if the header is not sticky/overlapping messages):
```css
background: rgba(9, 9, 9, 0.50);
backdrop-filter: blur(8px);
-webkit-backdrop-filter: blur(8px);
border-bottom: 1px solid rgba(222, 222, 222, 0.10);
```

---

### 3.4 Message Bubbles

#### 3.4.1 User Messages

**Current** (`chat-message.tsx` user branch):
```css
background: var(--dt-confidence-bg);           /* rgba(123,94,167,0.12) */
border: 1px solid var(--dt-confidence-border); /* rgba(123,94,167,0.28) */
border-radius: 16px 16px 4px 16px;
backdrop-filter: blur(16px);
```

**Target** -- Tier 2 interactive glass with subtle iris trace:
```css
background: rgba(19, 19, 19, 0.64);
backdrop-filter: blur(15px);
-webkit-backdrop-filter: blur(15px);
border: 1px solid rgba(139, 111, 212, 0.18);
border-radius: 16px 16px 4px 16px;
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.06),
  0 4px 12px rgba(0, 0, 0, 0.25);
```

The iris accent is visible only in the border (18% opacity) -- enough to distinguish from AI messages but not a colored "bubble."

#### 3.4.2 Assistant Messages (Answer Card)

**Current** (`answerCardStyle` in chat-message.tsx):
```css
background: var(--dt-answer-bg);               /* rgba(255,255,255,0.05) */
border: 0.5px solid var(--dt-answer-border);   /* rgba(255,255,255,0.09) */
border-radius: 16px;                            /* RADIUS.xl */
```

**Target** -- distinct from user messages, slightly more transparent:
```css
background: rgba(14, 14, 14, 0.55);
backdrop-filter: blur(12px);
-webkit-backdrop-filter: blur(12px);
border: 1px solid rgba(222, 222, 222, 0.10);
border-radius: 16px;
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.04),
  0 2px 8px rgba(0, 0, 0, 0.20);
```

No iris tint on the assistant card border -- pure achromatic glass.

---

### 3.5 Source Cards / Chips

**Current** (sources-panel.tsx, using `.v3-source-card`):
```css
background: var(--v3-glass-surface-bg);              /* rgba(255,255,255,0.05) */
border: 1px solid var(--v3-glass-surface-border);    /* rgba(255,255,255,0.09) */
border-top: 1.5px solid <jurisdiction-color>;        /* colored top edge */
backdrop-filter: blur(20px) saturate(180%);
border-radius: 9999px;                               /* pill */
```

**Target** -- Tier 2 interactive glass, keep jurisdiction color accent:
```css
background: rgba(19, 19, 19, 0.64);
backdrop-filter: blur(15px);
-webkit-backdrop-filter: blur(15px);
border: 1px solid rgba(222, 222, 222, 0.12);
border-left: 2px solid <jurisdiction-color>;    /* move from top to left -- more subtle */
border-radius: 8px;                              /* rounded rect, not pill */
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.05),
  0 2px 8px rgba(0, 0, 0, 0.20);
transition: background 0.15s ease, border-color 0.15s ease;
```

**Hover**:
```css
background: rgba(30, 30, 30, 0.70);
border-color: rgba(222, 222, 222, 0.20);
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.08),
  0 4px 16px rgba(0, 0, 0, 0.30);
```

---

### 3.6 Input Area (ChatInput)

**Current** (`chat-input.tsx`):
```css
/* dark + focused */
background: rgba(255, 255, 255, 0.08);
backdrop-filter: blur(32px) saturate(160%);
border: 0.5px solid rgba(201, 168, 76, 0.40);
box-shadow: inset 0 1px 0 rgba(255,255,255,0.10),
            0 0 0 3px rgba(201,168,76,0.08),
            0 2px 16px rgba(201,168,76,0.10);
```

**Target** -- reference's composer style:
```css
/* default state */
background: rgba(19, 19, 19, 0.64);
backdrop-filter: blur(15px);
-webkit-backdrop-filter: blur(15px);
border: 1px solid rgba(222, 222, 222, 0.14);
border-radius: 16px;
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.05),
  0 4px 16px rgba(0, 0, 0, 0.25);
transition: border-color 0.25s ease, box-shadow 0.25s ease, background 0.25s ease;

/* focused state */
background: rgba(19, 19, 19, 0.72);
border-color: rgba(139, 111, 212, 0.30);
box-shadow:
  inset 0 1px 0 rgba(255, 255, 255, 0.06),
  0 0 0 2px rgba(139, 111, 212, 0.08),
  0 4px 24px rgba(0, 0, 0, 0.35);
```

**Send button**:
```css
/* active (has text) */
background: linear-gradient(135deg, rgba(139, 111, 212, 0.85), rgba(157, 127, 204, 0.90));
color: #000000;
border-radius: 8px;

/* inactive */
background: rgba(50, 50, 50, 0.40);
color: rgba(255, 255, 255, 0.25);
```

**Placeholder text**:
```css
.dark textarea::placeholder { color: rgba(255, 255, 255, 0.22); }
```

**Caret color**:
```css
caret-color: rgba(139, 111, 212, 0.80);
```

---

### 3.7 History Panel (Sidebar)

**Current** (`makeGlassPanel(isV3)` on history panel):
Same as chat container -- V3 elevated glass.

**Target** -- Tier 1 structural glass, same as chat panel but potentially a separate floating panel:
```css
background: rgba(9, 9, 9, 0.73);
backdrop-filter: blur(10px);
-webkit-backdrop-filter: blur(10px);
border: 1px solid rgba(222, 222, 222, 0.22);
border-radius: 16px;
overflow: hidden;
box-shadow:
  0 10px 14px 4px rgba(0, 0, 0, 0.23),
  0 10px 19px 1px rgba(0, 0, 0, 0.27),
  inset -2px 0 10px 10px rgba(67, 67, 67, 0.15),
  inset 0 0 2px 1px rgba(222, 222, 222, 0.22);
```

**History list items**:

*Default*:
```css
background: transparent;
border: 1px solid transparent;
border-radius: 8px;
color: oklch(0.87 0 0 / 0.60);
```

*Hover*:
```css
background: rgba(50, 50, 50, 0.21);
border-color: rgba(255, 255, 255, 0.06);
color: oklch(0.87 0 0 / 0.80);
```

*Active*:
```css
background: rgba(139, 111, 212, 0.10);
border-color: rgba(139, 111, 212, 0.18);
color: oklch(0.87 0 0 / 0.90);
font-weight: 600;
```

**History header** (section label "Chats"):
```css
color: oklch(0.87 0 0 / 0.40);
border-bottom: 1px solid rgba(222, 222, 222, 0.08);
background: rgba(9, 9, 9, 0.40);
```

---

### 3.8 Grounding / Source Preview Panel (Right Drawer)

**Current**: Same `makeGlassPanel(isV3)`.

**Target**: Tier 1 structural glass, identical to chat container.

---

### 3.9 Jurisdiction Selector Pills

**Current**:
```css
/* active */
background: var(--dt-color-gold-solid);    /* rgba(157,127,204,0.75) */
border: 0.5px solid var(--dt-color-gold-border);

/* inactive */
background: var(--dt-pill-bg);             /* rgba(255,255,255,0.05) */
border: 0.5px solid var(--dt-glass-border);
```

**Target** -- achromatic inactive, iris-traced active:
```css
/* active */
background: rgba(139, 111, 212, 0.16);
border: 1px solid rgba(139, 111, 212, 0.30);
color: rgba(255, 255, 255, 0.92);
font-weight: 700;
border-radius: 8px;

/* inactive */
background: rgba(50, 50, 50, 0.21);
border: 1px solid rgba(255, 255, 255, 0.06);
color: rgba(255, 255, 255, 0.50);
font-weight: 500;
border-radius: 8px;

/* hover (inactive only) */
background: rgba(50, 50, 50, 0.35);
border-color: rgba(255, 255, 255, 0.12);
color: rgba(255, 255, 255, 0.70);
```

---

### 3.10 Follow-Up Suggestion Buttons

**Current**:
```css
background: var(--dt-button-bg-hover);     /* rgba(255,255,255,0.08) */
border: 1px solid var(--dt-glass-border);  /* rgba(255,255,255,0.14) */
border-radius: 9999px;
```

**Target**:
```css
background: rgba(30, 30, 30, 0.50);
border: 1px solid rgba(222, 222, 222, 0.12);
border-radius: 9999px;                     /* keep pill shape */
backdrop-filter: blur(8px);
-webkit-backdrop-filter: blur(8px);
color: rgba(255, 255, 255, 0.60);
transition: all 0.15s ease;

/* hover */
background: rgba(40, 40, 40, 0.60);
border-color: rgba(222, 222, 222, 0.20);
color: rgba(255, 255, 255, 0.85);
```

---

### 3.11 Document Index Panel

Same Tier 1 structural glass treatment as the history panel. Internal items follow the Tier 3 minimal glass for list items.

---

### 3.12 Error / Warning Banners

**Current**:
```css
background: var(--dt-error-bg-subtle);     /* rgba(255,80,60,0.10) */
border-bottom: 0.5px solid var(--dt-error-border-subtle);
```

**Target** -- keep semantic color, adapt to glass:
```css
background: rgba(248, 113, 113, 0.08);
border: 1px solid rgba(248, 113, 113, 0.20);
border-radius: 0;                          /* full-width banner, no radius */
backdrop-filter: blur(8px);
-webkit-backdrop-filter: blur(8px);
color: rgba(248, 113, 113, 0.90);
```

---

### 3.13 Confidence Badge

**Current**:
```css
background: var(--dt-confidence-bg);       /* rgba(123,94,167,0.12) */
border: 1px solid var(--dt-confidence-border);
color: var(--v3-iris-bright);
```

**Target**:
```css
background: rgba(139, 111, 212, 0.10);
border: 1px solid rgba(139, 111, 212, 0.22);
color: rgba(139, 111, 212, 0.90);
border-radius: 6px;
backdrop-filter: blur(8px);
-webkit-backdrop-filter: blur(8px);
```

---

### 3.14 Citation / Footnote Buttons

**Current**:
```css
/* resolvable */
color: var(--dt-citation-resolvable-color);
background: var(--dt-citation-resolvable-tint);
border: 0.5px solid var(--dt-citation-resolvable-border);
```

**Target** -- keep iris accent, reduce intensity:
```css
/* resolvable */
color: rgba(139, 111, 212, 0.85);
background: rgba(139, 111, 212, 0.08);
border: 1px solid rgba(139, 111, 212, 0.18);
border-radius: 4px;

/* hover */
background: rgba(139, 111, 212, 0.16);
border-color: rgba(139, 111, 212, 0.30);

/* unresolvable */
color: rgba(255, 255, 255, 0.25);
background: rgba(50, 50, 50, 0.15);
border: 1px solid rgba(255, 255, 255, 0.06);
cursor: not-allowed;
```

---

### 3.15 Code Blocks

**Current**:
```css
background: var(--dt-code-bg);             /* rgba(123,94,167,0.10) */
border: 1px solid var(--dt-code-border);
```

**Target**:
```css
background: rgba(19, 19, 19, 0.64);
border: 1px solid rgba(222, 222, 222, 0.10);
border-radius: 8px;
```

---

### 3.16 Scrollbar Styling

Add custom scrollbar for the glassmorphism panels:
```css
.design-v3.dark ::-webkit-scrollbar {
  width: 6px;
}
.design-v3.dark ::-webkit-scrollbar-track {
  background: transparent;
}
.design-v3.dark ::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.10);
  border-radius: 3px;
}
.design-v3.dark ::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.18);
}
```

---

## 4. Typography

No font changes. Only color adjustments.

**Current V3 dark text**:
```css
--v3-text-primary:    rgba(255, 255, 255, 0.95);
--v3-text-secondary:  rgba(255, 255, 255, 0.65);
```

**Target** -- use oklch for perceptual uniformity (matching reference):
```css
--v3-text-primary:    oklch(0.87 0 0 / 0.90);
--v3-text-secondary:  oklch(0.87 0 0 / 0.60);
--v3-text-tertiary:   oklch(0.87 0 0 / 0.40);
--v3-text-quaternary: oklch(0.87 0 0 / 0.22);
```

**Prose overrides** (markdown answer text): Use `--gm-text-primary` for paragraph text. Links remain iris-colored (`#8B6FD4`) but at reduced opacity (0.80).

---

## 5. Animations

### 5.1 Remove or Heavily Mute Aurora

```css
.design-v3.dark.glassmorphism .aurora-bg::before,
.design-v3.dark.glassmorphism .aurora-bg-static::before {
  opacity: 0.06;
  /* OR */
  display: none;
}
```

### 5.2 Remove Floating Orbs

The reference has no orbs. Pure black with glass floating on top.

```css
.design-v3.dark.glassmorphism .v3-orb {
  display: none;
}
```

### 5.3 Panel Entrance Animation

Keep `glass-in` keyframes but adjust:
```css
@keyframes glass-in {
  from {
    opacity: 0;
    transform: translateY(6px) scale(0.995) translateZ(0);
    backdrop-filter: blur(0);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1) translateZ(0);
    backdrop-filter: blur(10px);
  }
}
```

### 5.4 Hover Glass Reflection (New)

Subtle cursor-following highlight on structural panels (optional polish):

```css
.gm-glass-structural {
  position: relative;
}
.gm-glass-structural::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: radial-gradient(
    400px circle at var(--mouse-x, 50%) var(--mouse-y, 50%),
    rgba(255, 255, 255, 0.03) 0%,
    transparent 70%
  );
  pointer-events: none;
  z-index: 1;
  opacity: 0;
  transition: opacity 0.3s ease;
}
.gm-glass-structural:hover::after {
  opacity: 1;
}
```

Requires a small JS handler to set `--mouse-x` and `--mouse-y` CSS vars on mousemove.

---

## 6. Implementation Strategy

### 6.1 CSS Variable Layer

Add a new scope in `globals.css`:

```css
/* ============================================================
   GLASSMORPHISM MODE -- pure dark glass on black
   Activated by adding `.glassmorphism` class alongside .design-v3.dark
   ============================================================ */
.design-v3.dark.glassmorphism {
  --background: #000000;

  /* Glass tiers */
  --gm-structural-bg: rgba(9, 9, 9, 0.73);
  --gm-structural-blur: blur(10px);
  --gm-structural-border: rgba(222, 222, 222, 0.22);
  --gm-structural-shadow:
    0 10px 14px 4px rgba(0, 0, 0, 0.23),
    0 10px 19px 1px rgba(0, 0, 0, 0.27),
    inset -2px 0 10px 10px rgba(67, 67, 67, 0.15),
    inset 0 0 2px 1px rgba(222, 222, 222, 0.22);

  --gm-interactive-bg: rgba(19, 19, 19, 0.64);
  --gm-interactive-blur: blur(15px);
  --gm-interactive-border: rgba(222, 222, 222, 0.14);
  --gm-interactive-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 4px 16px rgba(0, 0, 0, 0.30);

  --gm-minimal-bg: rgba(50, 50, 50, 0.21);
  --gm-minimal-border: rgba(255, 255, 255, 0.06);

  /* Override dt-* tokens to route through glassmorphism values */
  --dt-glass-bg: var(--gm-structural-bg);
  --dt-glass-bg-subtle: rgba(9, 9, 9, 0.40);
  --dt-glass-bg-hover: rgba(30, 30, 30, 0.50);
  --dt-glass-border: var(--gm-structural-border);
  --dt-glass-border-subtle: rgba(222, 222, 222, 0.10);
  --dt-glass-blur: var(--gm-structural-blur);
  --dt-glass-blur-light: blur(8px);
  --dt-glass-inner-glow: inset 0 0 2px 1px rgba(222, 222, 222, 0.22);
  --dt-glass-shadow: var(--gm-structural-shadow);

  --dt-text-primary: oklch(0.87 0 0 / 0.90);
  --dt-text-secondary: oklch(0.87 0 0 / 0.60);
  --dt-text-tertiary: oklch(0.87 0 0 / 0.40);
  --dt-text-quaternary: oklch(0.87 0 0 / 0.22);

  --dt-answer-bg: rgba(14, 14, 14, 0.55);
  --dt-answer-border: rgba(222, 222, 222, 0.10);

  --dt-accent-tint: rgba(139, 111, 212, 0.10);
  --dt-accent-tint-subtle: rgba(139, 111, 212, 0.06);
  --dt-accent-border-color: rgba(139, 111, 212, 0.20);
  --dt-accent-glow: rgba(139, 111, 212, 0.12);
  --dt-accent-color: #8B6FD4;
  --dt-active-item-bg: rgba(139, 111, 212, 0.10);

  --dt-button-bg: var(--gm-interactive-bg);
  --dt-button-bg-hover: rgba(30, 30, 30, 0.70);
  --dt-button-border-color: var(--gm-interactive-border);
  --dt-pill-bg: var(--gm-minimal-bg);
  --dt-pill-bg-subtle: rgba(30, 30, 30, 0.30);
  --dt-pill-bg-hover: rgba(50, 50, 50, 0.35);
  --dt-pill-border-color: var(--gm-minimal-border);

  --dt-confidence-bg: rgba(19, 19, 19, 0.64);
  --dt-confidence-border: rgba(139, 111, 212, 0.18);
  --dt-confidence-text: oklch(0.87 0 0 / 0.90);

  --dt-chip-bg: var(--gm-interactive-bg);
  --dt-chip-border: var(--gm-interactive-border);
  --dt-chip-hover-bg: rgba(30, 30, 30, 0.70);
  --dt-chip-hover-border: rgba(222, 222, 222, 0.20);

  --dt-code-bg: var(--gm-interactive-bg);
  --dt-code-border: var(--gm-interactive-border);

  --dt-error-bg: rgba(248, 113, 113, 0.06);
  --dt-error-bg-subtle: rgba(248, 113, 113, 0.06);
  --dt-error-bg-hover: rgba(248, 113, 113, 0.12);
  --dt-error-border-color: rgba(248, 113, 113, 0.18);
  --dt-error-border-subtle: rgba(248, 113, 113, 0.14);
  --dt-error-text: rgba(248, 113, 113, 0.90);

  --dt-overlay-bg: rgba(0, 0, 0, 0.88);
  --dt-panel-overlay-bg: rgba(0, 0, 0, 0.90);
  --dt-panel-border-color: rgba(222, 222, 222, 0.22);
  --dt-panel-shadow: 0 -12px 48px rgba(0, 0, 0, 0.60),
                     inset 0 1px 0 rgba(255, 255, 255, 0.06);

  --dt-content-card-bg: rgba(9, 9, 9, 0.73);
  --dt-content-card-border: var(--gm-structural-border);
  --dt-content-card-shadow: var(--gm-structural-shadow);

  --dt-divider-bg: rgba(222, 222, 222, 0.08);
  --dt-divider-border: rgba(222, 222, 222, 0.10);
  --dt-progress-track-bg: rgba(139, 111, 212, 0.12);

  --dt-citation-resolvable-color: rgba(139, 111, 212, 0.85);
  --dt-citation-resolvable-tint: rgba(139, 111, 212, 0.08);
  --dt-citation-resolvable-border: rgba(139, 111, 212, 0.18);
  --dt-citation-default-tint: rgba(50, 50, 50, 0.15);
  --dt-citation-default-border: rgba(255, 255, 255, 0.06);

  --dt-vote-text: oklch(0.87 0 0 / 0.40);
  --dt-text-secondary-accent: oklch(0.87 0 0 / 0.65);

  /* V3 glass overrides to route through GM tiers */
  --v3-glass-elevated-bg: var(--gm-structural-bg);
  --v3-glass-elevated-blur: var(--gm-structural-blur);
  --v3-glass-elevated-border: var(--gm-structural-border);
  --v3-glass-elevated-shadow: var(--gm-structural-shadow);

  --v3-glass-surface-bg: var(--gm-interactive-bg);
  --v3-glass-surface-bg-hover: rgba(30, 30, 30, 0.70);
  --v3-glass-surface-blur: var(--gm-interactive-blur);
  --v3-glass-surface-border: var(--gm-interactive-border);
  --v3-glass-surface-shadow: var(--gm-interactive-shadow);

  --v3-glass-floating-bg: rgba(14, 14, 14, 0.82);
  --v3-glass-floating-border: rgba(222, 222, 222, 0.25);
  --v3-glass-floating-blur: blur(20px);
  --v3-glass-floating-shadow:
    0 24px 80px rgba(0, 0, 0, 0.70),
    inset 0 0 2px 1px rgba(222, 222, 222, 0.18);
}
```

### 6.2 `chat-input.tsx` Changes

The `ChatInput` component uses hardcoded color values instead of CSS vars. For glassmorphism mode, update the conditionals:

```typescript
// chat-input.tsx -- replace the hardcoded color blocks
// Option A: Check for glassmorphism mode via a context/prop
// Option B: Use CSS vars that the .glassmorphism scope already overrides

// The cleanest approach: migrate chat-input.tsx to use --dt-* vars
// instead of hardcoded rgba values. Then the glassmorphism CSS scope
// handles everything automatically.
```

Specific changes to `chat-input.tsx`:
1. Replace `sendBg` hardcoded gradient with `var(--dt-accent-solid)` / `var(--dt-glass-bg-subtle)`
2. Replace `borderColor` hardcoded values with `var(--dt-glass-border)` and `var(--dt-accent-border-color)`
3. Replace `glowShadow` with `var(--dt-glass-inner-glow)` and `var(--dt-accent-glow)`
4. Replace background hardcoded rgba with `var(--dt-button-bg)` / `var(--dt-button-bg-hover)`
5. Replace caret-color with `var(--dt-accent-color)`

### 6.3 Activation

Add `glassmorphism` to the HTML class list when the user selects this mode. This could be:
- A toggle in settings
- A separate design version "v3gm"
- Auto-applied when V3 dark mode is active

**Simplest**: always apply `.glassmorphism` when `.design-v3.dark` is active. All the CSS vars above are scoped to `.design-v3.dark.glassmorphism` so they only activate in that combination.

---

## 7. Summary of Glass Properties by Component

| Component | BG | Blur | Border | Shadow | Radius |
|---|---|---|---|---|---|
| Chat container | `rgba(9,9,9,0.73)` | 10px | `#dedede38` | structural 4-layer | 16px |
| History panel | `rgba(9,9,9,0.73)` | 10px | `#dedede38` | structural 4-layer | 16px |
| Source panel | `rgba(9,9,9,0.73)` | 10px | `#dedede38` | structural 4-layer | 16px |
| Chat header | `rgba(9,9,9,0.50)` | 8px | `#dedede14` bottom | none | 0 |
| Input area | `rgba(19,19,19,0.64)` | 15px | `#dedede24` | interactive 2-layer | 16px |
| User message | `rgba(19,19,19,0.64)` | 15px | iris 18% | interactive 2-layer | 16/16/4/16 |
| AI answer card | `rgba(14,14,14,0.55)` | 12px | `#dedede1a` | light 2-layer | 16px |
| Source chips | `rgba(19,19,19,0.64)` | 15px | `#dedede1f` | interactive 2-layer | 8px |
| Jurisdiction pills | `rgba(50,50,50,0.21)` | 4px | `#ffffff0f` | none | 8px |
| Follow-up buttons | `rgba(30,30,30,0.50)` | 8px | `#dedede1f` | none | pill |
| History item hover | `rgba(50,50,50,0.21)` | 4px | `#ffffff0f` | none | 8px |

---

## 8. What NOT to Change

- **Light mode**: Entire glassmorphism scope is `.design-v3.dark.glassmorphism` only
- **Fonts**: No font changes
- **Layout structure**: No changes to flex layout, panel widths, spacing grid
- **V2 theme**: Completely untouched
- **V1 theme**: Completely untouched
- **Component logic**: No business logic changes
- **Accessibility**: All WCAG focus rings remain, `prefers-reduced-motion` still respected
- **Mobile degradation**: Keep reduced blur on mobile (adjust thresholds to new values)

---

## 9. Mobile Degradation Overrides

```css
@media (max-width: 768px) {
  .design-v3.dark.glassmorphism .gm-glass-structural,
  .design-v3.dark.glassmorphism .v3-glass-elevated {
    backdrop-filter: blur(6px);
    -webkit-backdrop-filter: blur(6px);
  }

  .design-v3.dark.glassmorphism .gm-glass-interactive {
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
  }
}
```

---

## 10. Reference Comparison Table

| Property | Reference (ChatGPT DG) | Current V3 Dark | Target |
|---|---|---|---|
| Page BG | `#000` | `#07091A` | `#000` |
| Panel BG | `rgb(9 9 9 / 73%)` | `rgba(255,255,255,0.09)` | `rgba(9,9,9,0.73)` |
| Panel blur | `blur(10px)` | `blur(40px) saturate(200%)` | `blur(10px)` |
| Input BG | `rgb(19 19 19 / 64%)` | `rgba(255,255,255,0.08)` | `rgba(19,19,19,0.64)` |
| Input blur | `blur(15px)` | `blur(32px) saturate(160%)` | `blur(15px)` |
| Text | `oklch(0.87 0 0 / 0.9)` | `rgba(255,255,255,0.95)` | `oklch(0.87 0 0 / 0.90)` |
| Border trick | `inset ... #dedede38` | `inset 0 1px 0 rgba(255,255,255,0.10)` | `inset 0 0 2px 1px #dedede38` |
| Header | gradient fade to black | solid `rgba(255,255,255,0.02)` | gradient or semi-transparent |
| Sidebar bg | `rgb(9 9 9 / 73%)` | `rgba(255,255,255,0.09)` | `rgba(9,9,9,0.73)` |
| Saturate filter | none | `saturate(200%)` | none |
| Brightness filter | none | `brightness(106%)` | none |
| Aurora | none | animated/static gradient | none or 6% opacity |
| Orbs | none | 3 floating orbs | none |
