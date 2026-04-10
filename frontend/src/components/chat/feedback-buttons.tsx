"use client";

// FeedbackButtons — copy + thumbs + comment form, extracted from chat-message.tsx.
// Strict (dark) mode: spec layout (copy | separator | thumbs | "Helpful?").
// Light mode: thumbs-only layout matching existing chat-message design.

import { useState, useRef, useCallback } from "react";
import { Copy, Check, ThumbsUp, ThumbsDown } from "lucide-react";
import { motion, AnimatePresence } from "motion/react";
import { FONT, TYPE_SCALE, SPACE, RADIUS } from "@/lib/tokens";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface FeedbackState {
    rating: "positive" | "negative";
    comment?: string;
}

interface FeedbackButtonsProps {
    messageId?: string;
    traceId?: string | null;
    conversationId?: string | null;
    /** Answer text — used by copy button in strict mode */
    content?: string | null;
    feedback?: FeedbackState | null;
    onFeedback?: (messageId: string, rating: "positive" | "negative", comment?: string) => void;
    isStrict?: boolean;
}

// ─── Strict button (20×20, gold glass hover) ──────────────────────────────────

function StrictButton({
    onClick,
    disabled,
    active,
    children,
    "aria-label": ariaLabel,
    title,
}: {
    onClick?: () => void;
    disabled?: boolean;
    active?: boolean;
    children: React.ReactNode;
    "aria-label"?: string;
    title?: string;
}) {
    const [hovered, setHovered] = useState(false);
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            aria-label={ariaLabel}
            title={title}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                width: 20, height: 20, borderRadius: 5, padding: 0,
                border: `1px solid ${active ? "var(--strict-gold-border-active)" : hovered ? "var(--strict-gold-border)" : "transparent"}`,
                background: active ? "var(--strict-gold-badge-bg)" : hovered ? "var(--strict-glass-bg)" : "transparent",
                color: active ? "var(--strict-gold-text)" : hovered ? "var(--strict-text-secondary)" : "var(--strict-text-dim)",
                cursor: disabled && !active ? "not-allowed" : "pointer",
                transition: "all 0.15s",
                opacity: disabled && !active ? 0.4 : 1,
            }}
        >
            {children}
        </button>
    );
}

// ─── FeedbackButtons ──────────────────────────────────────────────────────────

export function FeedbackButtons({
    messageId,
    traceId,
    conversationId,
    content,
    feedback,
    onFeedback,
    isStrict = false,
}: FeedbackButtonsProps) {
    const [copied, setCopied] = useState(false);
    const [commentOpen, setCommentOpen] = useState(false);
    const [commentText, setCommentText] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [feedbackError, setFeedbackError] = useState<string | null>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    const postFeedback = useCallback(async (
        rating: "positive" | "negative",
        comment?: string,
        keepPanelOpen = false,
    ) => {
        if (!messageId || !traceId || !conversationId) return;
        const API = process.env.NEXT_PUBLIC_SSE_URL ?? "";
        setSubmitting(true);
        setFeedbackError(null);
        try {
            const res = await fetch(`${API}/api/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest" },
                credentials: "include",
                body: JSON.stringify({
                    trace_id: traceId, message_id: messageId,
                    conversation_id: conversationId, rating,
                    ...(comment ? { comment } : {}),
                }),
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            onFeedback?.(messageId, rating, comment);
            if (!keepPanelOpen) { setCommentOpen(false); setCommentText(""); }
        } catch {
            setFeedbackError("Couldn't save feedback. Try again.");
        } finally {
            setSubmitting(false);
        }
    }, [messageId, traceId, conversationId, onFeedback]);

    const handleCopy = useCallback(() => {
        if (!content) return;
        navigator.clipboard.writeText(content).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        });
    }, [content]);

    const handleThumbsUp = useCallback(() => {
        if (feedback?.rating === "positive") return;
        postFeedback("positive");
    }, [feedback, postFeedback]);

    const handleThumbsDown = useCallback(() => {
        if (feedback?.rating === "negative") return;
        postFeedback("negative", undefined, true);
        setCommentOpen(true);
        setTimeout(() => textareaRef.current?.focus(), 50);
    }, [feedback, postFeedback]);

    if (!traceId) return null;

    // ── Strict / dark mode ────────────────────────────────────────────────────
    if (isStrict) {
        return (
            <div>
                <div style={{ display: "flex", alignItems: "center", gap: 6, borderTop: "1px solid var(--strict-glass-border)", paddingTop: 8, marginTop: 8 }}>
                    <StrictButton onClick={handleCopy} active={copied} aria-label="Copy answer" title="Copy to clipboard">
                        {copied ? <Check size={10} /> : <Copy size={10} />}
                    </StrictButton>
                    <div style={{ width: 1, height: 12, background: "var(--strict-gold-border)" }} />
                    <StrictButton onClick={handleThumbsUp} disabled={submitting || feedback?.rating === "positive"} active={feedback?.rating === "positive"} aria-label="Helpful">
                        <ThumbsUp size={10} fill={feedback?.rating === "positive" ? "currentColor" : "none"} />
                    </StrictButton>
                    <StrictButton onClick={handleThumbsDown} disabled={submitting || feedback?.rating === "negative"} active={feedback?.rating === "negative"} aria-label="Not helpful">
                        <ThumbsDown size={10} fill={feedback?.rating === "negative" ? "currentColor" : "none"} />
                    </StrictButton>
                    <span style={{ marginLeft: "auto", font: "8.5px/1 system-ui", color: "var(--strict-text-dim)", letterSpacing: "0.02em" }}>Helpful?</span>
                </div>

                {!commentOpen && feedbackError && (
                    <span style={{ display: "block", marginTop: 4, font: "8.5px/1 system-ui", color: "var(--dt-error-text)" }}>{feedbackError}</span>
                )}
                {feedback?.rating === "negative" && feedback.comment && !commentOpen && (
                    <p style={{ margin: "4px 0 0", font: "8.5px/1.4 system-ui", color: "var(--strict-text-secondary)", fontStyle: "italic", maxWidth: "40ch", wordBreak: "break-word" }}>
                        {feedback.comment}
                    </p>
                )}

                <AnimatePresence>
                    {commentOpen && (
                        <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }} style={{ overflow: "hidden" }}>
                            <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                                <textarea
                                    ref={textareaRef}
                                    value={commentText}
                                    onChange={e => setCommentText(e.target.value)}
                                    maxLength={2000}
                                    rows={3}
                                    placeholder="What could be improved? (optional)"
                                    style={{ width: "100%", resize: "none", font: "10px/1.5 system-ui", padding: "7px 10px", borderRadius: 6, border: "1px solid var(--strict-gold-border)", background: "var(--strict-glass-bg)", color: "var(--strict-text-body)", outline: "none", boxSizing: "border-box", caretColor: "var(--strict-gold-base)" }}
                                />
                                <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                    <button onClick={() => postFeedback("negative", commentText.trim() || undefined)} disabled={submitting} style={{ font: "9px/1 system-ui", fontWeight: 600, padding: "5px 10px", borderRadius: 5, border: "1px solid var(--strict-gold-border-active)", background: "var(--strict-gold-badge-bg)", color: "var(--strict-gold-text)", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.6 : 1, transition: "all 0.15s" }}>
                                        {submitting ? "Sending…" : "Submit"}
                                    </button>
                                    <button onClick={() => { setCommentOpen(false); setCommentText(""); setFeedbackError(null); }} disabled={submitting} style={{ font: "9px/1 system-ui", padding: "5px 8px", borderRadius: 5, border: "none", background: "transparent", color: "var(--strict-text-dim)", cursor: "pointer" }}>
                                        Cancel
                                    </button>
                                    {feedbackError && <span style={{ font: "9px/1 system-ui", color: "var(--dt-error-text)" }}>{feedbackError}</span>}
                                </div>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        );
    }

    // ── Light mode (existing design) ──────────────────────────────────────────
    return (
        <div style={{ marginTop: SPACE[2] }}>
            <div style={{ display: "flex", alignItems: "center", gap: SPACE[2] }}>
                {(["positive", "negative"] as const).map((rating) => {
                    const isUp = rating === "positive";
                    const isActive = feedback?.rating === rating;
                    const isOpposite = feedback?.rating === (isUp ? "negative" : "positive");
                    return (
                        <button
                            key={rating}
                            onClick={isUp ? handleThumbsUp : handleThumbsDown}
                            disabled={submitting || isActive}
                            aria-label={isUp ? "Helpful" : "Not helpful"}
                            style={{
                                display: "flex", alignItems: "center", justifyContent: "center",
                                width: 28, height: 28, borderRadius: RADIUS.md, padding: 0,
                                border: `1px solid ${isActive ? "var(--dt-accent-highlight)" : "var(--dt-divider-border)"}`,
                                background: isActive ? "var(--dt-citation-resolvable-tint)" : "transparent",
                                color: isActive ? "var(--dt-accent-color)" : isOpposite ? "var(--dt-text-quaternary)" : "var(--dt-text-tertiary)",
                                cursor: isActive ? "default" : "pointer",
                                transition: "all 0.15s",
                            }}
                        >
                            {isUp
                                ? <ThumbsUp size={13} fill={isActive ? "currentColor" : "none"} />
                                : <ThumbsDown size={13} fill={isActive ? "currentColor" : "none"} />
                            }
                        </button>
                    );
                })}
            </div>

            {!commentOpen && feedbackError && (
                <span style={{ display: "block", marginTop: SPACE[1], fontSize: TYPE_SCALE.xs, color: "var(--dt-error-text)", fontFamily: FONT.sans }}>{feedbackError}</span>
            )}
            {feedback?.rating === "negative" && feedback.comment && !commentOpen && (
                <p style={{ margin: `${SPACE[1]}px 0 0`, fontSize: TYPE_SCALE.xs, color: "var(--dt-text-tertiary)", fontFamily: FONT.sans, lineHeight: 1.5, fontStyle: "italic", maxWidth: "40ch", wordBreak: "break-word" }}>
                    {feedback.comment}
                </p>
            )}

            <AnimatePresence>
                {commentOpen && (
                    <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2, ease: [0.32, 0.72, 0, 1] }} style={{ overflow: "hidden" }}>
                        <div style={{ marginTop: SPACE[2], display: "flex", flexDirection: "column", gap: SPACE[2] }}>
                            <textarea
                                ref={textareaRef}
                                value={commentText}
                                onChange={e => setCommentText(e.target.value)}
                                maxLength={2000}
                                rows={3}
                                placeholder="What could be improved? (optional)"
                                style={{ width: "100%", resize: "none", fontFamily: FONT.sans, fontSize: TYPE_SCALE.xs, padding: `${SPACE[2]}px ${SPACE[3]}px`, borderRadius: RADIUS.md, border: "1px solid var(--dt-divider-border)", background: "var(--dt-glass-bg-subtle)", color: "var(--dt-text-strong)", outline: "none", lineHeight: 1.5, boxSizing: "border-box" }}
                            />
                            <div style={{ display: "flex", alignItems: "center", gap: SPACE[2] }}>
                                <button onClick={() => postFeedback("negative", commentText.trim() || undefined)} disabled={submitting} style={{ fontFamily: FONT.sans, fontSize: TYPE_SCALE.xs, fontWeight: 600, padding: `${SPACE[1]}px ${SPACE[3]}px`, borderRadius: RADIUS.md, border: "1px solid var(--dt-accent-border-strong)", background: "var(--dt-accent-tint-subtle)", color: "var(--dt-accent-color)", cursor: submitting ? "not-allowed" : "pointer", opacity: submitting ? 0.6 : 1, transition: "all 0.15s" }}>
                                    {submitting ? "Sending…" : "Submit"}
                                </button>
                                <button onClick={() => { setCommentOpen(false); setCommentText(""); setFeedbackError(null); }} disabled={submitting} style={{ fontFamily: FONT.sans, fontSize: TYPE_SCALE.xs, padding: `${SPACE[1]}px ${SPACE[2]}px`, borderRadius: RADIUS.md, border: "none", background: "transparent", color: "var(--dt-text-tertiary)", cursor: "pointer" }}>
                                    Cancel
                                </button>
                                {feedbackError && <span style={{ fontSize: TYPE_SCALE.xs, color: "var(--dt-error-text)", fontFamily: FONT.sans }}>{feedbackError}</span>}
                            </div>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    );
}
