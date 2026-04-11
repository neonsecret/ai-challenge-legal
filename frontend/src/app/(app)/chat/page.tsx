"use client"

import {useRef, useEffect, useCallback, useState, Component, type ErrorInfo, type ReactNode} from "react"
import {createPortal} from "react-dom"
import {useRouter} from "next/navigation"
import {motion, AnimatePresence} from "motion/react"
import {V3_FADE_UP} from "@/lib/v3-motion"
import {useColorMode} from "@/lib/color-mode"
import {HistoryPanel} from "@/components/chat/history-panel"
import {ChatHeader} from "@/components/chat/chat-header"
import {ChatInput} from "@/components/chat/chat-input"
import {ChatMessage, type Source} from "@/components/chat/chat-message"
import {StrictSidebarRail} from "@/components/chat/strict-sidebar-rail"
import {SourcePanelV2} from "@/components/chat/source-panel-v2"
import {CollapsibleTurn} from "@/components/chat/collapsible-turn"
import {useChatState} from "@/components/chat/chat-state"
import {EmptyState, getPresetQuestions} from "@/components/chat/empty-state"
import {GroundingView} from "@/components/grounding/grounding-view"
import {FakePdf} from "@/components/landing/fake-pdf"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {type Jurisdiction} from "@/lib/jurisdictions"
import {useIsMobile} from "@/hooks/use-mobile"
import {useDocumentIndex} from "@/components/chat/use-document-index"
import {DocumentIndex} from "@/components/chat/document-index"
import {DocumentViewer} from "@/components/chat/document-viewer/DocumentViewer"
import {useDocumentState} from "@/hooks/use-document-state"
import {X} from "lucide-react"
import {FONT, TYPE_SCALE, SPACE, RADIUS, TIMING, EASE} from "@/lib/tokens"
import {PREVIEW_SCENARIOS_MAP} from "./scenarios"
import {MobileSourceSheet} from "@/components/chat/mobile-source-sheet"

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
    const {answer, sources, confidence, isStreaming, streamingStatus, streamingProgress, thinkingPreview, followUps, error, isDraftingMode, clearError, abort} = stream

    const [drawerOpen, setDrawerOpen] = useState(false)
    const [drawerData, setDrawerData] = useState<{ answer: string; sources: Source[]; focusDocId?: string; focusPage?: number; focusSeq: number }>({answer: "", sources: [], focusSeq: 0})
    const [previewIndex, setPreviewIndex] = useState<number | null>(null)
    const [historyOpen, setHistoryOpen] = useState(false)
    const [indexOpen, setIndexOpen] = useState(false)
    const [indexFocusDocId, setIndexFocusDocId] = useState<string | null>(null)
    const [lawPaneOpen, setLawPaneOpen] = useState(false)
    const [pendingTemplate, setPendingTemplate] = useState<{slug: string; name: string} | null>(null)
    const [documentViewerOpen, setDocumentViewerOpen] = useState(false)
    const [viewingDocId, setViewingDocId] = useState<string | null>(null)
    const [viewingDocName, setViewingDocName] = useState<string | undefined>(undefined)
    const docState = useDocumentState(currentSessionId)
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const longPressFiredRef = useRef(false)
    const corpusBlockedTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    /** 0-based pair index active when the current streaming query was sent. Used to anchor
     *  SSE-generated documents to the turn that created them (F2 — NEO-994). */
    const queryTurnIndexRef = useRef(0)
    /** Tracks user message count so onSend can read it without adding messages to its deps. */
    const userMsgCountRef = useRef(0)
    useEffect(() => {
        userMsgCountRef.current = messages.filter(m => m.role === "user").length
    }, [messages])
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
        if (!corpus) { setAvailableLaws([]); setLawPaneOpen(false); return } // eslint-disable-line react-hooks/set-state-in-effect
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

    // Sync SSE-delivered documents into docState, tagging each with the current turn index
    // so DocumentCard renders on the turn that created it rather than drifting to the latest.
    useEffect(() => {
        stream.documents.forEach(doc => docState.addDocument({...doc, turn_index: queryTurnIndexRef.current}))
    }, [stream.documents]) // eslint-disable-line react-hooks/exhaustive-deps

    const handleTemplateSelect = useCallback((template: {slug: string; name: string}) => {
        setPendingTemplate(template)
        inputFocusRef.current?.()
    }, [])

    const onSend = useCallback((question: string) => {
        setPreviewIndex(null)
        // Capture the turn index before handleSend adds the new user message.
        // userMsgCountRef tracks this without adding messages to the callback deps.
        queryTurnIndexRef.current = userMsgCountRef.current
        const slug = pendingTemplate?.slug
        setPendingTemplate(null)
        const result = handleSend(question, slug)
        if (result === "blocked") {
            showCorpusBlocked()
        }
        // "streaming" means previous query still running — silently ignore
    }, [handleSend, showCorpusBlocked, pendingTemplate])

    // Load custom corpus name and corpus warning preference from localStorage
    useEffect(() => {
        const storedName = localStorage.getItem("neolex_custom_corpus_name")
        if (storedName) setCustomCorpus(storedName) // eslint-disable-line react-hooks/set-state-in-effect
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
            fetchCorpora() // eslint-disable-line react-hooks/set-state-in-effect
        }
    }, [jurisdiction, fetchCorpora])

    // Reset preview when jurisdiction changes
    useEffect(() => {
        setPreviewIndex(null) // eslint-disable-line react-hooks/set-state-in-effect
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

    // Listen for sidebar rail custom events (bridge between layout-level sidebar and page-level state)
    useEffect(() => {
        const onHistoryToggle = () => setHistoryOpen(v => !v)
        const onNewChatEvent = () => { newChat(); setPreviewIndex(null) }
        const onDocIndexToggle = () => setIndexOpen(v => !v)
        window.addEventListener("vitreon:history-toggle", onHistoryToggle)
        window.addEventListener("vitreon:new-chat", onNewChatEvent)
        window.addEventListener("vitreon:doc-index-toggle", onDocIndexToggle)
        // Check for pending sidebar action from navigation (sessionStorage handoff)
        const pending = sessionStorage.getItem("vitreon:pending-action")
        if (pending) {
            sessionStorage.removeItem("vitreon:pending-action")
            if (pending === "history-toggle") setHistoryOpen(true) // eslint-disable-line react-hooks/set-state-in-effect
            else if (pending === "doc-index-toggle") setIndexOpen(true)
        }
        return () => {
            window.removeEventListener("vitreon:history-toggle", onHistoryToggle)
            window.removeEventListener("vitreon:new-chat", onNewChatEvent)
            window.removeEventListener("vitreon:doc-index-toggle", onDocIndexToggle)
        }
    }, [newChat])

    const previewScenarios = PREVIEW_SCENARIOS_MAP[jurisdiction] ?? []
    const presetQuestions = getPresetQuestions(jurisdiction)
    const showPreview = messages.length === 0 && previewIndex !== null && previewIndex < previewScenarios.length
    const lastAssistant = messages.at(-1)
    const showFollowUps = !isStreaming && lastAssistant?.role === "assistant" && lastAssistant.content

    return (
        <div className={isStrict ? undefined : "p-2 sm:p-4"} style={{
            height: "100%",
            display: "flex",
            alignItems: "stretch",
            gap: isStrict ? 0 : (isMobile ? 0 : SPACE['2']),
            overflow: "hidden",
            maxWidth: "100vw",
            position: "relative",
        }}>
            {/* ── History panel (left) — full-screen overlay on mobile ── */}
            <AnimatePresence>
                {historyOpen && (
                    <motion.div
                        initial={isMobile ? {x: "-100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {x: 0} : {opacity: 1, width: 280}}
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

            {/* ── Main content area ── */}
            {/* Dark mode: layout.tsx provides glass pane + sidebar rail, so we just render content */}
            {/* Light mode: we create our own glass pane */}
            <div className={isStrict ? undefined : "animate-glass-in"} style={{
                flex: 1,
                display: "flex",
                flexDirection: isStrict && !isMobile && drawerOpen && drawerData.sources.length > 0 ? "row" : "column",
                minHeight: 0,
                minWidth: 0,
                position: "relative",
                overflow: "hidden",
                contain: "style",
                transition: `border-color ${TIMING.slow} ${EASE.out}, box-shadow ${TIMING.slow} ${EASE.out}, background ${TIMING.slow} ${EASE.out}`,
                ...(isStrict ? {} : makeGlassPanel(false)),
            }}>
                {/* Reading area */}
                <div style={{flex: 1, display: "flex", flexDirection: "column", minHeight: 0, minWidth: 0, overflow: "hidden"}}>
                {/* TODO task 3.2 done: inline header replaced by ChatHeader component */}
                <ChatHeader
                    isStrict={isStrict}
                    isMobile={isMobile}
                    jurisdiction={jurisdiction}
                    currentCorpora={currentCorpora}
                    onSetJurisdiction={setJurisdiction}
                    useInternet={useInternet}
                    onToggleInternet={() => setUseInternet(prev => !prev)}
                    historyOpen={historyOpen}
                    onToggleHistory={() => setHistoryOpen(v => !v)}
                    indexOpen={indexOpen}
                    onToggleIndex={() => setIndexOpen(v => !v)}
                    documentIndexCount={documentIndex.length}
                    hasMessages={messages.length > 0}
                    onNewChat={newChat}
                    onSetPreviewIndex={setPreviewIndex}
                    availableLaws={availableLaws}
                    selectedLaws={selectedLaws}
                    onSetSelectedLaws={setSelectedLaws}
                    lawPaneOpen={lawPaneOpen}
                    onSetLawPaneOpen={setLawPaneOpen}
                    corpusWarning={corpusWarning}
                    onSetCorpusWarning={setCorpusWarning}
                    hideCorpusWarning={hideCorpusWarning}
                    onSetHideCorpusWarning={setHideCorpusWarning}
                    corpusBlocked={corpusBlocked}
                    onSetCorpusBlocked={setCorpusBlocked}
                    showCorpusBlocked={showCorpusBlocked}
                    availableCorpora={availableCorpora}
                    corporaLoading={corporaLoading}
                    documentCount={docState.count}
                />
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
                        // Group flat message list into user+assistant pairs for CollapsibleTurn
                        (() => {
                            type Msg = typeof messages[0]
                            const pairs: Array<{user: Msg; assistant: Msg | null}> = []
                            for (let i = 0; i < messages.length; i++) {
                                if (messages[i].role === "user") {
                                    const asst = messages[i + 1]?.role === "assistant" ? messages[i + 1] : null
                                    pairs.push({user: messages[i], assistant: asst})
                                    if (asst) i++
                                }
                            }
                            return pairs.map((pair, pairIdx) => {
                                const isLatestPair = pairIdx === pairs.length - 1
                                return (
                                    <CollapsibleTurn
                                        key={pair.user.id}
                                        question={pair.user.content ?? ""}
                                        sourceCount={pair.assistant?.sources?.length ?? 0}
                                        isLatest={isLatestPair}
                                    >
                                        <motion.div
                                            variants={isStrict ? V3_FADE_UP : undefined}
                                            initial={isStrict ? "hidden" : {opacity: 0, y: SPACE['3']}}
                                            animate={isStrict ? "visible" : {opacity: 1, y: 0}}
                                            transition={isStrict ? undefined : {duration: 0.2, ease: [0.32, 0.72, 0, 1]}}
                                        >
                                            <ChatMessage
                                                role="user"
                                                content={pair.user.content}
                                                isDark={isDark}
                                                isStrict={isStrict}
                                            />
                                        </motion.div>
                                        {pair.assistant && (
                                            <motion.div
                                                ref={isLatestPair ? lastAssistantRef : undefined}
                                                variants={isStrict ? V3_FADE_UP : undefined}
                                                initial={isStrict ? "hidden" : {opacity: 0, y: SPACE['3']}}
                                                animate={isStrict ? "visible" : {opacity: 1, y: 0}}
                                                transition={isStrict ? undefined : {type: "spring", damping: 25, stiffness: 200}}
                                            >
                                                <ChatMessage
                                                    role="assistant"
                                                    content={pair.assistant.content}
                                                    sources={pair.assistant.sources}
                                                    confidence={pair.assistant.confidence}
                                                    isStreaming={isStreaming && pair.assistant.id === activeAssistantId.current}
                                                    streamingStatus={isStreaming && pair.assistant.id === activeAssistantId.current ? streamingStatus : null}
                                                    streamingProgress={isStreaming && pair.assistant.id === activeAssistantId.current ? streamingProgress : null}
                                                    streamingThinkingPreview={isStreaming && pair.assistant.id === activeAssistantId.current ? thinkingPreview : null}
                                                    trace={pair.assistant.trace}
                                                    onSourceClick={handleSourceClick}
                                                    onAbort={abort}
                                                    isDark={isDark}
                                                    isStrict={isStrict}
                                                    messageId={pair.assistant.id}
                                                    traceId={pair.assistant.traceId}
                                                    conversationId={currentSessionId}
                                                    feedback={pair.assistant.feedback}
                                                    onFeedback={setMessageFeedback}
                                                    documents={docState.documents.filter(d =>
                                                        d.turn_index !== undefined ? d.turn_index === pairIdx : isLatestPair
                                                    )}
                                                    chatId={currentSessionId ?? undefined}
                                                    onDocumentPreview={(docId) => {
                                                        const doc = docState.documents.find(d => d.doc_id === docId)
                                                        setViewingDocId(docId)
                                                        setViewingDocName(doc?.template_name)
                                                        setDocumentViewerOpen(true)
                                                    }}
                                                    isDraftingMode={isLatestPair && isStreaming && pair.assistant.id === activeAssistantId.current && isDraftingMode}
                                                />
                                            </motion.div>
                                        )}
                                    </CollapsibleTurn>
                                )
                            })
                        })()
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
                    padding: isMobile ? `${SPACE['3']}px ${SPACE['3']}px env(safe-area-inset-bottom, ${SPACE['5']}px)` : `${SPACE['3']}px ${SPACE['6']}px ${SPACE['4']}px`,
                    borderTop: isStrict ? "1px solid var(--strict-footer-border)" : "0.5px solid var(--dt-glass-border)",
                    flexShrink: 0,
                    background: isStrict ? "var(--strict-footer-bg)" : "var(--dt-glass-bg-subtle)",
                }}>
                    <ChatInput
                        onSend={onSend}
                        disabled={isStreaming}
                        onFocusRef={inputFocusRef}
                        onTemplateSelect={handleTemplateSelect}
                        documentCount={docState.count}
                        pendingTemplate={pendingTemplate}
                        onClearTemplate={() => setPendingTemplate(null)}
                    />
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
                </div>{/* end reading area */}

                {/* Source panel — dark mode desktop: slides in at 42% on citation click */}
                <AnimatePresence>
                    {isStrict && !isMobile && drawerOpen && drawerData.sources.length > 0 && (
                        <SourcePanelV2
                            sources={drawerData.sources}
                            initialIndex={0}
                            onClose={() => setDrawerOpen(false)}
                        />
                    )}
                </AnimatePresence>
            </div>{/* end main glass pane */}

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
                            borderBottom: isStrict ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: isStrict ? "transparent" : "var(--dt-glass-bg-subtle)",
                        }}>
              <span style={{
                  fontSize: isStrict ? 9 : TYPE_SCALE.sm,
                  fontWeight: isStrict ? 400 : 600,
                  color: isStrict ? "rgba(201,168,76,0.4)" : "var(--dt-text-tertiary)",
                  fontFamily: isStrict ? "system-ui" : FONT.sans,
                  textTransform: "uppercase",
                  letterSpacing: isStrict ? "1.2px" : "0.10em",
              }}>
                Source Document
              </span>
                            <button
                                onClick={() => setPreviewIndex(null)}
                                style={{
                                    background: isStrict ? "rgba(201,168,76,0.04)" : "var(--dt-glass-bg)",
                                    border: isStrict ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border)",
                                    cursor: "pointer",
                                    padding: isMobile ? SPACE['2'] : SPACE['1'],
                                    color: isStrict ? "rgba(201,168,76,0.5)" : "var(--dt-text-tertiary)",
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
                                    isDark={isStrict}
                                />
                            </div>
                        </div>

                        {/* Ask button */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['5']}px 80px` : `${SPACE['3']}px ${SPACE['5']}px ${SPACE['4']}px`,
                            borderTop: isStrict ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border)",
                            flexShrink: 0, background: isStrict ? "transparent" : "var(--dt-glass-bg-subtle)",
                        }}>
                            <button
                                onClick={() => onSend(presetQuestions[previewIndex!].full)}
                                style={isStrict ? {
                                    width: "100%", padding: 10, borderRadius: 8,
                                    background: "rgba(255,255,255,0.025)",
                                    color: "rgba(230,235,245,0.88)",
                                    border: "1px solid rgba(255,255,255,0.04)",
                                    borderBottom: "1px solid rgba(201,168,76,0.3)",
                                    cursor: "pointer",
                                    fontSize: 10, fontWeight: 400,
                                    fontFamily: "system-ui",
                                    boxShadow: "none",
                                    opacity: 0.7,
                                    transition: `opacity ${TIMING.fast}, border-color ${TIMING.fast}`,
                                } : {
                                    width: "100%", padding: SPACE['3'], borderRadius: RADIUS.xl,
                                    background: "var(--dt-preview-btn-bg)", color: "var(--dt-preview-btn-text)",
                                    border: "none", cursor: "pointer",
                                    fontSize: TYPE_SCALE.sm, fontWeight: 600,
                                    fontFamily: FONT.sans,
                                    boxShadow: "0 2px 12px var(--dt-preview-btn-shadow)",
                                    transition: `opacity ${TIMING.fast}`,
                                }}
                                onMouseEnter={e => {
                                    if (isStrict) {
                                        e.currentTarget.style.opacity = "1";
                                        e.currentTarget.style.borderBottomColor = "rgba(201,168,76,0.5)";
                                    } else {
                                        e.currentTarget.style.opacity = "0.88";
                                    }
                                }}
                                onMouseLeave={e => {
                                    if (isStrict) {
                                        e.currentTarget.style.opacity = "0.7";
                                        e.currentTarget.style.borderBottomColor = "rgba(201,168,76,0.3)";
                                    } else {
                                        e.currentTarget.style.opacity = "1";
                                    }
                                }}
                            >
                                Ask this question →
                            </button>
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* ── Mobile dark mode source bottom sheet — portaled to escape glass pane stacking context ── */}
            {isMobile && isStrict && drawerOpen && drawerData.sources.length > 0 && typeof document !== "undefined" && createPortal(
                <MobileSourceSheet
                    sources={drawerData.sources}
                    answer={drawerData.answer}
                    focusDocId={drawerData.focusDocId}
                    focusPage={drawerData.focusPage}
                    focusSeq={drawerData.focusSeq}
                    onClose={() => setDrawerOpen(false)}
                />,
                document.body,
            )}

            {/* ── Source grounding panel ── */}
            {/* Strict desktop: handled by SourcePanelV2 inside main pane (above). */}
            {/* Strict mobile: handled by MobileSourceSheet (above). */}
            {/* Light mode: flex sibling beside chat (below). */}
            <AnimatePresence>
                {drawerOpen && drawerData.sources.length > 0 && !isStrict && (
                    <motion.div
                        initial={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {y: 0} : {opacity: 1, width: "50%"}}
                        exit={isMobile ? {y: "100%"} : {opacity: 0, width: 0}}
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
                        {/* Panel header — light mode only (strict uses SourcePanelV2) */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                            borderBottom: "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: "var(--dt-glass-bg-subtle)",
                        }}>
              <span style={{
                  fontSize: TYPE_SCALE.sm,
                  fontWeight: 700,
                  textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: "var(--dt-accent-color)",
                  fontFamily: FONT.sans,
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
                        animate={isMobile ? {y: 0} : {opacity: 1, width: 280}}
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
                            borderBottom: isStrict ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border-subtle)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isStrict ? "linear-gradient(180deg, rgba(255,255,255,0.015) 0%, transparent 100%)" : "var(--dt-glass-bg-subtle)",
                        }}>
                            <span style={{
                                fontSize: isStrict ? 9 : TYPE_SCALE.xs,
                                fontWeight: isStrict ? 400 : 700,
                                textTransform: "uppercase",
                                letterSpacing: isStrict ? "1.2px" : "0.12em",
                                color: isStrict ? "rgba(201,168,76,0.4)" : "var(--dt-accent-color)",
                                fontFamily: isStrict ? "system-ui" : FONT.sans,
                            }}>
                                Sources ({documentIndex.length})
                            </span>
                            <button
                                onClick={() => setIndexOpen(false)}
                                style={{
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    width: isMobile ? 34 : 28, height: isMobile ? 34 : 28,
                                    borderRadius: RADIUS.md,
                                    background: isStrict ? "rgba(201,168,76,0.04)" : "var(--dt-glass-bg)",
                                    border: isStrict ? "1px solid rgba(201,168,76,0.06)" : "0.5px solid var(--dt-glass-border)",
                                    cursor: "pointer",
                                    color: isStrict ? "rgba(201,168,76,0.5)" : "var(--dt-text-tertiary)",
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

            {/* ── Document Viewer — PDF preview panel for drafted documents ── */}
            <DocumentViewer
                open={documentViewerOpen}
                onClose={() => setDocumentViewerOpen(false)}
                onAskToModify={() => { setDocumentViewerOpen(false); inputFocusRef.current?.() }}
                chatId={currentSessionId ?? ""}
                docId={viewingDocId}
                docName={viewingDocName}
            />
        </div>
    )
}
