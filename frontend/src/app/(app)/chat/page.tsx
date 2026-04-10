"use client"

import {useRef, useEffect, useCallback, useState, Component, type ErrorInfo, type ReactNode} from "react"
import {useRouter} from "next/navigation"
import {motion, AnimatePresence} from "motion/react"
import {V3_SPRING, V3_FADE_UP} from "@/lib/v3-motion"
import {useColorMode} from "@/lib/color-mode"
import {SquarePen, History, Trash2, BookOpen, Globe} from "lucide-react"
import {HistoryPanel} from "@/components/chat/history-panel"
import {ChatInput} from "@/components/chat/chat-input"
import {ChatMessage, type Source} from "@/components/chat/chat-message"
import {StrictLayout} from "@/components/chat/strict-layout"
import {type StrictSourceMarginSource} from "@/components/chat/strict-source-margin"
import {useChatState} from "@/components/chat/chat-state"
import {EmptyState, getPresetQuestions} from "@/components/chat/empty-state"
import {GroundingView} from "@/components/grounding/grounding-view"
import {FakePdf} from "@/components/landing/fake-pdf"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {JURISDICTIONS, jurisdictionToCorpus, type Jurisdiction} from "@/lib/jurisdictions"
import {useIsMobile} from "@/hooks/use-mobile"
import {useDocumentIndex} from "@/components/chat/use-document-index"
import {DocumentIndex} from "@/components/chat/document-index"
import {X} from "lucide-react"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {PREVIEW_SCENARIOS_MAP} from "./scenarios"

interface CorpusEntry {
    name: string
    corpus_id: string
    doc_ids?: string[]   // doc IDs in this collection
    doc_count?: number
    indexed?: boolean
}

// Error boundary to prevent grounding panel crashes from taking down the whole page
class GroundingErrorBoundary extends Component<
    { children: ReactNode; onReset: () => void },
    { error: Error | null; retried: boolean }
> {
    state = {error: null, retried: false}
    static getDerivedStateFromError(error: Error) {
        return {error}
    }
    componentDidCatch(error: Error, info: ErrorInfo) {
        console.error("[Grounding] render error:", error, info)
    }
    private _retryTimer: ReturnType<typeof setTimeout> | null = null

    componentDidUpdate(_: unknown, prevState: {error: Error | null}) {
        // Auto-recover once after 500ms (enough for worker cleanup).
        // Won't loop: retried flag prevents a second reset.
        if (this.state.error && !prevState.error && !this.state.retried) {
            this._retryTimer = setTimeout(() => this.setState({error: null, retried: true}), 500)
        }
    }
    componentWillUnmount() {
        if (this._retryTimer) clearTimeout(this._retryTimer)
    }
    render() {
        if (this.state.error) {
            return null
        }
        return this.props.children
    }
}

const FOLLOWUP_SUGGESTIONS = [
    "Can you cite the specific article?",
    "What are the exceptions to this rule?",
    "How does this compare to English law?",
    "What is the enforcement mechanism?",
]

// Sessions are managed by ChatStateProvider via localStorage

/**
 * Conditional layout wrapper: renders StrictLayout (glass pane + sidebar rail +
 * source margin) in Strict dark mode; otherwise renders children directly.
 */
function StrictChatWrapper({
    active,
    sources,
    onSourceClick,
    sourcesVisible,
    children,
}: {
    active: boolean
    sources: import("@/components/chat/strict-source-margin").StrictSourceMarginSource[]
    onSourceClick?: (id: string) => void
    sourcesVisible: boolean
    children: ReactNode
}) {
    if (active) {
        return (
            <StrictLayout
                sources={sources}
                onSourceClick={onSourceClick}
                sourcesVisible={sourcesVisible}
            >
                {children}
            </StrictLayout>
        )
    }
    return <>{children}</>
}

function makeGlassPanel(isStrict = false) {
    if (isStrict) {
        return {
            background: "var(--strict-glass-bg)",
            backdropFilter: "var(--strict-glass-blur)",
            WebkitBackdropFilter: "var(--strict-glass-blur)",
            border: "1px solid var(--strict-glass-border)",
            borderRadius: "16px",
            boxShadow: "var(--strict-glass-shadow)",
            overflow: "hidden",
            willChange: "transform",
            transform: "translateZ(0)",
        };
    }
    return {
        background: "var(--dt-glass-bg)",
        backdropFilter: "var(--dt-glass-blur)",
        WebkitBackdropFilter: "var(--dt-glass-blur)",
        border: "0.5px solid var(--dt-glass-border)",
        borderRadius: "24px",
        boxShadow: "var(--dt-glass-inner-glow), var(--dt-glass-shadow)",
        willChange: "transform",
        transform: "translateZ(0)",
    };
}

export default function ChatPage() {
    const router = useRouter()
    // Chat state from layout-level context — survives tab switches
    const {
        messages, activeAssistantId,
        selectedCorpus, setSelectedCorpus, selectedLaws, setSelectedLaws,
        useInternet, setUseInternet,
        stream, handleSend,
        sessions, currentSessionId, currentCorpora, loadSession, newChat, deleteSession,
        setMessageFeedback,
    } = useChatState()
    const {jurisdiction, setJurisdiction} = useJurisdiction()
    const {answer, sources, confidence, isStreaming, streamingStatus, streamingProgress, thinkingPreview, followUps, error, clearError} = stream

    const [drawerOpen, setDrawerOpen] = useState(false)
    const [drawerData, setDrawerData] = useState<{ answer: string; sources: Source[]; focusDocId?: string; focusPage?: number; focusSeq: number }>({answer: "", sources: [], focusSeq: 0})
    const [previewIndex, setPreviewIndex] = useState<number | null>(null)
    const [historyOpen, setHistoryOpen] = useState(false)
    const [indexOpen, setIndexOpen] = useState(false)
    const [indexFocusDocId, setIndexFocusDocId] = useState<string | null>(null)
    const [lawPaneOpen, setLawPaneOpen] = useState(false)
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const longPressFiredRef = useRef(false)
    const corpusBlockedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const [layoutMode, setLayoutMode] = useState<"chat" | "split" | "source">("split")
    const [customCorpus, setCustomCorpus] = useState("")
    const [corpusWarning, setCorpusWarning] = useState<{corpus: string, jurisdiction: Jurisdiction} | null>(null)
    const [corpusBlocked, setCorpusBlocked] = useState(false)
    const [hideCorpusWarning, setHideCorpusWarning] = useState(false)
    const [availableCorpora, setAvailableCorpora] = useState<CorpusEntry[]>([])
    const [corporaLoading, setCorporaLoading] = useState(false)
    const {isDark} = useColorMode()
    const isStrict = isDark
    const isMobile = useIsMobile()
    const documentIndex = useDocumentIndex(messages)

    // Law selector: fetch available laws from backend based on jurisdiction
    const [availableLaws, setAvailableLaws] = useState<{id: string; name: string; name_en: string}[]>([])
    useEffect(() => {
        const corpus = jurisdiction === "uk" ? "uk" : jurisdiction === "au" ? "au" : ""
        if (!corpus) { setAvailableLaws([]); setLawPaneOpen(false); return }
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        const controller = new AbortController()
        fetch(`${sseBase}/api/v1/laws?corpus=${corpus}`, {signal: controller.signal})
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data?.laws?.length) {
                    setAvailableLaws(data.laws)
                    setSelectedLaws(data.laws.map((l: {id: string}) => l.id))
                    setLawPaneOpen(true)
                } else {
                    setAvailableLaws([])
                    setLawPaneOpen(false)
                }
            })
            .catch(err => { if (err.name !== "AbortError") { setAvailableLaws([]); setLawPaneOpen(false) } })
        return () => controller.abort()
    }, [jurisdiction])

    const scrollAreaRef = useRef<HTMLDivElement>(null)
    const inputFocusRef = useRef<(() => void) | null>(null)
    /** Ref attached to the last assistant message wrapper, used for scroll-to-top-of-answer. */
    const lastAssistantRef = useRef<HTMLDivElement>(null)
    /** Track whether the user is near the bottom of the scroll area.
     *  Updated on scroll events; used to decide if auto-scroll should fire. */
    const isNearBottomRef = useRef(true)
    const prevMessageCountRef = useRef(0)

    // Redirect to landing if no valid session cookie
    useEffect(() => {
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        fetch(`${sseBase}/auth/me`, {credentials: "include"})
            .then(res => {
                if (!res.ok) router.replace("/")
            })
            .catch(() => router.replace("/"))
    }, [router])

    // (Sessions are managed by ChatStateProvider)

    const handleSourceClick = useCallback((answer: string, sources: Source[], focusDocId?: string, focusPage?: number) => {
        setDrawerData(prev => ({answer, sources, focusDocId, focusPage, focusSeq: prev.focusSeq + 1}))
        setDrawerOpen(true)
        // Also focus the doc in the document index if it's open
        if (focusDocId) {
            setIndexFocusDocId(focusDocId)
        }
    }, [])

    const showCorpusBlocked = useCallback(() => {
        setCorpusBlocked(true)
        if (corpusBlockedTimerRef.current) clearTimeout(corpusBlockedTimerRef.current)
        corpusBlockedTimerRef.current = setTimeout(() => setCorpusBlocked(false), 4000)
    }, [])

    // Cleanup timers on unmount
    useEffect(() => {
        return () => {
            if (longPressTimerRef.current) clearTimeout(longPressTimerRef.current)
            if (corpusBlockedTimerRef.current) clearTimeout(corpusBlockedTimerRef.current)
        }
    }, [])

    const onSend = useCallback((question: string) => {
        setPreviewIndex(null)
        const result = handleSend(question)
        if (result === "blocked") {
            showCorpusBlocked()
        }
        // "streaming" means previous query still running — silently ignore
    }, [handleSend, showCorpusBlocked])

    // Load custom corpus name and corpus warning preference from localStorage
    useEffect(() => {
        const storedName = localStorage.getItem("neolex_custom_corpus_name")
        if (storedName) setCustomCorpus(storedName)
        setHideCorpusWarning(localStorage.getItem("neolex_hide_corpus_warning") === "1")
    }, [])

    // Fetch available corpora when custom jurisdiction is selected
    const fetchCorpora = useCallback(() => {
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        setCorporaLoading(true)
        fetch(`${sseBase}/api/v1/corpora`, {credentials: "include"})
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data?.corpora) {
                    setAvailableCorpora(data.corpora)
                    // Auto-select corpus_id if none stored yet
                    const storedId = localStorage.getItem("neolex_custom_corpus")
                    if (!storedId && data.corpora.length > 0) {
                        const first = data.corpora[0]
                        setCustomCorpus(first.name)
                        localStorage.setItem("neolex_custom_corpus", first.corpus_id)
                        localStorage.setItem("neolex_custom_corpus_name", first.name)
                        // Default: "All" (no collection filter)
                        localStorage.removeItem("neolex_selected_collection")
                        localStorage.removeItem("neolex_selected_doc_ids")
                    }
                }
            })
            .catch(() => {})
            .finally(() => setCorporaLoading(false))
    }, [])

    // Fetch corpora when switching to custom jurisdiction
    useEffect(() => {
        if (jurisdiction === "custom") {
            fetchCorpora()
        }
    }, [jurisdiction, fetchCorpora])

    // Reset preview when jurisdiction changes
    useEffect(() => {
        setPreviewIndex(null)
    }, [jurisdiction])

    // Update document title
    useEffect(() => {
        if (isStreaming) {
            const lastQ = messages.filter(m => m.role === "user").at(-1)?.content
            if (lastQ) {
                document.title = lastQ.length > 50 ? lastQ.slice(0, 50) + "…" : lastQ;
                return
            }
        }
        document.title = "Vitreon Legal — Your AI Legal Counsel"
    }, [isStreaming, messages])

    // Track scroll position to decide whether auto-scroll should fire
    useEffect(() => {
        const el = scrollAreaRef.current
        if (!el) return
        const NEAR_BOTTOM_PX = 120
        const onScroll = () => {
            isNearBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM_PX
        }
        el.addEventListener("scroll", onScroll, {passive: true})
        return () => el.removeEventListener("scroll", onScroll)
    }, [])

    // Auto-scroll: when a new message is added (user sent a question), scroll to the
    // top of the latest assistant message so the answer heading is visible. During
    // streaming, only scroll if the user is already near the bottom to avoid
    // fighting manual scrolling.
    useEffect(() => {
        const el = scrollAreaRef.current
        if (!el) return
        const newMessageAdded = messages.length > prevMessageCountRef.current
        prevMessageCountRef.current = messages.length

        if (newMessageAdded) {
            // New message just appeared — scroll to show it.
            // For user messages, scroll to bottom so the input stays visible.
            // For assistant messages, scroll to the top of the answer card.
            const lastMsg = messages.at(-1)
            if (lastMsg?.role === "assistant" && lastAssistantRef.current) {
                requestAnimationFrame(() => {
                    lastAssistantRef.current?.scrollIntoView({
                        block: "start",
                        behavior: "smooth",
                    })
                })
            } else {
                el.scrollTop = el.scrollHeight
            }
        }
        // No auto-scroll during streaming — let the user scroll freely.
    }, [messages])

    // Cmd+K focus
    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                inputFocusRef.current?.()
            }
        }
        window.addEventListener("keydown", handler)
        return () => window.removeEventListener("keydown", handler)
    }, [])

    const previewScenarios = PREVIEW_SCENARIOS_MAP[jurisdiction] ?? []
    const presetQuestions = getPresetQuestions(jurisdiction)
    const showPreview = messages.length === 0 && previewIndex !== null && previewIndex < previewScenarios.length
    const lastAssistant = messages.at(-1)
    const showFollowUps = !isStreaming && lastAssistant?.role === "assistant" && lastAssistant.content

    // Derive Strict source margin entries from the most recent assistant message sources
    const strictMarginSources: StrictSourceMarginSource[] = (() => {
        const recentSources = lastAssistant?.sources ?? (isStreaming ? sources : [])
        return recentSources.slice(0, 8).map((s, i) => ({
            id: s.doc_id ?? `src-${i}`,
            label: s.title ?? s.doc_id ?? `Source ${i + 1}`,
            detail: s.page_numbers?.length
                ? `p. ${s.page_numbers[0]}`
                : s.case_number ?? "",
        }))
    })()
    const strictSourcesVisible = isStrict && strictMarginSources.length > 0 && !isStreaming

    return (
        <div className="p-2 sm:p-4" style={{
            height: "100%",
            display: "flex",
            alignItems: "stretch",
            gap: isMobile ? 0 : SPACE['2'],
            overflow: "hidden",
            maxWidth: "100vw",
            position: "relative",
            ...(isStrict ? {background: "var(--strict-page-bg)"} : {}),
        }}>
            {/* ── History panel (left) — full-screen overlay on mobile ── */}
            <AnimatePresence>
                {historyOpen && (
                    <motion.div
                        initial={isMobile ? {x: "-100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {x: 0} : {opacity: 1, width: 260}}
                        exit={isMobile ? {x: "-100%"} : {opacity: 0, width: 0}}
                        transition={isMobile ? {type: "spring", damping: 30, stiffness: 300} : {duration: 0.25, ease: [0.32, 0.72, 0, 1]}}
                        className={isStrict && !isMobile ? "v3-glass-elevated" : undefined}
                        style={{
                            display: "flex", flexDirection: "column",
                            minHeight: 0, flexShrink: 0,
                            overflow: "clip",
                            ...(isMobile ? {
                                position: "fixed",
                                inset: 0,
                                zIndex: 100,
                                borderRadius: 0,
                                willChange: "transform",
                                background: "var(--dt-overlay-bg)",
                                backdropFilter: "var(--dt-glass-blur-light)",
                                WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                                boxShadow: "var(--dt-glass-inner-glow)",
                                border: "0.5px solid var(--dt-panel-border-color)",
                            } : makeGlassPanel(isStrict)),
                        }}
                    >
                        <HistoryPanel
                            sessions={sessions}
                            currentSessionId={currentSessionId}
                            onLoadSession={loadSession}
                            onNewChat={newChat}
                            onDeleteSession={deleteSession}
                            onClose={() => setHistoryOpen(false)}
                            isMobile={isMobile}
                        />
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Chat panel ── */}
            <div className="animate-glass-in" style={{
                flex: (drawerOpen && drawerData.sources.length > 0) || showPreview
                    ? layoutMode === "chat" ? 2 : layoutMode === "source" ? 1 : 1
                    : 1,
                display: "flex",
                flexDirection: "column",
                minHeight: 0,
                minWidth: 0,
                position: "relative",
                overflow: "hidden",
                contain: "style",
                transition: `all ${TIMING.slow} ${EASE.out}`,
                ...(isStrict && !isMobile ? {} : makeGlassPanel(false)),
            }}>
            <StrictChatWrapper
                active={isStrict && !isMobile}
                sources={strictMarginSources}
                onSourceClick={(id) => {
                    const recentSources = lastAssistant?.sources ?? sources
                    const src = recentSources.find((s, i) => (s.doc_id ?? `src-${i}`) === id)
                    if (src) handleSourceClick(
                        lastAssistant?.content ?? "",
                        recentSources,
                        src.doc_id,
                        src.page_numbers?.[0]
                    )
                }}
                sourcesVisible={strictSourcesVisible}
            >
                {/* Header */}
                <div style={{
                    padding: isMobile ? `${SPACE['3']}px ${SPACE['3']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                    borderBottom: isStrict ? "1px solid var(--strict-header-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                    display: "flex", alignItems: "center", gap: isMobile ? SPACE['2'] : SPACE['3'], flexShrink: 0,
                    background: isStrict ? "var(--strict-chat-header-bg)" : "var(--dt-glass-bg-subtle)",
                    overflow: "visible", position: "relative", zIndex: 10,
                }}>
                    <div style={{
                        width: isMobile ? 26 : 30, height: isMobile ? 26 : 30, borderRadius: "50%",
                        background: isStrict ? "transparent" : "var(--dt-accent-tint)",
                        border: isStrict ? "1px solid var(--strict-gold-border-active)" : "0.5px solid var(--dt-accent-border-color)",
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        boxShadow: isStrict ? undefined : "inset 0 1px 0 rgba(255,255,255,0.65)",
                    }}>
            <span style={{
                fontSize: isMobile ? TYPE_SCALE.sm : TYPE_SCALE.md,
                fontWeight: isStrict ? "normal" : 700,
                color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                lineHeight: 1,
                fontFamily: isStrict ? "Georgia, serif" : FONT.brand,
            }}>{isStrict ? "V" : "N"}</span>
                    </div>
                    {!isMobile && <span style={{
                        fontWeight: isStrict ? "normal" : 700,
                        fontSize: TYPE_SCALE.md,
                        color: isStrict ? "var(--strict-text-primary)" : "var(--dt-text-primary)",
                        fontFamily: isStrict ? "Georgia, serif" : FONT.brand,
                        letterSpacing: isStrict ? "0.01em" : "-0.04em",
                    }}>
            Vitreon Legal
          </span>}
                    {/* Jurisdiction selector pills */}
                    <div style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 2 : 3,
                        marginLeft: isMobile ? SPACE['1'] : SPACE['3'],
                        overflowX: "auto",
                        minWidth: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                    }}>
                        {(["difc", "cz", "uk", "au", "custom"] as Jurisdiction[]).map((key) => {
                            const config = JURISDICTIONS[key]
                            const isActive = jurisdiction === key
                            const isEnabled = key === "difc" || key === "cz" || key === "uk" || key === "au" || key === "custom"
                            const hasLawPane = (key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key
                            // Wrap "custom" pill in a relative container so the dropdown anchors to it
                            const pillButton = (
                                <button
                                    key={key}
                                    disabled={!isEnabled}
                                    onClick={() => {
                                        if (longPressFiredRef.current) {
                                            longPressFiredRef.current = false
                                            return
                                        }
                                        if (!isEnabled) return

                                        // Custom pill — just select the jurisdiction (corpora pills shown inline below)
                                        if (key === "custom") {
                                            if (!isActive) setJurisdiction(key)
                                            setLawPaneOpen(false)
                                            return
                                        }

                                        const newCorpus = jurisdictionToCorpus(key)

                                        // Already in this chat's corpora, or new chat — just switch
                                        if (currentCorpora.length === 0 || currentCorpora.includes(newCorpus)) {
                                            if (isActive && hasLawPane) {
                                                setLawPaneOpen(o => !o)
                                            } else {
                                                setJurisdiction(key)
                                                if (hasLawPane) setLawPaneOpen(true)
                                                else setLawPaneOpen(false)
                                            }
                                            return
                                        }

                                        // Would be 3rd+ corpus — block
                                        if (currentCorpora.length >= 2) {
                                            showCorpusBlocked()
                                            return
                                        }

                                        // Would be 2nd corpus — show warning (unless dismissed)
                                        if (hideCorpusWarning) {
                                            setJurisdiction(key)
                                            if (hasLawPane) setLawPaneOpen(true)
                                            else setLawPaneOpen(false)
                                        } else {
                                            setCorpusWarning({corpus: newCorpus, jurisdiction: key})
                                        }
                                    }}
                                    title={isEnabled ? config.description : "Coming soon"}
                                    onMouseDown={(e) => {
                                        if (isEnabled) e.currentTarget.style.transform = "scale(0.97)"
                                        longPressFiredRef.current = false
                                        if (hasLawPane && isActive) {
                                            longPressTimerRef.current = setTimeout(() => {
                                                longPressFiredRef.current = true
                                                setSelectedLaws(availableLaws.map(l => l.id))
                                                longPressTimerRef.current = null
                                            }, 500)
                                        }
                                    }}
                                    onMouseUp={(e) => {
                                        e.currentTarget.style.transform = "scale(1)"
                                        if (longPressTimerRef.current) {
                                            clearTimeout(longPressTimerRef.current)
                                            longPressTimerRef.current = null
                                        }
                                    }}
                                    onTouchStart={() => {
                                        longPressFiredRef.current = false
                                        if (hasLawPane && isActive) {
                                            longPressTimerRef.current = setTimeout(() => {
                                                longPressFiredRef.current = true
                                                setSelectedLaws(availableLaws.map(l => l.id))
                                                longPressTimerRef.current = null
                                            }, 500)
                                        }
                                    }}
                                    onTouchEnd={() => {
                                        if (longPressTimerRef.current) {
                                            clearTimeout(longPressTimerRef.current)
                                            longPressTimerRef.current = null
                                        }
                                    }}
                                    onContextMenu={(e) => e.preventDefault()}
                                    onMouseEnter={(e) => {
                                        if (!isActive && isEnabled) {
                                            e.currentTarget.style.background = isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-pill-bg-hover)"
                                            e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border-active)" : "var(--dt-glass-border)"
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.transform = "scale(1)"
                                        if (!isActive && isEnabled) {
                                            e.currentTarget.style.background = isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"
                                            e.currentTarget.style.borderColor = isStrict ? "var(--strict-gold-border)" : "var(--dt-glass-border)"
                                        }
                                    }}
                                    style={{
                                        display: "inline-flex", alignItems: "center", gap: 2,
                                        fontSize: TYPE_SCALE.xs, fontWeight: isActive ? (isStrict ? 400 : 700) : 500,
                                        padding: isMobile ? `2px ${SPACE['2']}px` : `3px ${SPACE['2']}px`, borderRadius: RADIUS.sm,
                                        cursor: isEnabled ? "pointer" : "not-allowed",
                                        opacity: isEnabled ? 1 : 0.38,
                                        background: isActive
                                            ? (isStrict ? "var(--strict-pill-active-bg)" : "var(--dt-color-gold-solid)")
                                            : (isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"),
                                        border: isActive
                                            ? (isStrict ? `1px solid var(--strict-pill-active-border)` : "0.5px solid var(--dt-color-gold-border)")
                                            : (isStrict ? `1px solid var(--strict-gold-border)` : "0.5px solid var(--dt-glass-border)"),
                                        color: isActive
                                            ? (isStrict ? "var(--strict-text-primary)" : "var(--dt-text-primary)")
                                            : (isStrict ? "var(--strict-gold-text)" : "var(--dt-text-tertiary)"),
                                        fontFamily: FONT.sans,
                                        transition: `all ${TIMING.fast} ${EASE.spring}`,
                                        whiteSpace: "nowrap",
                                        userSelect: "none",
                                        WebkitUserSelect: "none",
                                    }}
                                >
                                    {config.name}
                                </button>
                            )

                            return pillButton
                        })}
                        {/* Active corpora indicator */}
                        {currentCorpora.length > 0 && (
                            <span style={{
                                fontSize: TYPE_SCALE.xs,
                                color: "var(--dt-text-quaternary)",
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                                fontFamily: FONT.sans,
                            }}>
                                {currentCorpora.join(" + ")}
                            </span>
                        )}
                        {/* Internet toggle — teal accent (Neon) or gold accent (Strict) */}
                        <button
                            onClick={() => setUseInternet(prev => !prev)}
                            title={useInternet ? "Web search enabled — click to disable" : "Web search disabled — click to enable"}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: 3,
                                padding: isMobile ? `2px ${SPACE['2']}px` : `3px ${SPACE['2']}px`, borderRadius: RADIUS.sm,
                                fontSize: TYPE_SCALE.xs, fontWeight: useInternet ? (isStrict ? 400 : 700) : 500, lineHeight: 1,
                                fontFamily: FONT.sans,
                                background: useInternet
                                    ? (isStrict ? "var(--strict-internet-active-bg)" : "var(--dt-teal-tint)")
                                    : (isStrict ? "var(--strict-glass-bg)" : "var(--dt-pill-bg)"),
                                border: useInternet
                                    ? (isStrict ? `1px solid var(--strict-internet-active-border)` : "0.5px solid var(--dt-teal-border-color)")
                                    : (isStrict ? `1px solid var(--strict-gold-border)` : "0.5px solid var(--dt-glass-border)"),
                                color: useInternet
                                    ? (isStrict ? "var(--strict-gold-text)" : "var(--dt-teal-on-surface)")
                                    : (isStrict ? "var(--strict-text-secondary)" : "var(--dt-text-tertiary)"),
                                cursor: "pointer",
                                transition: `all ${TIMING.fast} ${EASE.spring}`,
                                userSelect: "none",
                                WebkitUserSelect: "none",
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                            }}
                        >
                            <Globe size={TYPE_SCALE.xs} strokeWidth={useInternet ? 2 : 1.5}/>
                            Internet
                        </button>
                    </div>
                    {/* History toggle + Sources toggle + New chat */}
                    <button
                        onClick={() => setHistoryOpen(o => !o)}
                        title="Chat history"
                        style={{
                            display: "flex", alignItems: "center", gap: SPACE['1'],
                            padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.sm, fontWeight: 500,
                            background: historyOpen
                                ? (isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-tint-subtle)")
                                : (isStrict ? "var(--strict-btn-bg)" : "var(--dt-button-bg)"),
                            border: historyOpen
                                ? (isStrict ? "1px solid var(--strict-gold-border-active)" : "0.5px solid var(--dt-accent-border-color)")
                                : (isStrict ? "1px solid var(--strict-btn-border)" : "0.5px solid var(--dt-button-border-color)"),
                            color: historyOpen
                                ? (isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)")
                                : (isStrict ? "var(--strict-btn-text)" : "var(--dt-text-tertiary)"),
                            cursor: "pointer", transition: `all ${TIMING.instant}`,
                            fontFamily: FONT.sans,
                        }}
                        onMouseEnter={e => {
                            if (!historyOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"
                        }}
                        onMouseLeave={e => {
                            if (!historyOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border)"
                        }}
                    >
                        <History size={TYPE_SCALE.sm} strokeWidth={1.8}/>
                    </button>
                    {documentIndex.length > 0 && (
                        <button
                            onClick={() => {
                                setIndexOpen(o => !o)
                                setIndexFocusDocId(null)
                            }}
                            title="Document sources index"
                            style={{
                                display: "flex", alignItems: "center", gap: SPACE['1'],
                                padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.sm, fontWeight: 500,
                                position: "relative",
                                background: indexOpen
                                    ? (isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-tint-subtle)")
                                    : (isStrict ? "var(--strict-btn-bg)" : "var(--dt-button-bg)"),
                                border: indexOpen
                                    ? (isStrict ? "1px solid var(--strict-gold-border-active)" : "0.5px solid var(--dt-accent-border-color)")
                                    : (isStrict ? "1px solid var(--strict-btn-border)" : "0.5px solid var(--dt-button-border-color)"),
                                color: indexOpen
                                    ? (isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)")
                                    : (isStrict ? "var(--strict-btn-text)" : "var(--dt-text-tertiary)"),
                                cursor: "pointer", transition: `all ${TIMING.instant}`,
                                fontFamily: FONT.sans,
                            }}
                            onMouseEnter={e => {
                                if (!indexOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"
                            }}
                            onMouseLeave={e => {
                                if (!indexOpen && isStrict) e.currentTarget.style.borderColor = "var(--strict-btn-border)"
                            }}
                        >
                            <BookOpen size={TYPE_SCALE.sm} strokeWidth={1.8}/>
                            {/* Badge with count */}
                            <span style={{
                                display: "inline-flex", alignItems: "center", justifyContent: "center",
                                minWidth: SPACE['4'], height: SPACE['4'], borderRadius: RADIUS.md,
                                padding: `0 ${SPACE['1']}px`,
                                fontSize: TYPE_SCALE.xs, fontWeight: isStrict ? 400 : 700,
                                background: isStrict ? "var(--strict-gold-badge-bg)" : "var(--dt-accent-glow)",
                                color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                                border: isStrict ? "1px solid var(--strict-gold-badge-border)" : undefined,
                            }}>
                                {documentIndex.length}
                            </span>
                        </button>
                    )}
                    {messages.length > 0 && (
                        <button
                            onClick={() => {
                                newChat();
                                setPreviewIndex(null)
                            }}
                            title="New chat"
                            style={{
                                display: "flex", alignItems: "center", gap: SPACE['1'],
                                padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.sm, fontWeight: 500,
                                background: isStrict ? "var(--strict-btn-bg)" : "var(--dt-button-bg)",
                                border: isStrict ? "1px solid var(--strict-btn-border)" : "0.5px solid var(--dt-button-border-color)",
                                color: isStrict ? "var(--strict-btn-text)" : "var(--dt-text-tertiary)",
                                cursor: "pointer", transition: `all ${TIMING.instant}`,
                                fontFamily: FONT.sans,
                            }}
                            onMouseEnter={e => {
                                if (isStrict) {
                                    e.currentTarget.style.borderColor = "var(--strict-btn-border-hover)"
                                    e.currentTarget.style.color = "var(--strict-text-secondary)"
                                } else {
                                    e.currentTarget.style.background = "var(--dt-button-bg-hover)";
                                    e.currentTarget.style.color = "var(--dt-text-primary)"
                                }
                            }}
                            onMouseLeave={e => {
                                if (isStrict) {
                                    e.currentTarget.style.borderColor = "var(--strict-btn-border)"
                                    e.currentTarget.style.color = "var(--strict-btn-text)"
                                } else {
                                    e.currentTarget.style.background = "var(--dt-button-bg)";
                                    e.currentTarget.style.color = "var(--dt-text-tertiary)"
                                }
                            }}
                        >
                            <SquarePen size={TYPE_SCALE.sm} strokeWidth={1.8}/>
                            New
                        </button>
                    )}
                </div>

                {/* Corpus warning banner — switching to a 2nd corpus */}
                {corpusWarning && (
                    <div style={{
                        padding: `${SPACE['3']}px ${SPACE['5']}px`,
                        background: "var(--dt-accent-tint-subtle)",
                        border: "0.5px solid var(--dt-accent-border-color)",
                        borderRadius: 0,
                        borderBottom: "0.5px solid var(--dt-accent-glow)",
                        display: "flex", alignItems: "center", gap: SPACE['3'], flexWrap: "wrap",
                        fontSize: TYPE_SCALE.sm,
                        color: "var(--dt-text-primary)",
                        fontFamily: FONT.sans,
                        flexShrink: 0,
                    }}>
                        <span>
                            Adding <strong>{JURISDICTIONS[corpusWarning.jurisdiction].name}</strong> to this conversation. Cross-jurisdiction queries may be slower.
                        </span>
                        <div style={{display: "flex", gap: SPACE['2'], marginLeft: "auto"}}>
                            <button
                                onClick={() => {
                                    const j = corpusWarning.jurisdiction
                                    const hasLawPane = (j === "uk" || j === "au") && availableLaws.length > 0
                                    setJurisdiction(j)
                                    if (hasLawPane) setLawPaneOpen(true)
                                    else setLawPaneOpen(false)
                                    setCorpusWarning(null)
                                }}
                                style={{
                                    fontSize: TYPE_SCALE.xs, fontWeight: 600,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md,
                                    cursor: "pointer",
                                    background: "var(--dt-accent-glow)",
                                    border: "0.5px solid var(--dt-accent-border-color)",
                                    color: "var(--dt-accent-color)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                Continue
                            </button>
                            <button
                                onClick={() => setCorpusWarning(null)}
                                style={{
                                    fontSize: TYPE_SCALE.xs, fontWeight: 500,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md,
                                    cursor: "pointer",
                                    background: "var(--dt-button-bg)",
                                    border: "0.5px solid var(--dt-glass-border-subtle)",
                                    color: "var(--dt-text-tertiary)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                        <label style={{
                            fontSize: TYPE_SCALE.xs, opacity: 0.55, cursor: "pointer",
                            display: "flex", alignItems: "center", gap: SPACE['1'],
                            fontFamily: FONT.sans,
                        }}>
                            <input
                                type="checkbox"
                                style={{width: SPACE['3'], height: SPACE['3'], cursor: "pointer"}}
                                onChange={(e) => {
                                    setHideCorpusWarning(e.target.checked)
                                    localStorage.setItem("neolex_hide_corpus_warning", e.target.checked ? "1" : "")
                                }}
                            />
                            Don&apos;t show again
                        </label>
                    </div>
                )}

                {/* Corpus blocked banner — max 2 per conversation */}
                <AnimatePresence>
                    {corpusBlocked && (
                        <motion.div
                            initial={{opacity: 0, height: 0}}
                            animate={{opacity: 1, height: "auto"}}
                            exit={{opacity: 0, height: 0}}
                            transition={{...V3_SPRING.standard, restDelta: 0.5}}
                            style={{overflow: "hidden", flexShrink: 0}}
                        >
                            <div style={{
                                padding: `${SPACE['3']}px ${SPACE['5']}px`,
                                background: "var(--dt-error-bg-subtle)",
                                borderBottom: "0.5px solid var(--dt-error-border-subtle)",
                                fontSize: TYPE_SCALE.sm,
                                color: "var(--dt-error-text)",
                                fontFamily: FONT.sans,
                                display: "flex", alignItems: "center", gap: SPACE['2'],
                            }}>
                                <span>Maximum 2 jurisdictions per conversation. Start a new chat to use a different corpus.</span>
                                <button
                                    onClick={() => {
                                        newChat()
                                        setCorpusBlocked(false)
                                    }}
                                    style={{
                                        fontSize: TYPE_SCALE.xs, fontWeight: 600,
                                        padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md,
                                        cursor: "pointer", marginLeft: "auto", whiteSpace: "nowrap",
                                        background: "var(--dt-error-bg-interactive)",
                                        border: "0.5px solid var(--dt-error-border-active)",
                                        color: "var(--dt-error-text)",
                                        fontFamily: FONT.sans,
                                        transition: `all ${TIMING.instant}`,
                                    }}
                                >
                                    New chat
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Law selector pills (UK/AU) — toggle via country pill click */}
                {(jurisdiction === "uk" || jurisdiction === "au") && lawPaneOpen && availableLaws.length > 0 && (
                    <div style={{
                        padding: isMobile ? `${SPACE['1']}px ${SPACE['3']}px` : `${SPACE['1']}px ${SPACE['6']}px`,
                        borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 3 : SPACE['1'],
                        overflowX: "auto",
                        flexShrink: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                        background: "var(--dt-glass-bg-subtle)",
                    }}>
                        <span style={{
                            fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                            color: "var(--dt-text-quaternary)",
                            fontFamily: FONT.sans,
                        }}>
                            {selectedLaws.length === availableLaws.length ? "All" : `${selectedLaws.length}/${availableLaws.length}`}
                        </span>
                        {availableLaws.map((law) => {
                            const isActive = selectedLaws.includes(law.id)
                            return (
                                <button
                                    key={law.id}
                                    onClick={() => {
                                        if (longPressFiredRef.current) {
                                            longPressFiredRef.current = false
                                            return
                                        }
                                        setSelectedLaws(prev =>
                                            prev.includes(law.id)
                                                ? prev.filter(l => l !== law.id)
                                                : [...prev, law.id]
                                        )
                                    }}
                                    onMouseDown={() => {
                                        longPressFiredRef.current = false
                                        longPressTimerRef.current = setTimeout(() => {
                                            longPressFiredRef.current = true
                                            setSelectedLaws([law.id])
                                            longPressTimerRef.current = null
                                        }, 500)
                                    }}
                                    onMouseUp={() => {
                                        if (longPressTimerRef.current) {
                                            clearTimeout(longPressTimerRef.current)
                                            longPressTimerRef.current = null
                                        }
                                    }}
                                    onTouchStart={() => {
                                        longPressFiredRef.current = false
                                        longPressTimerRef.current = setTimeout(() => {
                                            longPressFiredRef.current = true
                                            setSelectedLaws([law.id])
                                            longPressTimerRef.current = null
                                        }, 500)
                                    }}
                                    onTouchEnd={() => {
                                        if (longPressTimerRef.current) {
                                            clearTimeout(longPressTimerRef.current)
                                            longPressTimerRef.current = null
                                        }
                                    }}
                                    onContextMenu={(e) => e.preventDefault()}
                                    title={law.name_en}
                                    style={{
                                        fontSize: TYPE_SCALE.sm, fontWeight: isActive ? 700 : 500,
                                        padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.sm,
                                        cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                                        userSelect: "none", WebkitUserSelect: "none",
                                        background: isActive
                                            ? "var(--dt-color-gold-solid)"
                                            : "var(--dt-pill-bg-subtle)",
                                        border: isActive
                                            ? "0.5px solid var(--dt-color-gold-border)"
                                            : "0.5px solid var(--dt-pill-border-color)",
                                        color: isActive
                                            ? "var(--dt-text-primary)"
                                            : "var(--dt-text-tertiary)",
                                        fontFamily: FONT.sans,
                                        transition: `all ${TIMING.fast} ${EASE.spring}`,
                                    }}
                                    onMouseEnter={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = "var(--dt-glass-bg-hover)"
                                            e.currentTarget.style.borderColor = "var(--dt-glass-border)"
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = "var(--dt-pill-bg-subtle)"
                                            e.currentTarget.style.borderColor = "var(--dt-pill-border-color)"
                                        }
                                    }}
                                >
                                    {law.name}
                                </button>
                            )
                        })}
                        {selectedLaws.length < availableLaws.length && (
                            <button
                                onClick={() => setSelectedLaws(availableLaws.map(l => l.id))}
                                title="Select all laws"
                                style={{
                                    fontSize: TYPE_SCALE.sm, fontWeight: 500,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.sm,
                                    cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                                    userSelect: "none", WebkitUserSelect: "none",
                                    background: "var(--dt-pill-bg)",
                                    border: "0.5px solid var(--dt-glass-border)",
                                    color: "var(--dt-text-tertiary)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.instant}`,
                                }}
                            >
                                All
                            </button>
                        )}
                    </div>
                )}

                {/* Custom corpus selector pills — inline bar like Czech laws */}
                {jurisdiction === "custom" && (
                    <div style={{
                        padding: isMobile ? `${SPACE['2']}px ${SPACE['3']}px` : `${SPACE['2']}px ${SPACE['6']}px`,
                        borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                        display: "flex",
                        alignItems: "center",
                        gap: SPACE['2'],
                        overflowX: "auto",
                        flexShrink: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                        background: "var(--dt-glass-bg-subtle)",
                    }}>
                        <span style={{
                            fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                            color: "var(--dt-text-quaternary)",
                            fontFamily: FONT.sans,
                        }}>
                            Collections
                        </span>
                        {corporaLoading ? (
                            <span style={{
                                fontSize: TYPE_SCALE.sm,
                                color: "var(--dt-text-quaternary)",
                                fontFamily: FONT.sans,
                                whiteSpace: "nowrap",
                            }}>
                                Loading...
                            </span>
                        ) : availableCorpora.length > 0 ? (
                            (() => {
                                const storedCollection = typeof window !== "undefined"
                                    ? localStorage.getItem("neolex_selected_collection") : null
                                // "All" is active when no specific collection is stored
                                const isAllActive = !storedCollection
                                const corpusId = availableCorpora[0]?.corpus_id ?? ""
                                // Total document count across all collections
                                const totalDocs = availableCorpora.reduce((sum, c) => sum + (c.doc_count ?? c.doc_ids?.length ?? 0), 0)

                                const pillStyle = (active: boolean) => ({
                                    fontSize: TYPE_SCALE.sm, fontWeight: active ? 700 : 500,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.sm,
                                    cursor: "pointer" as const, whiteSpace: "nowrap" as const, flexShrink: 0,
                                    userSelect: "none" as const, WebkitUserSelect: "none" as const,
                                    background: active
                                        ? "var(--dt-color-gold-solid)"
                                        : "var(--dt-pill-bg-subtle)",
                                    border: active
                                        ? "0.5px solid var(--dt-color-gold-border)"
                                        : "0.5px solid var(--dt-pill-border-color)",
                                    color: active
                                        ? "var(--dt-text-primary)"
                                        : "var(--dt-text-tertiary)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.fast} ${EASE.spring}`,
                                })

                                const hoverHandlers = (active: boolean) => ({
                                    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
                                        if (!active) {
                                            e.currentTarget.style.background = "var(--dt-glass-bg-hover)"
                                            e.currentTarget.style.borderColor = "var(--dt-glass-border)"
                                        }
                                    },
                                    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
                                        if (!active) {
                                            e.currentTarget.style.background = "var(--dt-pill-bg-subtle)"
                                            e.currentTarget.style.borderColor = "var(--dt-pill-border-color)"
                                        }
                                    },
                                })

                                const truncate = (name: string, max: number = 25) =>
                                    name.length > max ? name.slice(0, max) + "\u2026" : name

                                return <>
                                    {/* "All" pill — no doc_ids filter, searches everything */}
                                    <button
                                        key="__all__"
                                        onClick={() => {
                                            setCustomCorpus("All Documents")
                                            localStorage.setItem("neolex_custom_corpus", corpusId)
                                            localStorage.setItem("neolex_custom_corpus_name", "All Documents")
                                            localStorage.removeItem("neolex_selected_collection")
                                            localStorage.removeItem("neolex_selected_doc_ids")
                                        }}
                                        style={pillStyle(isAllActive)}
                                        {...hoverHandlers(isAllActive)}
                                    >
                                        All ({totalDocs})
                                    </button>
                                    {/* Collection pills */}
                                    {availableCorpora.map((c) => {
                                        const isActive = storedCollection === c.name
                                        const docCount = c.doc_count ?? c.doc_ids?.length ?? 0
                                        return (
                                            <button
                                                key={c.name}
                                                onClick={() => {
                                                    setCustomCorpus(c.name)
                                                    localStorage.setItem("neolex_custom_corpus", c.corpus_id)
                                                    localStorage.setItem("neolex_custom_corpus_name", c.name)
                                                    localStorage.setItem("neolex_selected_collection", c.name)
                                                    if (c.doc_ids && c.doc_ids.length > 0) {
                                                        localStorage.setItem("neolex_selected_doc_ids", JSON.stringify(c.doc_ids))
                                                    } else {
                                                        localStorage.removeItem("neolex_selected_doc_ids")
                                                    }
                                                }}
                                                title={`${c.name} (${docCount} ${docCount === 1 ? "doc" : "docs"})`}
                                                style={pillStyle(isActive)}
                                                {...hoverHandlers(isActive)}
                                            >
                                                {truncate(c.name)}{docCount > 0 ? ` (${docCount})` : ""}
                                            </button>
                                        )
                                    })}
                                </>
                            })()
                        ) : (
                            <button
                                onClick={() => router.push("/documents")}
                                style={{
                                    fontSize: TYPE_SCALE.sm, fontWeight: 500,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.sm,
                                    cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                                    userSelect: "none", WebkitUserSelect: "none",
                                    background: "var(--dt-pill-bg-subtle)",
                                    border: "0.5px solid var(--dt-pill-border-color)",
                                    color: "var(--dt-text-tertiary)",
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.fast} ${EASE.spring}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = "var(--dt-glass-bg-hover)"
                                    e.currentTarget.style.borderColor = "var(--dt-glass-border)"
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = "var(--dt-pill-bg-subtle)"
                                    e.currentTarget.style.borderColor = "var(--dt-pill-border-color)"
                                }}
                            >
                                Upload documents to get started
                            </button>
                        )}
                    </div>
                )}

                {/* Messages */}
                <div ref={scrollAreaRef} style={{flex: 1, overflowY: "auto", padding: isMobile ? `${SPACE['4']}px ${SPACE['3']}px 90px` : `${SPACE['6']}px ${SPACE['6']}px`, minHeight: 0}}>
                    {messages.length === 0 ? (
                        <>
                            <EmptyState
                                onSelectQuestion={onSend}
                                onPreviewQuestion={setPreviewIndex}
                                previewIndex={previewIndex}
                                isDark={isDark}
                                isStrict={isStrict}
                                jurisdiction={jurisdiction}
                            />
                        </>
                    ) : (
                        messages.map((m, idx) => {
                            // Attach ref to the last assistant message for scroll-to-top
                            const isLastAssistant = m.role === "assistant" && idx === messages.length - 1
                            return (
                            <motion.div
                                key={m.id}
                                ref={isLastAssistant ? lastAssistantRef : undefined}
                                variants={isStrict ? V3_FADE_UP : undefined}
                                initial={isStrict ? "hidden" : {opacity: 0, y: SPACE['3'], ...(isMobile ? {} : {scale: 0.98})}}
                                animate={isStrict ? "visible" : {opacity: 1, y: 0, ...(isMobile ? {} : {scale: 1})}}
                                transition={isStrict ? undefined : (isMobile
                                    ? {duration: 0.2, ease: [0.32, 0.72, 0, 1]}
                                    : {
                                        type: "spring",
                                        damping: 25,
                                        stiffness: 200,
                                        delay: idx === messages.length - 1 ? 0.05 : 0,
                                    })}
                            >
                                <ChatMessage
                                    role={m.role}
                                    content={m.content}
                                    sources={m.sources}
                                    confidence={m.confidence}
                                    isStreaming={isStreaming && m.id === activeAssistantId.current}
                                    streamingStatus={isStreaming && m.id === activeAssistantId.current ? streamingStatus : null}
                                    streamingProgress={isStreaming && m.id === activeAssistantId.current ? streamingProgress : null}
                                    streamingThinkingPreview={isStreaming && m.id === activeAssistantId.current ? thinkingPreview : null}
                                    trace={m.trace}
                                    onSourceClick={handleSourceClick}
                                    isDark={isDark}
                                    isStrict={isStrict}
                                    messageId={m.id}
                                    traceId={m.traceId}
                                    conversationId={currentSessionId}
                                    feedback={m.feedback}
                                    onFeedback={setMessageFeedback}
                                />
                            </motion.div>
                            )
                        })
                    )}

                    {showFollowUps && (
                        <div className="mb-4 animate-fade-in-up">
                            <div style={{display: "flex", gap: SPACE['2'], overflowX: "auto", paddingBottom: SPACE['1']}}>
                                {(followUps && followUps.length > 0 ? followUps : FOLLOWUP_SUGGESTIONS).slice(0, 3).map((suggestion) => (
                                    <button key={suggestion} onClick={() => onSend(suggestion)} style={{
                                        flexShrink: 0, fontSize: TYPE_SCALE.xs, padding: `${SPACE['2']}px ${SPACE['4']}px`,
                                        borderRadius: RADIUS.full, cursor: "pointer",
                                        background: isStrict ? "var(--strict-glass-bg)" : "var(--dt-button-bg-hover)",
                                        border: isStrict ? "1px solid var(--strict-gold-border)" : "1px solid var(--dt-glass-border)",
                                        color: isStrict ? "var(--strict-text-secondary)" : "var(--dt-text-secondary-accent)",
                                        transition: `all ${TIMING.fast}`,
                                        fontFamily: isStrict ? "Georgia, serif" : FONT.sans,
                                        fontStyle: isStrict ? "italic" : undefined,
                                    }}
                                            onMouseEnter={(e) => {
                                                if (isStrict) {
                                                    e.currentTarget.style.borderColor = "var(--strict-gold-border-active)"
                                                    e.currentTarget.style.color = "var(--strict-text-primary)"
                                                } else {
                                                    e.currentTarget.style.background = "var(--dt-accent-tint-hover)"
                                                    e.currentTarget.style.color = "var(--dt-accent-color-hover)"
                                                }
                                            }}
                                            onMouseLeave={(e) => {
                                                if (isStrict) {
                                                    e.currentTarget.style.borderColor = "var(--strict-gold-border)"
                                                    e.currentTarget.style.color = "var(--strict-text-secondary)"
                                                } else {
                                                    e.currentTarget.style.background = "var(--dt-button-bg-hover)"
                                                    e.currentTarget.style.color = "var(--dt-text-secondary-accent)"
                                                }
                                            }}
                                    >
                                        {suggestion}
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {error && (
                        <div style={{
                            fontSize: TYPE_SCALE.sm, textAlign: "center", marginTop: SPACE['2'], marginBottom: SPACE['4'],
                            borderRadius: RADIUS.lg, padding: `${SPACE['3']}px ${SPACE['4']}px`,
                            color: "var(--dt-error-color)",
                            background: "var(--dt-error-bg)",
                            border: "1px solid var(--dt-error-border-color)",
                            display: "flex", alignItems: "center", justifyContent: "center", gap: SPACE['3'],
                            flexWrap: "wrap",
                        }}>
                            <span>{error}</span>
                            <button
                                onClick={() => {
                                    clearError()
                                }}
                                style={{
                                    fontSize: TYPE_SCALE.sm, fontWeight: 600, padding: `${SPACE['1']}px ${SPACE['3']}px`,
                                    borderRadius: RADIUS.md, cursor: "pointer",
                                    background: "var(--dt-error-bg-hover)",
                                    border: "1px solid var(--dt-error-border-strong)",
                                    color: "var(--dt-error-color)",
                                    fontFamily: FONT.sans,
                                }}
                            >
                                Dismiss
                            </button>
                        </div>
                    )}
                </div>

                {/* Input */}
                <div style={{
                    padding: isMobile ? `${SPACE['3']}px ${SPACE['3']}px ${SPACE['5']}px` : `${SPACE['3']}px ${SPACE['6']}px ${SPACE['4']}px`,
                    borderTop: isStrict ? "1px solid var(--strict-footer-border)" : "0.5px solid var(--dt-glass-border)",
                    flexShrink: 0,
                    background: isStrict ? "var(--strict-footer-bg)" : "var(--dt-glass-bg-subtle)",
                }}>
                    <ChatInput onSend={onSend} disabled={isStreaming} onFocusRef={inputFocusRef}/>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        color: isStrict ? "var(--strict-text-dim)" : "var(--dt-text-quaternary)",
                        fontFamily: isStrict ? "Georgia, serif" : FONT.sans,
                        fontStyle: isStrict ? "italic" : undefined,
                        margin: `${SPACE['2']}px 0 0`,
                        textAlign: "center",
                        lineHeight: 1,
                    }}>
                        For research purposes only. Not legal advice.
                    </p>
                </div>
            </StrictChatWrapper>
            </div>

            {/* ── Document preview panel — same flex:1, slides in alongside chat ── */}
            <AnimatePresence>
                {showPreview && (
                    <motion.div
                        initial={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {y: 0} : {opacity: 1, width: "50%"}}
                        exit={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
                        transition={{duration: 0.25, ease: [0.32, 0.72, 0, 1], ...(isMobile ? {type: "tween"} : {})}}
                        className={isStrict && !isMobile ? "v3-glass-elevated" : undefined}
                        style={{
                            ...(isMobile ? {
                                position: "fixed",
                                left: 0,
                                right: 0,
                                bottom: 0,
                                top: "8vh",
                                zIndex: 100,
                                borderRadius: "20px 20px 0 0",
                                willChange: "transform",
                                background: "var(--dt-panel-overlay-bg)",
                                backdropFilter: "var(--dt-glass-blur-light)",
                                WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                                border: "0.5px solid var(--dt-panel-border-color)",
                                boxShadow: "var(--dt-panel-shadow)",
                            } : {
                                flex: layoutMode === "source" ? 2 : layoutMode === "chat" ? 1 : 1,
                                position: "relative",
                                zIndex: 1,
                                flexShrink: 0,
                                ...makeGlassPanel(isStrict),
                            }),
                            display: "flex",
                            flexDirection: "column",
                            minHeight: 0,
                            minWidth: 0,
                            overflow: "clip",
                        }}
                    >
                        {/* Mobile drag handle */}
                        {isMobile && (
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: "var(--dt-text-quaternary)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                            borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: "var(--dt-glass-bg-subtle)",
                        }}>
              <span style={{
                  fontSize: TYPE_SCALE.sm, fontWeight: 600,
                  color: "var(--dt-text-tertiary)",
                  fontFamily: FONT.sans,
                  textTransform: "uppercase", letterSpacing: "0.10em"
              }}>
                Source Document
              </span>
                            <button
                                onClick={() => setPreviewIndex(null)}
                                style={{
                                    background: "var(--dt-glass-bg)",
                                    border: "0.5px solid var(--dt-glass-border)",
                                    cursor: "pointer",
                                    padding: isMobile ? SPACE['2'] : SPACE['1'],
                                    color: "var(--dt-text-tertiary)",
                                    borderRadius: RADIUS.md,
                                    display: "flex"
                                }}
                            >
                                <X size={14} strokeWidth={2}/>
                            </button>
                        </div>

                        {/* FakePdf fills remaining height */}
                        <div style={{flex: 1, padding: SPACE['4'], minHeight: 0, overflow: "hidden"}}>
                            <div style={{height: "100%", position: "relative"}}>
                                <FakePdf
                                    scenario={previewScenarios[previewIndex!]}
                                    showHighlights={true}
                                />
                            </div>
                        </div>

                        {/* Ask button */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['5']}px 80px` : `${SPACE['3']}px ${SPACE['5']}px ${SPACE['4']}px`,
                            borderTop: "0.5px solid var(--dt-glass-border)",
                            flexShrink: 0, background: "var(--dt-glass-bg-subtle)",
                        }}>
                            <button
                                onClick={() => onSend(presetQuestions[previewIndex!].full)}
                                style={{
                                    width: "100%", padding: SPACE['3'], borderRadius: RADIUS.xl,
                                    background: "var(--dt-preview-btn-bg)", color: "var(--dt-preview-btn-text)",
                                    border: "none", cursor: "pointer",
                                    fontSize: TYPE_SCALE.sm, fontWeight: 600,
                                    fontFamily: FONT.sans,
                                    boxShadow: "0 2px 12px var(--dt-preview-btn-shadow)",
                                    transition: `opacity ${TIMING.fast}`,
                                }}
                                onMouseEnter={e => (e.currentTarget.style.opacity = "0.88")}
                                onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
                            >
                                Ask this question →
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Strict overlay backdrop — dismiss on click-outside ── */}
            {isStrict && drawerOpen && (
                <div
                    onClick={() => setDrawerOpen(false)}
                    style={{position: "fixed", inset: 0, zIndex: 199, background: "rgba(0,0,0,0.4)"}}
                />
            )}

            {/* ── Source grounding panel ── */}
            {/* In Strict mode: centered overlay. Otherwise: flex sibling beside chat. */}
            <AnimatePresence>
                {drawerOpen && drawerData.sources.length > 0 && (
                    <motion.div
                        initial={isMobile ? {y: "100%"} : isStrict ? {opacity: 0, y: 16} : {opacity: 0, width: 0}}
                        animate={isMobile ? {y: 0} : isStrict ? {opacity: 1, y: 0} : {opacity: 1, width: "50%"}}
                        exit={isMobile ? {y: "100%"} : isStrict ? {opacity: 0, y: 16} : {opacity: 0, width: 0}}
                        transition={{duration: 0.25, ease: [0.32, 0.72, 0, 1], ...(isMobile ? {type: "tween"} : {})}}
                        style={{
                            ...(isMobile ? {
                                position: "fixed",
                                left: 0,
                                right: 0,
                                bottom: 0,
                                top: "8vh",
                                zIndex: 100,
                                borderRadius: "20px 20px 0 0",
                                willChange: "transform",
                                background: "var(--dt-panel-overlay-bg)",
                                backdropFilter: "var(--dt-glass-blur-light)",
                                WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                                border: "0.5px solid var(--dt-panel-border-color)",
                                boxShadow: "var(--dt-panel-shadow)",
                            } : isStrict ? {
                                // Strict: centered glass overlay — doesn't compress StrictLayout
                                position: "fixed",
                                left: "8%",
                                right: "8%",
                                top: "6%",
                                bottom: "6%",
                                zIndex: 200,
                                borderRadius: 16,
                                background: "var(--strict-glass-bg)",
                                backdropFilter: "var(--strict-glass-blur)",
                                WebkitBackdropFilter: "var(--strict-glass-blur)",
                                border: "1px solid var(--strict-glass-border)",
                                boxShadow: "var(--strict-glass-shadow)",
                                willChange: "transform, opacity",
                            } : {
                                flex: layoutMode === "source" ? 2 : layoutMode === "chat" ? 1 : 1,
                                position: "relative",
                                flexShrink: 0,
                                ...makeGlassPanel(false),
                            }),
                            display: "flex",
                            flexDirection: "column",
                            minHeight: 0,
                            minWidth: 0,
                            overflow: "clip",
                        }}
                    >
                        {/* Mobile drag handle */}
                        {isMobile && (
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: "var(--dt-text-quaternary)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                            borderBottom: isStrict ? "1px solid var(--strict-gold-border)" : "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isStrict ? "var(--strict-drawer-header-bg)" : "var(--dt-glass-bg-subtle)",
                        }}>
              <span style={{
                  fontSize: isStrict ? "var(--strict-label-size)" : TYPE_SCALE.sm,
                  fontWeight: isStrict ? 400 : 700,
                  textTransform: "uppercase",
                  letterSpacing: isStrict ? "var(--strict-label-tracking)" : "0.12em",
                  color: isStrict ? "var(--strict-gold-text)" : "var(--dt-accent-color)",
                  fontFamily: isStrict ? "system-ui" : FONT.sans,
              }}>
                Source Grounding
              </span>
                            <div style={{display: "flex", alignItems: "center", gap: SPACE['1']}}>
                                {/* Layout toggle buttons — hide on mobile and in Strict mode */}
                                {!isMobile && !isStrict && (["chat", "split", "source"] as const).map((mode) => (
                                    <button
                                        key={mode}
                                        onClick={() => setLayoutMode(mode)}
                                        title={mode === "chat" ? "Chat focused" : mode === "split" ? "Equal split" : "Sources focused"}
                                        style={{
                                            display: "flex", alignItems: "center", gap: 1,
                                            padding: `3px ${SPACE['1']}px`, borderRadius: RADIUS.sm,
                                            background: layoutMode === mode
                                                ? "var(--dt-accent-tint)"
                                                : "var(--dt-button-bg)",
                                            border: layoutMode === mode
                                                ? "0.5px solid var(--dt-accent-border-color)"
                                                : "0.5px solid var(--dt-glass-border-subtle)",
                                            cursor: "pointer",
                                            transition: `all ${TIMING.instant}`,
                                        }}
                                    >
                                        {/* Left rectangle (chat) */}
                                        <span style={{
                                            display: "block",
                                            width: mode === "chat" ? 10 : mode === "split" ? 7 : SPACE['1'],
                                            height: 10, borderRadius: 1.5,
                                            background: layoutMode === mode
                                                ? "var(--dt-color-gold-solid)"
                                                : "var(--dt-text-quaternary)",
                                            transition: `all ${TIMING.instant}`,
                                        }}/>
                                        {/* Right rectangle (sources) */}
                                        <span style={{
                                            display: "block",
                                            width: mode === "chat" ? SPACE['1'] : mode === "split" ? 7 : 10,
                                            height: 10, borderRadius: 1.5,
                                            background: layoutMode === mode
                                                ? "var(--dt-color-gold-solid)"
                                                : "var(--dt-text-quaternary)",
                                            transition: `all ${TIMING.instant}`,
                                        }}/>
                                    </button>
                                ))}
                                <button
                                    onClick={() => setDrawerOpen(false)}
                                    style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: isMobile ? 34 : 28, height: isMobile ? 34 : 28,
                                        borderRadius: RADIUS.md, marginLeft: SPACE['1'],
                                        background: "var(--dt-glass-bg)",
                                        border: "0.5px solid var(--dt-glass-border)",
                                        cursor: "pointer",
                                        color: "var(--dt-text-tertiary)",
                                    }}
                                >
                                    <X size={isMobile ? 16 : 14} strokeWidth={2}/>
                                </button>
                            </div>
                        </div>

                        {/* Grounding content */}
                        <div className="flex-1 overflow-hidden min-h-0">
                            <GroundingErrorBoundary onReset={() => setDrawerOpen(false)}>
                                <GroundingView answer={drawerData.answer} sources={drawerData.sources} isDark={isDark} isMobile={isMobile} focusDocId={drawerData.focusDocId} focusPage={drawerData.focusPage} focusSeq={drawerData.focusSeq}/>
                            </GroundingErrorBoundary>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Document Index panel — accumulated sources across conversation ── */}
            <AnimatePresence>
                {indexOpen && (
                    <motion.div
                        initial={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {y: 0} : {opacity: 1, width: 300}}
                        exit={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
                        transition={isMobile
                            ? {type: "spring", damping: 30, stiffness: 300}
                            : {duration: 0.25, ease: [0.32, 0.72, 0, 1]}
                        }
                        className={isStrict && !isMobile ? "v3-glass-elevated" : undefined}
                        style={{
                            display: "flex", flexDirection: "column",
                            minHeight: 0, flexShrink: 0,
                            overflow: "clip",
                            ...(isMobile ? {
                                position: "fixed",
                                left: 0,
                                right: 0,
                                bottom: 0,
                                top: "12vh",
                                zIndex: 100,
                                borderRadius: "20px 20px 0 0",
                                willChange: "transform",
                                background: "var(--dt-panel-overlay-bg)",
                                backdropFilter: "var(--dt-glass-blur-light)",
                                WebkitBackdropFilter: "var(--dt-glass-blur-light)",
                                border: "0.5px solid var(--dt-panel-border-color)",
                                boxShadow: "var(--dt-panel-shadow)",
                            } : makeGlassPanel(isStrict)),
                        }}
                    >
                        {/* Mobile drag handle */}
                        {isMobile && (
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: "var(--dt-text-quaternary)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['4']}px`,
                            borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: "var(--dt-glass-bg-subtle)",
                        }}>
                            <span style={{
                                fontSize: TYPE_SCALE.xs, fontWeight: 700, textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: "var(--dt-accent-color)",
                                fontFamily: FONT.sans,
                            }}>
                                Sources ({documentIndex.length})
                            </span>
                            <button
                                onClick={() => setIndexOpen(false)}
                                style={{
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    width: isMobile ? 34 : 28, height: isMobile ? 34 : 28,
                                    borderRadius: RADIUS.md,
                                    background: "var(--dt-glass-bg)",
                                    border: "0.5px solid var(--dt-glass-border)",
                                    cursor: "pointer",
                                    color: "var(--dt-text-tertiary)",
                                }}
                            >
                                <X size={isMobile ? 16 : 14} strokeWidth={2}/>
                            </button>
                        </div>

                        {/* Document index content */}
                        <DocumentIndex
                            entries={documentIndex}
                            isDark={isDark}
                            focusDocId={indexFocusDocId}
                            onEntryClick={(entry) => {
                                // Open the grounding drawer focused on this doc
                                const source = messages
                                    .flatMap(m => m.sources ?? [])
                                    .find(s => s.doc_id === entry.docId)
                                if (source) {
                                    handleSourceClick(
                                        "",
                                        messages.flatMap(m => m.sources ?? []).filter(s => s.doc_id === entry.docId),
                                        entry.docId,
                                        entry.pages[0],
                                    )
                                }
                            }}
                        />
                    </motion.div>
                )}
            </AnimatePresence>
        </div>
    )
}
