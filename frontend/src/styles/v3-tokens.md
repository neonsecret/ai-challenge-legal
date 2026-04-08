# V3 "Luminous" Design Token Specification

**Version:** 3.0  
**Theme Name:** Luminous  
**CSS class trigger:** `.design-v3` on `<html>`  
**Branch:** `feature/NEO-612-v3-luminous-design`

---

## Design Research Summary

Studied 7 reference designs to inform this spec:

| Source | Key Takeaway for Luminous |
|---|---|
| **Linear** | Spring-physics micro-interactions; every hover/click has a physical feel. Tight indigo-violet color story with depth through layering, not decoration. Navigation transitions use shared-element morph. |
| **Apple VisionOS** | Glass is not a trick — it is a material with real properties: thickness, translucency, edge specular. Panels live at explicit Z-depths. Shadows encode physical height, not mood. The "Ultra Thin Material" and "Thick Material" maps to our surface/elevated/floating tier model. |
| **Vercel** | Bold display typography at 56–80px creates drama on a mostly-empty canvas. Gradient text (indigo→violet→pink) on white backgrounds is readable and striking. "Geist" variable font weight transitions on hover feel alive. |
| **Stripe** | Mesh gradients done right: 5-6 color stops, animated on a 20–30s loop, subtle. Their iridescent "holographic" card effect (hue-rotate on a diagonal gradient) is achievable with pure CSS + transform. Their "blur-on-scroll" pattern keeps the background interesting without distracting. |
| **Raycast** | Aurora-glow behind glass = depth without fake 3D. Command palette glass: `backdrop-filter: blur(40px) saturate(180%)` + thin specular top-edge (`inset 0 1px 0 rgba(255,255,255,0.12)`) is the canonical formula. Spring config: stiffness 300, damping 30 gives the characteristic "snappy settle". |
| **Craft.do** | Floating cards with `perspective: 1200px` and subtle `rotateX/rotateY` on hover give the impression of picking something up. No WebGL needed. |
| **Resend** | Minimal dark surfaces with precisely placed glows (radial-gradient behind key UI elements) communicate hierarchy through light, not color weight. |

---

## 1. Color Palette

### Philosophy
Luminous uses a **cool violet-blue-teal spectrum** as its primary palette — shifting away from V2's indigo toward a deeper, more spatial "aurora" color story. The palette should feel like deep space lit by bioluminescent light.

### Brand Colors

```css
/* Core palette — the "aurora spectrum" */
--v3-iris:        #7B5EA7;   /* deep violet — primary brand */
--v3-aurora:      #4F8FD4;   /* luminous blue — secondary */
--v3-teal:        #2DD4BF;   /* iridescent teal — accent */
--v3-rose:        #F472B6;   /* aurora pink — highlight */
--v3-gold:        #FCD34D;   /* warm star-gold — attention / active states */

/* Derived interactive states */
--v3-iris-bright: #9D7FCC;   /* iris at 85% luminosity for hover */
--v3-aurora-glow: #60A5FA;   /* aurora at +20% lightness for glows */
```

### Dark Mode Surfaces

```css
/* Dark mode — "deep space" base */
--v3-dark-bg:           #07090F;   /* near-black with cool blue tint */
--v3-dark-surface:      #0D1120;   /* primary surface — cards, panels */
--v3-dark-elevated:     #111827;   /* elevated panels — modals, dropdowns */
--v3-dark-floating:     #161F30;   /* highest z-level — tooltips, popovers */
--v3-dark-overlay:      rgba(7, 9, 15, 0.85);  /* scrim/backdrop */
```

### Light Mode Surfaces

```css
/* Light mode — "frosted daylight" */
--v3-light-bg:          #F0F2F8;   /* cool off-white — barely tinted blue */
--v3-light-surface:     rgba(255, 255, 255, 0.82);  /* card backgrounds */
--v3-light-elevated:    rgba(255, 255, 255, 0.92);  /* modals, dropdowns */
--v3-light-floating:    rgba(255, 255, 255, 0.97);  /* tooltips */
--v3-light-overlay:     rgba(7, 9, 30, 0.40);       /* scrim */
```

### Text Hierarchy

```css
/* Dark mode text */
--v3-text-primary:      rgba(255, 255, 255, 0.94);
--v3-text-secondary:    rgba(255, 255, 255, 0.64);
--v3-text-tertiary:     rgba(255, 255, 255, 0.38);
--v3-text-quaternary:   rgba(255, 255, 255, 0.20);
--v3-text-accent:       #9D7FCC;   /* iris-tinted links / labels */

/* Light mode text */
--v3-text-light-primary:    #0D0F1A;
--v3-text-light-secondary:  rgba(13, 15, 26, 0.64);
--v3-text-light-tertiary:   rgba(13, 15, 26, 0.38);
--v3-text-light-accent:     #5B40A0;   /* darkened iris for contrast */
```

### Semantic Colors

```css
--v3-success:   #34D399;
--v3-warning:   #FBBF24;
--v3-danger:    #F87171;
--v3-info:      #60A5FA;
```

---

## 2. Glass Material System

### Design Principle
Glass in V3 is a **material**, not a filter effect. Each tier has a specific physical analogy:

| Tier | Analogy | Use Case |
|---|---|---|
| `surface` | Thin frosted glass | Cards, panels, sidebars |
| `elevated` | Medium-weight glass | Modals, dropdowns, drawers |
| `floating` | Thick crystal panel | Command palette, tooltips, popovers |
| `overlay` | Frosted room divider | Sheet modals, onboarding |

### Glass Tokens — Dark Mode

```css
/* Surface glass — base layer */
--v3-glass-surface-bg:        rgba(255, 255, 255, 0.04);
--v3-glass-surface-bg-hover:  rgba(255, 255, 255, 0.07);
--v3-glass-surface-border:    rgba(255, 255, 255, 0.08);
--v3-glass-surface-blur:      blur(20px) saturate(140%);
--v3-glass-surface-shadow:    0 4px 16px rgba(0, 0, 0, 0.35),
                               inset 0 1px 0 rgba(255, 255, 255, 0.06);

/* Elevated glass — modal / drawer */
--v3-glass-elevated-bg:       rgba(255, 255, 255, 0.07);
--v3-glass-elevated-bg-hover: rgba(255, 255, 255, 0.10);
--v3-glass-elevated-border:   rgba(255, 255, 255, 0.12);
--v3-glass-elevated-blur:     blur(40px) saturate(160%) brightness(105%);
--v3-glass-elevated-shadow:   0 12px 48px rgba(0, 0, 0, 0.50),
                               0 2px 8px rgba(0, 0, 0, 0.30),
                               inset 0 1px 0 rgba(255, 255, 255, 0.10);

/* Floating glass — command palette, tooltips */
--v3-glass-floating-bg:       rgba(255, 255, 255, 0.10);
--v3-glass-floating-border:   rgba(255, 255, 255, 0.16);
--v3-glass-floating-blur:     blur(60px) saturate(180%) brightness(108%);
--v3-glass-floating-shadow:   0 24px 80px rgba(0, 0, 0, 0.65),
                               0 8px 24px rgba(0, 0, 0, 0.40),
                               inset 0 1px 0 rgba(255, 255, 255, 0.14),
                               inset 0 -1px 0 rgba(0, 0, 0, 0.20);

/* Signature: iris-tinted glass for active/selected states */
--v3-glass-iris-bg:           rgba(123, 94, 167, 0.12);
--v3-glass-iris-border:       rgba(157, 127, 204, 0.25);
--v3-glass-iris-glow:         0 0 24px rgba(123, 94, 167, 0.20);
```

### Glass Tokens — Light Mode

```css
/* Surface */
--v3-glass-surface-bg:        rgba(255, 255, 255, 0.60);
--v3-glass-surface-bg-hover:  rgba(255, 255, 255, 0.72);
--v3-glass-surface-border:    rgba(255, 255, 255, 0.80);
--v3-glass-surface-shadow:    0 2px 12px rgba(7, 9, 30, 0.08),
                               inset 0 1px 0 rgba(255, 255, 255, 0.90);

/* Elevated */
--v3-glass-elevated-bg:       rgba(255, 255, 255, 0.78);
--v3-glass-elevated-border:   rgba(255, 255, 255, 0.90);
--v3-glass-elevated-blur:     blur(40px) saturate(150%);
--v3-glass-elevated-shadow:   0 8px 32px rgba(7, 9, 30, 0.12),
                               inset 0 1px 0 rgba(255, 255, 255, 0.95);

/* Floating */
--v3-glass-floating-bg:       rgba(255, 255, 255, 0.90);
--v3-glass-floating-border:   rgba(255, 255, 255, 0.98);
--v3-glass-floating-blur:     blur(60px) saturate(160%);
--v3-glass-floating-shadow:   0 16px 56px rgba(7, 9, 30, 0.18),
                               inset 0 1px 0 rgba(255, 255, 255, 1);

/* Iris accent glass — light */
--v3-glass-iris-bg:           rgba(91, 64, 160, 0.06);
--v3-glass-iris-border:       rgba(91, 64, 160, 0.20);
```

### Specular Edge Highlight (Signature)
The "light refraction on glass edges" effect uses a 1px top-edge highlight and optional side gradients:

```css
/* Standard glass edge — top specular only */
--v3-specular-top:    inset 0 1px 0 rgba(255, 255, 255, 0.12);

/* Premium glass edge — top bright + bottom shadow edge */
--v3-specular-full:   inset 0 1px 0 rgba(255, 255, 255, 0.18),
                      inset 0 -1px 0 rgba(0, 0, 0, 0.20),
                      inset 1px 0 rgba(255, 255, 255, 0.06),
                      inset -1px 0 rgba(0, 0, 0, 0.08);

/* Iridescent edge — shifts color with hue-rotate animation */
/* Apply with: @keyframes iridescent-edge */
--v3-specular-iris:   inset 0 1px 0 rgba(157, 127, 204, 0.30);
```

---

## 3. Aurora / Mesh Gradient System

### Background Mesh (Primary)
The page background in dark mode is a multi-stop mesh gradient that slowly animates. Implemented as a fixed-position canvas or CSS `@keyframes` on a `::before` pseudo-element.

```css
/* Aurora background definition */
--v3-aurora-stop-1: oklch(0.25 0.20 285);   /* deep iris-violet */
--v3-aurora-stop-2: oklch(0.18 0.16 260);   /* dark aurora-blue */
--v3-aurora-stop-3: oklch(0.22 0.14 230);   /* deep teal */
--v3-aurora-stop-4: oklch(0.15 0.08 300);   /* near-black violet */
--v3-aurora-stop-5: oklch(0.12 0.05 250);   /* deep space */
```

**CSS Implementation:**
```css
.design-v3 .aurora-bg::before {
    content: '';
    position: fixed;
    inset: -50%;
    background: radial-gradient(ellipse 80% 60% at 20% 20%, oklch(0.25 0.20 285 / 0.6) 0%, transparent 60%),
                radial-gradient(ellipse 60% 80% at 80% 30%, oklch(0.18 0.16 260 / 0.4) 0%, transparent 55%),
                radial-gradient(ellipse 70% 50% at 50% 80%, oklch(0.22 0.14 230 / 0.35) 0%, transparent 60%),
                radial-gradient(ellipse 90% 70% at 30% 70%, oklch(0.15 0.08 300 / 0.3) 0%, transparent 65%),
                #07090F;
    animation: aurora-drift 30s ease-in-out infinite alternate;
    filter: blur(60px);
    transform: translateZ(0);
    will-change: transform;
}

@keyframes aurora-drift {
    0%   { transform: translate(0, 0) scale(1.0) rotate(0deg); }
    33%  { transform: translate(2%, 1.5%) scale(1.03) rotate(0.5deg); }
    66%  { transform: translate(-1.5%, 2%) scale(0.98) rotate(-0.3deg); }
    100% { transform: translate(1%, -1%) scale(1.02) rotate(0.2deg); }
}
```

### Cursor-Responsive Ambient Light
A radial glow that follows the cursor, implemented via CSS custom properties set from JavaScript:

```css
.design-v3 .ambient-cursor {
    background: radial-gradient(
        600px circle at var(--cursor-x, 50%) var(--cursor-y, 50%),
        rgba(123, 94, 167, 0.08) 0%,
        transparent 70%
    );
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: 0;
    transition: opacity 0.3s ease;
}
```

**JS driver (minimal, ~12 lines):**
```typescript
// In a top-level component
useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
        document.documentElement.style.setProperty('--cursor-x', `${e.clientX}px`);
        document.documentElement.style.setProperty('--cursor-y', `${e.clientY}px`);
    };
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    return () => window.removeEventListener('mousemove', handleMouseMove);
}, []);
```

### Iridescent Accent Gradient
For CTAs, active pills, and selected states. Shifts through the aurora spectrum:

```css
--v3-iridescent: linear-gradient(
    135deg,
    oklch(0.55 0.25 285) 0%,     /* iris-violet */
    oklch(0.50 0.28 260) 35%,    /* aurora-blue */
    oklch(0.55 0.22 195) 65%,    /* teal */
    oklch(0.62 0.25 285) 100%    /* back to violet */
);

/* Animated iridescent for hover states */
@keyframes iridescent-shift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
/* background-size: 300% 300% + animation: iridescent-shift 5s ease infinite */
```

### Light Mode Aurora
In light mode, the aurora is very subtle — barely visible tint behind frosted glass:

```css
/* Light mode aurora — soft lavender wisps */
.design-v3:not(.dark) .aurora-bg::before {
    background: radial-gradient(ellipse 70% 50% at 20% 20%, oklch(0.85 0.06 285 / 0.35) 0%, transparent 60%),
                radial-gradient(ellipse 60% 70% at 80% 60%, oklch(0.88 0.04 220 / 0.25) 0%, transparent 55%),
                #F0F2F8;
    filter: blur(80px);
}
```

---

## 4. Typography Scale

### Font Stack
```css
--v3-font-display:  "Inter var", "SF Pro Display", -apple-system, system-ui, sans-serif;
--v3-font-body:     "Inter", "SF Pro Text", -apple-system, system-ui, sans-serif;
--v3-font-mono:     "Berkeley Mono", "SF Mono", "Fira Code", monospace;
```
*Inter variable font enables weight transitions on hover — a key V3 micro-interaction.*

### Type Scale

```css
/* Display — hero sections, landing page */
--v3-type-display-2xl:  clamp(48px, 6vw, 80px);   /* line-height: 1.0; letter-spacing: -0.04em; weight: 800 */
--v3-type-display-xl:   clamp(40px, 5vw, 64px);    /* line-height: 1.05; letter-spacing: -0.03em; weight: 700 */
--v3-type-display-lg:   clamp(32px, 4vw, 48px);    /* line-height: 1.1; letter-spacing: -0.02em; weight: 700 */

/* Headings — page titles, section headers */
--v3-type-h1:  28px;   /* weight: 600; letter-spacing: -0.02em; line-height: 1.2 */
--v3-type-h2:  22px;   /* weight: 600; letter-spacing: -0.015em; line-height: 1.3 */
--v3-type-h3:  18px;   /* weight: 600; letter-spacing: -0.01em; line-height: 1.35 */
--v3-type-h4:  15px;   /* weight: 600; letter-spacing: 0; line-height: 1.4 */

/* Body */
--v3-type-body-lg:  16px;  /* weight: 400; line-height: 1.7 */
--v3-type-body:     14px;  /* weight: 400; line-height: 1.65 — primary reading */
--v3-type-body-sm:  13px;  /* weight: 400; line-height: 1.6 */

/* UI / Labels */
--v3-type-label:    12px;  /* weight: 500; letter-spacing: 0.01em; line-height: 1.4 */
--v3-type-caption:  11px;  /* weight: 400; letter-spacing: 0.01em; line-height: 1.35 */
--v3-type-overline: 10px;  /* weight: 600; letter-spacing: 0.08em; uppercase */
```

### Gradient Text (Signature V3 Effect)
For headings and hero copy:

```css
.v3-text-gradient {
    background: var(--v3-iridescent);
    background-size: 200% 100%;
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    animation: iridescent-shift 6s ease infinite;
}

/* Subtler version — fixed gradient, no animation */
.v3-text-aurora {
    background: linear-gradient(135deg, #9D7FCC 0%, #60A5FA 50%, #2DD4BF 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
```

---

## 5. Spacing & Radius Tokens

### Spacing (4px grid — unchanged from V1/V2)
V3 uses the same 4px grid but with **more generous whitespace** — visual breathing room is a core pillar.

```css
/* V3 preferred spacing — more generous than V2 */
--v3-space-xs:    4px;
--v3-space-sm:    8px;
--v3-space-md:    16px;
--v3-space-lg:    24px;
--v3-space-xl:    32px;
--v3-space-2xl:   48px;
--v3-space-3xl:   64px;
--v3-space-4xl:   96px;

/* Section padding (landing page sections) */
--v3-section-pad-y: clamp(64px, 8vw, 120px);
```

### Border Radius
V3 uses **softer, more generous radii** — closer to VisionOS panels than V2's tight corners:

```css
--v3-radius-xs:   4px;
--v3-radius-sm:   8px;
--v3-radius-md:   12px;    /* default card radius */
--v3-radius-lg:   16px;    /* modal, large panel */
--v3-radius-xl:   20px;    /* hero card, feature showcase */
--v3-radius-2xl:  28px;    /* floating overlay, command palette */
--v3-radius-pill: 9999px;  /* pills, badges */
```

---

## 6. Animation & Motion Tokens

### Design Philosophy
**Spring physics everywhere.** CSS transitions are only for color/opacity. Transforms use Framer Motion springs. This creates the characteristic "physical" feel — elements settle like real objects.

### Spring Physics Presets (Framer Motion)

```typescript
// In src/lib/v3-motion.ts
export const V3_SPRING = {
    /** Micro-interactions: hover states, button press */
    micro: { type: "spring", stiffness: 500, damping: 30, mass: 0.8 },
    
    /** Standard transitions: panel open/close, card hover */
    standard: { type: "spring", stiffness: 300, damping: 25, mass: 1.0 },
    
    /** Gentle: page transitions, list stagger */
    gentle: { type: "spring", stiffness: 180, damping: 20, mass: 1.2 },
    
    /** Snappy: command palette, dropdown */
    snappy: { type: "spring", stiffness: 400, damping: 28, mass: 0.9 },
    
    /** Bouncy: success states, notifications */
    bouncy: { type: "spring", stiffness: 350, damping: 18, mass: 0.8 },
} as const;

/** Stagger children — for list items, card grids */
export const V3_STAGGER = {
    fast:     { staggerChildren: 0.04 },
    standard: { staggerChildren: 0.06 },
    slow:     { staggerChildren: 0.10 },
} as const;

/** Entry animation variants */
export const V3_VARIANTS = {
    hidden:  { opacity: 0, y: 12, scale: 0.98 },
    visible: { opacity: 1, y: 0,  scale: 1.0,  transition: V3_SPRING.gentle },
    exit:    { opacity: 0, y: -8, scale: 0.98, transition: { duration: 0.15 } },
} as const;

/** Card hover — 3D lift */
export const V3_CARD_HOVER = {
    whileHover: {
        y: -4,
        scale: 1.005,
        transition: V3_SPRING.micro,
    },
    whileTap: {
        y: 0,
        scale: 0.99,
        transition: V3_SPRING.micro,
    },
} as const;
```

### CSS Transition Tokens (non-transform properties)

```css
--v3-transition-color:    color 0.15s ease, background-color 0.15s ease;
--v3-transition-border:   border-color 0.15s ease, outline-color 0.15s ease;
--v3-transition-opacity:  opacity 0.15s ease;
--v3-transition-shadow:   box-shadow 0.20s ease;
--v3-transition-blur:     backdrop-filter 0.25s ease;

/* Combined for interactive elements */
--v3-transition-interactive: color 0.15s ease,
                              background-color 0.15s ease,
                              border-color 0.15s ease,
                              box-shadow 0.20s ease,
                              opacity 0.15s ease;
```

### Reduced Motion
All animations degrade to instant for `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
    .design-v3 * {
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
    }
    .design-v3 .aurora-bg::before {
        animation: none !important;
    }
}
```

---

## 7. Signature Elements

These are the V3 design signatures that make it recognizably "Vitreon Luminous."

### 7.1 Glass Edge Refraction
A very subtle iridescent shimmer on the top edge of floating panels. Implemented as a `::before` pseudo-element with a very thin animated gradient:

```css
.v3-glass-panel::before {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: inherit;
    padding: 1px;
    background: linear-gradient(
        135deg,
        rgba(157, 127, 204, 0.40) 0%,
        rgba(96, 165, 250, 0.20) 33%,
        rgba(45, 212, 191, 0.25) 66%,
        rgba(157, 127, 204, 0.35) 100%
    );
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: xor;
    mask-composite: exclude;
    pointer-events: none;
    opacity: 0;
    transition: opacity 0.3s ease;
}
.v3-glass-panel:hover::before {
    opacity: 1;
}
```

### 7.2 Depth Grid (Landing Page)
A subtle perspective grid that recedes into the background. Pure CSS, no canvas:

```css
.v3-depth-grid {
    position: absolute;
    inset: 0;
    background-image:
        linear-gradient(rgba(157, 127, 204, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(157, 127, 204, 0.04) 1px, transparent 1px);
    background-size: 48px 48px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 50%, black 0%, transparent 70%);
    transform: perspective(800px) rotateX(25deg) translateY(-20px);
    transform-origin: center bottom;
}
```

### 7.3 Luminous Active Indicator
Active sidebar items get a distinctive iris glow — not a flat color, but a backlit look:

```css
.v3-nav-active {
    background: rgba(123, 94, 167, 0.15);
    border-left: 2px solid #9D7FCC;
    box-shadow: inset 0 0 20px rgba(123, 94, 167, 0.10),
                -2px 0 12px rgba(123, 94, 167, 0.20);
}
```

### 7.4 Source Card Luminous Style
Legal source cards get a distinctive treatment — glass with a colored top-edge that encodes jurisdiction:

```css
.v3-source-card {
    background: var(--v3-glass-surface-bg);
    border: 1px solid var(--v3-glass-surface-border);
    border-top: 1.5px solid transparent; /* colored per jurisdiction */
    backdrop-filter: var(--v3-glass-surface-blur);
    border-radius: var(--v3-radius-md);
}

/* Jurisdiction color encoding (top border) */
.v3-source-card[data-corpus="difc"]  { border-top-color: #60A5FA; }  /* blue */
.v3-source-card[data-corpus="uk"]    { border-top-color: #A78BFA; }  /* violet */
.v3-source-card[data-corpus="czech"] { border-top-color: #34D399; }  /* green */
.v3-source-card[data-corpus="au"]    { border-top-color: #FCD34D; }  /* gold */
```

### 7.5 Aurora Orbs (Background Layer)
Replaced V1/V2 "orbs" with gaussian blobs that contribute to the mesh gradient:

```css
/* Aurora blob layer — rendered behind content at z-index: var(--z-aurora) */
.v3-orb {
    position: fixed;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.35;
    pointer-events: none;
    animation: v3-orb-float var(--orb-duration, 25s) ease-in-out infinite alternate;
    will-change: transform;
}

/* Orb sizes and positions per page */
.v3-orb-1 { width: 600px; height: 600px; background: radial-gradient(circle, oklch(0.40 0.22 285) 0%, transparent 70%); top: -100px; left: -100px; --orb-duration: 28s; }
.v3-orb-2 { width: 500px; height: 500px; background: radial-gradient(circle, oklch(0.35 0.18 220) 0%, transparent 70%); top: 30%; right: -80px; --orb-duration: 22s; }
.v3-orb-3 { width: 400px; height: 400px; background: radial-gradient(circle, oklch(0.38 0.20 195) 0%, transparent 70%); bottom: -80px; left: 30%; --orb-duration: 32s; }

@keyframes v3-orb-float {
    0%   { transform: translate(0, 0); }
    100% { transform: translate(30px, 20px); }
}
```

---

## 8. Component-Level Token Map

Quick reference for component implementation:

| Component | Background | Border | Blur | Shadow |
|---|---|---|---|---|
| Sidebar | `v3-glass-surface-bg` | `v3-glass-surface-border` | `blur(24px) saturate(150%)` | `v3-glass-surface-shadow` |
| Chat card | `v3-glass-elevated-bg` | `v3-glass-elevated-border` | `blur(40px) saturate(160%)` | `v3-glass-elevated-shadow` |
| Source card | `v3-glass-surface-bg` | corpus color (see §7.4) | `blur(16px)` | sm shadow |
| Modal | `v3-glass-elevated-bg` | `v3-glass-elevated-border` | `blur(60px) saturate(170%)` | `v3-glass-elevated-shadow` |
| Command palette | `v3-glass-floating-bg` | `v3-glass-floating-border` | `blur(60px) saturate(180%)` | `v3-glass-floating-shadow` |
| Nav/Header | `v3-dark-surface/60%` | subtle bottom border | `blur(20px) saturate(140%)` | none |
| Tooltip | `v3-glass-floating-bg` | `v3-glass-floating-border` | `blur(24px)` | sm shadow |
| Input | `v3-glass-surface-bg` | `v3-glass-surface-border` focused: `v3-glass-iris-border` | none | iris glow on focus |
| Button (primary) | iridescent gradient | none | none | iris glow |
| Button (secondary) | `v3-glass-surface-bg` | `v3-glass-iris-border` | none | none |
| Active nav item | `v3-glass-iris-bg` | left: `--v3-iris-bright` | none | iris backglow |

---

## 9. Implementation Notes

### CSS Variable Cascade
V3 tokens follow the same pattern as V1/V2 — add `.design-v3` to `<html>`, all tokens cascade:
```
:root → .dark → .design-v3 → .design-v3.dark
```

### Tailwind Extension
Add to `tailwind.config.ts`:
```typescript
theme: {
    extend: {
        colors: {
            'v3-iris':   'var(--v3-iris)',
            'v3-aurora': 'var(--v3-aurora)',
            'v3-teal':   'var(--v3-teal)',
        },
        backdropBlur: {
            'v3-surface':  '20px',
            'v3-elevated': '40px',
            'v3-floating': '60px',
        },
        boxShadow: {
            'v3-glass': 'var(--v3-glass-elevated-shadow)',
            'v3-iris':  '0 0 24px rgba(123, 94, 167, 0.20)',
        },
        borderRadius: {
            'v3-card':    'var(--v3-radius-md)',
            'v3-modal':   'var(--v3-radius-lg)',
            'v3-float':   'var(--v3-radius-2xl)',
        },
        animation: {
            'aurora-drift':      'aurora-drift 30s ease-in-out infinite alternate',
            'iridescent-shift':  'iridescent-shift 6s ease infinite',
            'v3-orb-float':      'v3-orb-float 25s ease-in-out infinite alternate',
        },
    },
}
```

### Performance Constraints
- Aurora background: `will-change: transform` + `transform: translateZ(0)` on the pseudo-element
- Backdrop filters: never on more than 4 visible stacked layers simultaneously (compounding blur causes GPU thrash)
- Orbs: use `filter: blur()` not `backdrop-filter` — much cheaper when not behind content
- Cursor ambient: throttle to `requestAnimationFrame`, debounce the CSS property setter
- `prefers-reduced-motion`: disable all `@keyframes` animations, cursor ambient light off

### Mobile Degradation
On mobile (≤ 768px):
- Reduce backdrop blur: surface: `blur(12px)`, elevated: `blur(20px)`, floating: `blur(32px)`
- Disable aurora drift animation
- Disable cursor ambient light entirely
- Keep glass backgrounds but reduce opacity by 10–15% (mobile GPUs struggle with saturate())
- Orbs: reduce count from 3 to 1, opacity 0.2

---

## 10. V1 Removal Notes

When V1 is removed (NEO-613 cleanup step), the following V1-specific tokens become dead code and should be deleted from `globals.css`:
- All `:root` gold palette vars (`--orb-gold-color`, `--glass-top-line` gold gradient, `--accent: #C9A84C`)
- `--aurora-base: #060C16` — replaced by `--v3-dark-bg: #07090F`
- V1 sidebar warm-amber tones in `.dark` block
- `textarea::placeholder { color: #b29254; }` (V1 warm gold placeholder)

These removals should happen in the FrontendDev V1 cleanup pass, not before V3 implementation is confirmed working.
