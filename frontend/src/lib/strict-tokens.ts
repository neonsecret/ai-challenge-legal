/** Strict design animation and timing constants */

/** Typewriter speeds (ms per character) */
export const STRICT_TYPEWRITER = {
  /** Chat preview on landing page */
  preview: 8,
  /** How It Works typing demo */
  hiw: 35,
} as const;

/** How It Works auto-advance */
export const STRICT_HIW = {
  /** Duration each step is active (ms) */
  stepDuration: 5000,
  /** Pause after user clicks a step before resuming auto (ms) */
  userPause: 8000,
  /** Delay between scanning items appearing (ms) */
  scanStagger: 800,
  /** Delay before result highlight slides in (ms) */
  resultHighlightDelay: 400,
  /** Duration of scan fill animation (ms) */
  scanFillDuration: 1500,
  /** Base delay for step item entrance animation (s) */
  stepBaseDelay: 0.1,
  /** Stagger between each step item (s) */
  stepStagger: 0.08,
} as const;

/** Preview section delays */
export const STRICT_PREVIEW = {
  /** Delay before question fades in (ms) */
  questionDelay: 300,
  /** Delay before typewriter starts (ms) */
  typewriterDelay: 900,
} as const;

/** Source margin reveal */
export const STRICT_SOURCES = {
  /** Stagger between each source tile appearing (ms) */
  stagger: 250,
} as const;

/** Mesh blob animation */
export const STRICT_MESH = {
  /** Full drift cycle duration (s) */
  driftDuration: 8,
} as const;

/** 100% citation accuracy counter */
export const STRICT_COUNTER = {
  /** Increment per tick */
  step: 2,
  /** Ms between ticks */
  interval: 20,
  /** Delay before counter starts (ms) */
  delay: 1200,
} as const;

/** Hero stat stagger delay (ms between each stat row) */
export const STRICT_HERO_STAGGER = 150;

/** Badge pulse cycle (seconds) */
export const STRICT_BADGE_PULSE = 3;

/** Gold glow brightness pulse cycle (seconds) */
export const STRICT_GLOW_PULSE = 2.5;
