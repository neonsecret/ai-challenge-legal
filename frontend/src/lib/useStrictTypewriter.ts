import { useEffect, useRef, useState, startTransition } from "react";
import { STRICT_TYPEWRITER } from "@/lib/strict-tokens";

/**
 * Build the next "chunk" to append from position `pos` in `src`.
 * - If the char at `pos` is `<`, scans to closing `>` and returns the full tag.
 * - `\n` becomes `<br>`.
 * - Otherwise returns the single character.
 */
function nextChunk(src: string, pos: number): { chunk: string; next: number } {
  if (pos >= src.length) return { chunk: "", next: pos };

  const ch = src[pos];

  if (ch === "<") {
    const closeIdx = src.indexOf(">", pos);
    if (closeIdx === -1) return { chunk: ch, next: pos + 1 };
    const tag = src.slice(pos, closeIdx + 1);
    const next = closeIdx + 1;
    if (tag.startsWith("</") && next < src.length && src[next] !== "<") {
      const extra = src[next] === "\n" ? "<br>" : src[next];
      return { chunk: tag + extra, next: next + 1 };
    }
    return { chunk: tag, next };
  }

  if (ch === "\n") return { chunk: "<br>", next: pos + 1 };

  return { chunk: ch, next: pos + 1 };
}

/**
 * rAF-based typewriter hook for Strict design preview.
 * Advances multiple chars per frame to match the target ms-per-char rate
 * without scheduling hundreds of setTimeout callbacks.
 *
 * Instead of using `setTick` to force React re-renders at 60fps, this hook
 * mutates the DOM directly via `answerRef`, emitting only a single state
 * update when typing is complete.
 */
export function useStrictTypewriter(
  text: string,
  active: boolean
): { answerRef: React.RefObject<HTMLDivElement | null>; typingDone: boolean } {
  const answerRef = useRef<HTMLDivElement | null>(null);
  const bufferRef = useRef("");
  const posRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const [typingDone, setTypingDone] = useState(false);

  useEffect(() => {
    if (!active) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }

    bufferRef.current = "";
    posRef.current = 0;
    startTransition(() => setTypingDone(false));
    if (answerRef.current) answerRef.current.innerHTML = "";

    const tick = () => {
      // Advance enough chars so that at 60fps we match STRICT_TYPEWRITER.preview ms/char
      const charsPerFrame = Math.max(1, Math.ceil(16 / STRICT_TYPEWRITER.preview));
      for (let i = 0; i < charsPerFrame && posRef.current < text.length; i++) {
        const { chunk, next } = nextChunk(text, posRef.current);
        bufferRef.current += chunk;
        posRef.current = next;
      }
      // Imperatively update DOM — no React re-render
      if (answerRef.current) answerRef.current.innerHTML = bufferRef.current;
      if (posRef.current < text.length) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setTypingDone(true);
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [active, text]);

  return { answerRef, typingDone };
}
