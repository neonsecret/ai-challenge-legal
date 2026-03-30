"use client"

import {useRef, useEffect, useCallback, useState, Component, type ErrorInfo, type ReactNode} from "react"
import {useRouter} from "next/navigation"
import {motion, AnimatePresence} from "motion/react"
import {SquarePen, History, Trash2, BookOpen, Globe} from "lucide-react"
import {useTheme} from "next-themes"
import {ChatInput} from "@/components/chat/chat-input"
import {ChatMessage, type Source} from "@/components/chat/chat-message"
import {useChatState} from "@/components/chat/chat-state"
import {EmptyState, getPresetQuestions} from "@/components/chat/empty-state"
import {GroundingView} from "@/components/grounding/grounding-view"
import {FakePdf} from "@/components/landing/fake-pdf"
import type {DemoScenario} from "@/components/landing/demo-panel"
import {useJurisdiction} from "@/lib/use-jurisdiction"
import {JURISDICTIONS, JURISDICTION_ORDER, jurisdictionToCorpus, type Jurisdiction} from "@/lib/jurisdictions"
import {useIsMobile} from "@/hooks/use-mobile"
import {useDocumentIndex} from "@/components/chat/use-document-index"
import {DocumentIndex} from "@/components/chat/document-index"
import {X} from "lucide-react"

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
        // Auto-recover once after 500ms — enough for worker cleanup to finish.
        // Won't loop: retried flag prevents a second reset.
        if (!this.state.retried) {
            setTimeout(() => this.setState({error: null, retried: true}), 500)
        }
    }
    render() {
        if (this.state.error) return null
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

// Scenarios for the side-panel document viewer, keyed by jurisdiction
const DIFC_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "DIFC",
        question: "What is the limitation period under DIFC Law No. 5 of 2005?",
        answer: "",
        pdfTitle: "DIFC Limitation Law No. 5 of 2005",
        pdfArticleHeader: "Article 4 — General Limitation Period",
        pdfClauses: [
            {
                id: "4(1)",
                text: "An action founded on contract shall not be brought after the end of six years beginning with the date on which the cause of action accrued."
            },
            {
                id: "4(2)",
                text: "An action in tort shall not be brought after three years beginning with the date on which the claimant first had knowledge of all relevant facts."
            },
            {
                id: "4(3)",
                text: "Knowledge includes facts which a claimant might reasonably be expected to acquire from observable facts or from expert advice."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "DIFC Law No. 5 of 2005 · Art. 4 · p.12",
        pageBadge: "Page 12",
    },
    {
        jurisdiction: "DIFC",
        question: "What are the grounds for termination under DIFC Employment Law?",
        answer: "",
        pdfTitle: "DIFC Employment Law No. 2 of 2019",
        pdfArticleHeader: "Article 59 — Termination by Employer",
        pdfClauses: [
            {
                id: "59(1)",
                text: "An employer may terminate without notice where the employee has committed a fundamental breach of the employment contract."
            },
            {
                id: "59(2)",
                text: "An employer may terminate for cause by providing written notice of not less than the minimum notice period, setting out the grounds."
            },
            {
                id: "59(3)",
                text: "Termination shall not be on grounds related to pregnancy, maternity leave, or the exercise of any statutory right."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "DIFC Employment Law · Art. 59 · p.31",
        pageBadge: "Page 31",
    },
]

const CZ_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "Czech Republic",
        question: "Jaká je výpovědní doba podle zákoníku práce?",
        answer: "",
        pdfTitle: "Zákoník práce (262/2006 Sb.)",
        pdfArticleHeader: "§ 51 — Výpovědní doba",
        pdfClauses: [
            {
                id: "§51(1)",
                text: "Byla-li dána výpověď, skončí pracovní poměr uplynutím výpovědní doby. Výpovědní doba musí být stejná pro zaměstnavatele i zaměstnance."
            },
            {id: "§51(2)", text: "Výpovědní doba činí nejméně 2 měsíce."},
            {
                id: "§51(3)",
                text: "Výpovědní doba začíná prvním dnem kalendářního měsíce následujícího po doručení výpovědi."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Zákoník práce · § 51 · p.51",
        pageBadge: "Page 51",
    },
    {
        jurisdiction: "Czech Republic",
        question: "Jak je upraveno bezdůvodné obohacení v občanském zákoníku?",
        answer: "",
        pdfTitle: "Občanský zákoník (89/2012 Sb.)",
        pdfArticleHeader: "§ 2991 — Bezdůvodné obohacení",
        pdfClauses: [
            {
                id: "§2991(1)",
                text: "Kdo se na úkor jiného bez spravedlivého důvodu obohatí, musí ochuzenému vydat, oč se obohatil."
            },
            {
                id: "§2991(2)",
                text: "Bezdůvodně se obohatí zvláště ten, kdo získá majetkový prospěch plněním bez právního důvodu, plněním z právního důvodu, který odpadl, nebo protiprávním užitím cizí hodnoty."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Občanský zákoník · § 2991 · p.195",
        pageBadge: "Page 195",
    },
]

const PREVIEW_SCENARIOS_MAP: Record<string, DemoScenario[]> = {
    difc: DIFC_SCENARIOS,
    cz: CZ_SCENARIOS,
}

function makeGlassPanel(isDark: boolean) {
    return isDark ? {
        background: "rgba(255,255,255,0.07)",
        backdropFilter: "blur(40px) saturate(180%) brightness(108%)",
        WebkitBackdropFilter: "blur(40px) saturate(180%) brightness(108%)",
        border: "0.5px solid rgba(255,255,255,0.14)",
        borderRadius: "24px",
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.10), 0 20px 60px rgba(0,0,0,0.40)",
        willChange: "transform",
        transform: "translateZ(0)",
    } : {
        background: "rgba(255,252,242,0.18)",
        backdropFilter: "blur(40px) saturate(160%) brightness(106%)",
        WebkitBackdropFilter: "blur(40px) saturate(160%) brightness(106%)",
        border: "0.5px solid rgba(255,255,255,0.55)",
        borderRadius: "24px",
        boxShadow: "inset 0 1.5px 0 rgba(255,255,255,0.85), inset 1px 0 0 rgba(255,255,255,0.30), 0 16px 48px rgba(100,50,0,0.12)",
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
    } = useChatState()
    const {jurisdiction, setJurisdiction} = useJurisdiction()
    const {answer, sources, confidence, isStreaming, streamingStatus, error, clearError} = stream

    const [drawerOpen, setDrawerOpen] = useState(false)
    const [drawerData, setDrawerData] = useState<{ answer: string; sources: Source[]; focusDocId?: string; focusPage?: number; focusSeq: number }>({answer: "", sources: [], focusSeq: 0})
    const [previewIndex, setPreviewIndex] = useState<number | null>(null)
    const [historyOpen, setHistoryOpen] = useState(false)
    const [indexOpen, setIndexOpen] = useState(false)
    const [indexFocusDocId, setIndexFocusDocId] = useState<string | null>(null)
    const [lawPaneOpen, setLawPaneOpen] = useState(false)
    const longPressTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
    const longPressFiredRef = useRef(false)
    const [layoutMode, setLayoutMode] = useState<"chat" | "split" | "source">("split")
    const [customCorpus, setCustomCorpus] = useState("")
    const [corpusWarning, setCorpusWarning] = useState<{corpus: string, jurisdiction: Jurisdiction} | null>(null)
    const [corpusBlocked, setCorpusBlocked] = useState(false)
    const [hideCorpusWarning, setHideCorpusWarning] = useState(false)
    const customInputRef = useRef<HTMLInputElement>(null)
    const {resolvedTheme} = useTheme()
    const [mounted, setMounted] = useState(false)
    useEffect(() => setMounted(true), [])
    const isDark = mounted && resolvedTheme === "dark"
    const isMobile = useIsMobile()
    const documentIndex = useDocumentIndex(messages)

    // Czech law selector: fetch available laws from backend (cached)
    const [availableLaws, setAvailableLaws] = useState<{id: string; name: string; name_en: string}[]>([])
    useEffect(() => {
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        fetch(`${sseBase}/api/v1/laws`)
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                if (data?.laws) {
                    setAvailableLaws(data.laws)
                    // Default: all laws selected (visually active)
                    if (selectedLaws.length === 0) {
                        setSelectedLaws(data.laws.map((l: {id: string}) => l.id))
                    }
                }
            })
            .catch(() => {})
    }, [])

    const scrollAreaRef = useRef<HTMLDivElement>(null)
    const inputFocusRef = useRef<(() => void) | null>(null)

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

    const onSend = useCallback((question: string) => {
        setPreviewIndex(null)
        const result = handleSend(question)
        if (result === "blocked") {
            setCorpusBlocked(true)
            setTimeout(() => setCorpusBlocked(false), 4000)
        }
    }, [handleSend])

    // Load custom corpus name and corpus warning preference from localStorage
    useEffect(() => {
        const stored = localStorage.getItem("neolex_custom_corpus")
        if (stored) setCustomCorpus(stored)
        setHideCorpusWarning(localStorage.getItem("neolex_hide_corpus_warning") === "1")
    }, [])

    // Auto-focus custom input when switching to custom jurisdiction
    useEffect(() => {
        if (jurisdiction === "custom") {
            setTimeout(() => customInputRef.current?.focus(), 50)
        }
    }, [jurisdiction])

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

    // Auto-scroll
    useEffect(() => {
        if (scrollAreaRef.current) scrollAreaRef.current.scrollTop = scrollAreaRef.current.scrollHeight
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

    const previewScenarios = PREVIEW_SCENARIOS_MAP[jurisdiction] ?? DIFC_SCENARIOS
    const presetQuestions = getPresetQuestions(jurisdiction)
    const showPreview = messages.length === 0 && previewIndex !== null && previewIndex < previewScenarios.length
    const lastAssistant = messages.at(-1)
    const showFollowUps = !isStreaming && lastAssistant?.role === "assistant" && lastAssistant.content

    return (
        <div className="p-2 sm:p-4" style={{
            height: "100%",
            display: "flex",
            alignItems: "stretch",
            gap: isMobile ? "0px" : "8px",
            overflow: "hidden",
            maxWidth: "100vw",
            position: "relative",
        }}>
            {/* ── History panel (left) — full-screen overlay on mobile ── */}
            <AnimatePresence>
                {historyOpen && (
                    <motion.div
                        initial={isMobile ? {x: "-100%"} : {opacity: 0, width: 0}}
                        animate={isMobile ? {x: 0} : {opacity: 1, width: 260}}
                        exit={isMobile ? {x: "-100%"} : {opacity: 0, width: 0}}
                        transition={isMobile ? {type: "spring", damping: 30, stiffness: 300} : {duration: 0.25, ease: [0.32, 0.72, 0, 1]}}
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
                                background: isDark ? "rgba(15,22,35,0.60)" : "rgba(255,250,235,0.45)",
                                backdropFilter: "blur(60px) saturate(200%) brightness(110%)",
                                WebkitBackdropFilter: "blur(60px) saturate(200%) brightness(110%)",
                                boxShadow: isDark ? "inset 0 1px 0 rgba(255,255,255,0.12)" : "inset 0 1.5px 0 rgba(255,255,255,0.75)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                            } : makeGlassPanel(isDark)),
                        }}
                    >
                        {/* History header */}
                        <div style={{
                            padding: isMobile ? "16px 16px" : "14px 16px",
                            paddingTop: isMobile ? "max(16px, env(safe-area-inset-top))" : "14px",
                            borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.06)",
                        }}>
              <span style={{
                  fontSize: 11, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.50)",
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              }}>Chats</span>
                            <div style={{display: "flex", alignItems: "center", gap: 6}}>
                            <button onClick={() => {
                                newChat();
                                setHistoryOpen(false)
                            }} title="New chat" style={{
                                display: "flex", alignItems: "center", gap: 4,
                                padding: "4px 8px", borderRadius: 7, fontSize: 11, fontWeight: 500,
                                background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.22)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.45)",
                                color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                                cursor: "pointer", transition: "all 0.12s",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}>
                                <SquarePen size={11} strokeWidth={1.8}/>
                                New
                            </button>
                            {isMobile && (
                                <button
                                    onClick={() => setHistoryOpen(false)}
                                    title="Close"
                                    style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: 28, height: 28, borderRadius: 8,
                                        background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                                        border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                                        cursor: "pointer",
                                        color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
                                    }}
                                >
                                    <X size={14} strokeWidth={2}/>
                                </button>
                            )}
                            </div>
                        </div>
                        {/* Sessions list */}
                        <div style={{flex: 1, overflowY: "auto", padding: "8px"}}>
                            {sessions.length === 0 ? (
                                <p style={{
                                    fontSize: 12, textAlign: "center", padding: "24px 12px",
                                    color: isDark ? "rgba(255,255,255,0.28)" : "rgba(46,31,8,0.35)",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                }}>No chats yet</p>
                            ) : (
                                sessions.map((s) => {
                                    const isActive = s.id === currentSessionId
                                    return (
                                        <div
                                            key={s.id}
                                            style={{position: "relative", marginBottom: 2}}
                                            className="group"
                                        >
                                            <button
                                                onClick={() => { loadSession(s.id); if (isMobile) setHistoryOpen(false) }}
                                                style={{
                                                    display: "block", width: "100%", textAlign: "left",
                                                    padding: "9px 30px 9px 10px", borderRadius: 10,
                                                    fontSize: 12.5,
                                                    color: isActive
                                                        ? isDark ? "rgba(255,255,255,0.92)" : "#1a0e04"
                                                        : isDark ? "rgba(255,255,255,0.65)" : "rgba(46,31,8,0.68)",
                                                    background: isActive
                                                        ? isDark ? "rgba(201,168,76,0.14)" : "rgba(255,255,255,0.38)"
                                                        : "transparent",
                                                    border: isActive
                                                        ? isDark ? "0.5px solid rgba(201,168,76,0.28)" : "0.5px solid rgba(255,255,255,0.60)"
                                                        : "0.5px solid transparent",
                                                    cursor: "pointer",
                                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                                    transition: "background 0.12s, border-color 0.12s, box-shadow 0.12s, color 0.12s",
                                                    fontWeight: isActive ? 600 : 400,
                                                }}
                                                onMouseEnter={e => {
                                                    if (!isActive) {
                                                        e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.28)"
                                                        e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.50)"
                                                        e.currentTarget.style.boxShadow = isDark
                                                            ? "inset 0 1px 0 rgba(255,255,255,0.06), 0 2px 8px rgba(0,0,0,0.15)"
                                                            : "inset 0 1px 0 rgba(255,255,255,0.60), 0 2px 8px rgba(100,50,0,0.08)"
                                                        e.currentTarget.style.backdropFilter = "blur(12px) saturate(140%)"
                                                    }
                                                }}
                                                onMouseLeave={e => {
                                                    if (!isActive) {
                                                        e.currentTarget.style.background = "transparent"
                                                        e.currentTarget.style.borderColor = "transparent"
                                                        e.currentTarget.style.boxShadow = "none"
                                                        e.currentTarget.style.backdropFilter = "none"
                                                    }
                                                }}
                                            >
                                                {s.title}
                                            </button>
                                            <button
                                                onPointerDown={(e) => {
                                                    e.stopPropagation()
                                                    e.preventDefault()
                                                }}
                                                onMouseDown={(e) => {
                                                    e.stopPropagation()
                                                }}
                                                onClick={(e) => {
                                                    e.preventDefault()
                                                    e.stopPropagation()
                                                    deleteSession(s.id)
                                                }}
                                                title="Delete chat"
                                                className="opacity-0 group-hover:opacity-100 no-press-scale"
                                                style={{
                                                    position: "absolute",
                                                    right: 6,
                                                    top: "50%",
                                                    /* Negate the global button:active scale by always including translateY centering */
                                                    transform: "translateY(-50%)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    width: 22,
                                                    height: 22,
                                                    borderRadius: 6,
                                                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.45)",
                                                    cursor: "pointer",
                                                    color: isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.40)",
                                                    transition: "opacity 0.12s, background 0.12s, color 0.12s",
                                                    padding: 0,
                                                    zIndex: 1,
                                                    flexShrink: 0,
                                                }}
                                                onMouseEnter={e => {
                                                    e.currentTarget.style.background = isDark ? "rgba(255,80,60,0.18)" : "rgba(200,50,30,0.12)"
                                                    e.currentTarget.style.color = isDark ? "rgba(255,120,100,0.90)" : "rgba(180,40,20,0.80)"
                                                }}
                                                onMouseLeave={e => {
                                                    e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)"
                                                    e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.40)" : "rgba(46,31,8,0.40)"
                                                }}
                                            >
                                                <Trash2 size={11} strokeWidth={1.8}/>
                                            </button>
                                        </div>
                                    )
                                })
                            )}
                        </div>
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
                overflow: "clip",
                contain: "layout style",
                transition: "all 0.3s cubic-bezier(0.32, 0.72, 0, 1)",
                ...makeGlassPanel(isDark),
            }}>
                {/* Header */}
                <div style={{
                    padding: isMobile ? "10px 12px" : "14px 22px",
                    borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
                    display: "flex", alignItems: "center", gap: isMobile ? "6px" : "10px", flexShrink: 0,
                    background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.06)",
                }}>
                    <div style={{
                        width: isMobile ? 26 : 30, height: isMobile ? 26 : 30, borderRadius: isMobile ? 7 : 9,
                        background: isDark ? "rgba(201,168,76,0.14)" : "rgba(196,124,0,0.18)",
                        border: isDark ? "0.5px solid rgba(201,168,76,0.28)" : "0.5px solid rgba(196,124,0,0.38)",
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.65)",
                    }}>
            <span style={{
                fontSize: isMobile ? "13px" : "15px", fontWeight: 700, color: isDark ? "#C9A84C" : "#7a4a00", lineHeight: 1,
                fontFamily: "Georgia, serif"
            }}>N</span>
                    </div>
                    {!isMobile && <span style={{
                        fontWeight: 700, fontSize: "15px", color: isDark ? "rgba(255,255,255,0.90)" : "#1a0e04",
                        fontFamily: "Georgia, 'Times New Roman', serif", letterSpacing: "-0.04em"
                    }}>
            Vitreon Legal
          </span>}
                    {/* Jurisdiction selector pills */}
                    <div style={{
                        flex: 1,
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 2 : 3,
                        marginLeft: isMobile ? 4 : 12,
                        overflowX: "auto",
                        minWidth: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                    }}>
                        {(["difc", "cz", "eu", "uk", "us", "au", "custom"] as Jurisdiction[]).map((key) => {
                            const config = JURISDICTIONS[key]
                            const isActive = jurisdiction === key
                            const isEnabled = key === "difc" || key === "cz" || key === "custom"
                            const accentColor = "#d4af37"
                            const hasLawPane = key === "cz" && availableLaws.length > 0
                            return (
                                <button
                                    key={key}
                                    disabled={!isEnabled}
                                    onClick={() => {
                                        if (longPressFiredRef.current) {
                                            longPressFiredRef.current = false
                                            return
                                        }
                                        if (!isEnabled) return

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
                                            setCorpusBlocked(true)
                                            setTimeout(() => setCorpusBlocked(false), 4000)
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
                                            e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.24)"
                                            e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.20)" : "rgba(255,255,255,0.45)"
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.transform = "scale(1)"
                                        if (!isActive && isEnabled) {
                                            e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)"
                                            e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.12)" : "rgba(255,255,255,0.32)"
                                        }
                                    }}
                                    style={{
                                        fontSize: isMobile ? 9 : 10, fontWeight: isActive ? 700 : 500,
                                        padding: isMobile ? "2px 6px" : "3px 8px", borderRadius: 6,
                                        cursor: isEnabled ? "pointer" : "not-allowed",
                                        opacity: isEnabled ? 1 : 0.38,
                                        background: isActive
                                            ? isDark ? "rgba(201,168,76,0.75)" : "rgba(196,124,0,0.65)"
                                            : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)",
                                        border: isActive
                                            ? isDark ? "0.5px solid rgba(201,168,76,0.80)" : "0.5px solid rgba(196,124,0,0.75)"
                                            : isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.32)",
                                        color: isActive
                                            ? "rgba(255,255,255,0.95)"
                                            : isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                        transition: "all 0.15s cubic-bezier(0.34, 1.56, 0.64, 1)",
                                        whiteSpace: "nowrap",
                                        userSelect: "none",
                                        WebkitUserSelect: "none",
                                    }}
                                >
                                    {config.name}
                                </button>
                            )
                        })}
                        {/* Custom corpus name input — visible when "Custom" is selected */}
                        {jurisdiction === "custom" && (
                            <input
                                ref={customInputRef}
                                type="text"
                                value={customCorpus}
                                placeholder="difc"
                                maxLength={40}
                                onChange={(e) => {
                                    const val = e.target.value
                                    setCustomCorpus(val)
                                }}
                                onBlur={() => {
                                    const val = customCorpus.trim() || "difc"
                                    setCustomCorpus(val)
                                    localStorage.setItem("neolex_custom_corpus", val)
                                }}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter") {
                                        const val = customCorpus.trim() || "difc"
                                        setCustomCorpus(val)
                                        localStorage.setItem("neolex_custom_corpus", val)
                                        ;(e.target as HTMLInputElement).blur()
                                    }
                                }}
                                style={{
                                    fontSize: isMobile ? 9 : 10,
                                    fontWeight: 500,
                                    padding: isMobile ? "2px 6px" : "3px 8px",
                                    borderRadius: 6,
                                    maxWidth: 120,
                                    minWidth: 60,
                                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.22)",
                                    border: isDark ? "0.5px solid rgba(201,168,76,0.35)" : "0.5px solid rgba(212,175,55,0.45)",
                                    color: isDark ? "rgba(255,255,255,0.80)" : "rgba(46,31,8,0.75)",
                                    outline: "none",
                                    fontFamily: "monospace",
                                    backdropFilter: "blur(8px)",
                                    WebkitBackdropFilter: "blur(8px)",
                                    transition: "all 0.15s cubic-bezier(0.34, 1.56, 0.64, 1)",
                                }}
                            />
                        )}
                        {/* Active corpora indicator */}
                        {currentCorpora.length > 0 && (
                            <span style={{
                                fontSize: 9,
                                color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.30)",
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}>
                                {currentCorpora.join(" + ")}
                            </span>
                        )}
                        {/* Internet toggle — teal accent to distinguish from gold jurisdiction pills */}
                        <button
                            onClick={() => setUseInternet(prev => !prev)}
                            title={useInternet ? "Web search enabled — click to disable" : "Web search disabled — click to enable"}
                            style={{
                                display: "inline-flex", alignItems: "center", gap: 3,
                                padding: isMobile ? "2px 6px" : "3px 8px", borderRadius: 6,
                                fontSize: isMobile ? 9 : 10, fontWeight: useInternet ? 700 : 500, lineHeight: 1,
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                background: useInternet
                                    ? isDark ? "rgba(56,178,172,0.14)" : "rgba(0,128,128,0.10)"
                                    : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)",
                                border: useInternet
                                    ? isDark ? "0.5px solid rgba(56,178,172,0.35)" : "0.5px solid rgba(0,128,128,0.25)"
                                    : isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.32)",
                                color: useInternet
                                    ? isDark ? "#38B2AC" : "#0d7377"
                                    : isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.45)",
                                cursor: "pointer",
                                transition: "all 0.15s cubic-bezier(0.34, 1.56, 0.64, 1)",
                                userSelect: "none",
                                WebkitUserSelect: "none",
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                            }}
                        >
                            <Globe size={10} strokeWidth={useInternet ? 2 : 1.5}/>
                            Internet
                        </button>
                    </div>
                    {/* History toggle + Sources toggle + New chat */}
                    <button
                        onClick={() => setHistoryOpen(o => !o)}
                        title="Chat history"
                        style={{
                            display: "flex", alignItems: "center", gap: 4,
                            padding: "5px 10px", borderRadius: 9, fontSize: 12, fontWeight: 500,
                            background: historyOpen
                                ? isDark ? "rgba(201,168,76,0.16)" : "rgba(196,124,0,0.12)"
                                : isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)",
                            border: historyOpen
                                ? isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(196,124,0,0.28)"
                                : isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.42)",
                            color: historyOpen
                                ? isDark ? "rgba(201,168,76,0.85)" : "#7a4a00"
                                : isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)",
                            cursor: "pointer", transition: "all 0.12s",
                            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        }}
                    >
                        <History size={12} strokeWidth={1.8}/>
                    </button>
                    {documentIndex.length > 0 && (
                        <button
                            onClick={() => {
                                setIndexOpen(o => !o)
                                setIndexFocusDocId(null)
                            }}
                            title="Document sources index"
                            style={{
                                display: "flex", alignItems: "center", gap: 4,
                                padding: "5px 10px", borderRadius: 9, fontSize: 12, fontWeight: 500,
                                position: "relative",
                                background: indexOpen
                                    ? isDark ? "rgba(201,168,76,0.16)" : "rgba(196,124,0,0.12)"
                                    : isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)",
                                border: indexOpen
                                    ? isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(196,124,0,0.28)"
                                    : isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.42)",
                                color: indexOpen
                                    ? isDark ? "rgba(201,168,76,0.85)" : "#7a4a00"
                                    : isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)",
                                cursor: "pointer", transition: "all 0.12s",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}
                        >
                            <BookOpen size={12} strokeWidth={1.8}/>
                            {/* Badge with count */}
                            <span style={{
                                display: "inline-flex", alignItems: "center", justifyContent: "center",
                                minWidth: 16, height: 16, borderRadius: 8,
                                padding: "0 4px",
                                fontSize: 9, fontWeight: 700,
                                background: isDark ? "rgba(201,168,76,0.22)" : "rgba(196,124,0,0.16)",
                                color: isDark ? "#C9A84C" : "#7a4a00",
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
                                display: "flex", alignItems: "center", gap: 5,
                                padding: "5px 10px", borderRadius: 9, fontSize: 12, fontWeight: 500,
                                background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.14)" : "0.5px solid rgba(255,255,255,0.42)",
                                color: isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)",
                                cursor: "pointer", transition: "all 0.12s",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}
                            onMouseEnter={e => {
                                e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.14)" : "rgba(255,255,255,0.28)";
                                e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.80)" : "rgba(46,31,8,0.80)"
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.18)";
                                e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.52)" : "rgba(46,31,8,0.55)"
                            }}
                        >
                            <SquarePen size={12} strokeWidth={1.8}/>
                            New
                        </button>
                    )}
                </div>

                {/* Corpus warning banner — switching to a 2nd corpus */}
                {corpusWarning && (
                    <div style={{
                        padding: "10px 20px",
                        background: isDark ? "rgba(201,168,76,0.12)" : "rgba(196,124,0,0.08)",
                        border: isDark ? "0.5px solid rgba(201,168,76,0.30)" : "0.5px solid rgba(196,124,0,0.25)",
                        borderRadius: 0,
                        borderBottom: isDark ? "0.5px solid rgba(201,168,76,0.20)" : "0.5px solid rgba(196,124,0,0.18)",
                        display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
                        fontSize: 12,
                        color: isDark ? "rgba(255,255,255,0.85)" : "#2e1f08",
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        flexShrink: 0,
                    }}>
                        <span>
                            Adding <strong>{JURISDICTIONS[corpusWarning.jurisdiction].name}</strong> to this conversation. Cross-jurisdiction queries may be slower.
                        </span>
                        <div style={{display: "flex", gap: 6, marginLeft: "auto"}}>
                            <button
                                onClick={() => {
                                    const j = corpusWarning.jurisdiction
                                    const hasLawPane = j === "cz" && availableLaws.length > 0
                                    setJurisdiction(j)
                                    if (hasLawPane) setLawPaneOpen(true)
                                    else setLawPaneOpen(false)
                                    setCorpusWarning(null)
                                }}
                                style={{
                                    fontSize: 11, fontWeight: 600,
                                    padding: "4px 12px", borderRadius: 7,
                                    cursor: "pointer",
                                    background: isDark ? "rgba(201,168,76,0.22)" : "rgba(196,124,0,0.16)",
                                    border: isDark ? "0.5px solid rgba(201,168,76,0.45)" : "0.5px solid rgba(196,124,0,0.35)",
                                    color: isDark ? "#C9A84C" : "#7a4a00",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    transition: "all 0.12s",
                                }}
                            >
                                Continue
                            </button>
                            <button
                                onClick={() => setCorpusWarning(null)}
                                style={{
                                    fontSize: 11, fontWeight: 500,
                                    padding: "4px 10px", borderRadius: 7,
                                    cursor: "pointer",
                                    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.18)",
                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.35)",
                                    color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    transition: "all 0.12s",
                                }}
                            >
                                Cancel
                            </button>
                        </div>
                        <label style={{
                            fontSize: 10, opacity: 0.55, cursor: "pointer",
                            display: "flex", alignItems: "center", gap: 4,
                            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        }}>
                            <input
                                type="checkbox"
                                style={{width: 12, height: 12, cursor: "pointer"}}
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
                            transition={{duration: 0.2}}
                            style={{overflow: "hidden", flexShrink: 0}}
                        >
                            <div style={{
                                padding: "10px 20px",
                                background: isDark ? "rgba(255,80,60,0.10)" : "rgba(180,40,20,0.07)",
                                borderBottom: isDark ? "0.5px solid rgba(255,80,60,0.25)" : "0.5px solid rgba(180,40,20,0.20)",
                                fontSize: 12,
                                color: isDark ? "rgba(255,140,122,0.90)" : "#7a2010",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                display: "flex", alignItems: "center", gap: 8,
                            }}>
                                <span>Maximum 2 jurisdictions per conversation. Start a new chat to use a different corpus.</span>
                                <button
                                    onClick={() => {
                                        newChat()
                                        setCorpusBlocked(false)
                                    }}
                                    style={{
                                        fontSize: 11, fontWeight: 600,
                                        padding: "4px 10px", borderRadius: 7,
                                        cursor: "pointer", marginLeft: "auto", whiteSpace: "nowrap",
                                        background: isDark ? "rgba(255,80,60,0.18)" : "rgba(180,40,20,0.12)",
                                        border: isDark ? "0.5px solid rgba(255,80,60,0.35)" : "0.5px solid rgba(180,40,20,0.25)",
                                        color: isDark ? "rgba(255,140,122,0.90)" : "#7a2010",
                                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                        transition: "all 0.12s",
                                    }}
                                >
                                    New chat
                                </button>
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>

                {/* Czech law selector pills — toggle via country pill click */}
                {jurisdiction === "cz" && lawPaneOpen && availableLaws.length > 0 && (
                    <div style={{
                        padding: isMobile ? "5px 12px" : "5px 22px",
                        borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.08)" : "0.5px solid rgba(255,255,255,0.22)",
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 3 : 4,
                        overflowX: "auto",
                        flexShrink: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                        background: isDark ? "rgba(255,255,255,0.015)" : "rgba(255,255,255,0.03)",
                    }}>
                        <span style={{
                            fontSize: 9, fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                            color: isDark ? "rgba(255,255,255,0.30)" : "rgba(46,31,8,0.35)",
                            fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        }}>
                            {selectedLaws.length === availableLaws.length ? "All" : `${selectedLaws.length}/${availableLaws.length}`}
                        </span>
                        {availableLaws.map((law) => {
                            const isActive = selectedLaws.includes(law.id)
                            const accentColor = "#d4af37"
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
                                        fontSize: isMobile ? 9 : 10, fontWeight: isActive ? 700 : 500,
                                        padding: isMobile ? "2px 6px" : "2px 8px", borderRadius: 5,
                                        cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                                        userSelect: "none", WebkitUserSelect: "none",
                                        background: isActive
                                            ? isDark ? "rgba(201,168,76,0.75)" : "rgba(196,124,0,0.65)"
                                            : isDark ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.12)",
                                        border: isActive
                                            ? isDark ? "0.5px solid rgba(201,168,76,0.80)" : "0.5px solid rgba(196,124,0,0.75)"
                                            : isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.28)",
                                        color: isActive
                                            ? "rgba(255,255,255,0.95)"
                                            : isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
                                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                        transition: "all 0.15s cubic-bezier(0.34, 1.56, 0.64, 1)",
                                    }}
                                    onMouseEnter={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.22)"
                                            e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.40)"
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.12)"
                                            e.currentTarget.style.borderColor = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)"
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
                                    fontSize: isMobile ? 8 : 9, fontWeight: 500,
                                    padding: isMobile ? "2px 5px" : "2px 7px", borderRadius: 5,
                                    cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
                                    userSelect: "none", WebkitUserSelect: "none",
                                    background: isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.14)",
                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.30)",
                                    color: isDark ? "rgba(255,255,255,0.45)" : "rgba(46,31,8,0.50)",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    transition: "all 0.12s",
                                }}
                            >
                                All
                            </button>
                        )}
                    </div>
                )}

                {/* Messages */}
                <div ref={scrollAreaRef} style={{flex: 1, overflowY: "auto", padding: isMobile ? "14px 12px 90px" : "22px 24px", minHeight: 0}}>
                    {messages.length === 0 ? (
                        <>
                            <EmptyState
                                onSelectQuestion={onSend}
                                onPreviewQuestion={setPreviewIndex}
                                previewIndex={previewIndex}
                                isDark={isDark}
                                jurisdiction={jurisdiction}
                            />
                        </>
                    ) : (
                        messages.map((m, idx) => (
                            <motion.div
                                key={m.id}
                                initial={{opacity: 0, y: 12, scale: 0.98}}
                                animate={{opacity: 1, y: 0, scale: 1}}
                                transition={{
                                    type: "spring",
                                    damping: 25,
                                    stiffness: 200,
                                    delay: idx === messages.length - 1 ? 0.05 : 0,
                                }}
                            >
                                <ChatMessage
                                    role={m.role}
                                    content={m.content}
                                    sources={m.sources}
                                    confidence={m.confidence}
                                    isStreaming={isStreaming && m.id === activeAssistantId.current}
                                    streamingStatus={isStreaming && m.id === activeAssistantId.current ? streamingStatus : null}
                                    trace={m.trace}
                                    onSourceClick={handleSourceClick}
                                    isDark={isDark}
                                />
                            </motion.div>
                        ))
                    )}

                    {showFollowUps && (
                        <div className="mb-4 animate-fade-in-up">
                            <div style={{display: "flex", gap: "8px", overflowX: "auto", paddingBottom: "4px"}}>
                                {FOLLOWUP_SUGGESTIONS.slice(0, 3).map((suggestion) => (
                                    <button key={suggestion} onClick={() => onSend(suggestion)} style={{
                                        flexShrink: 0, fontSize: "11px", padding: "6px 14px",
                                        borderRadius: "9999px", cursor: "pointer",
                                        background: isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)",
                                        border: isDark ? "1px solid rgba(255,255,255,0.18)" : "1px solid rgba(255,255,255,0.55)",
                                        color: isDark ? "rgba(255,255,255,0.72)" : "#5a3a08",
                                        transition: "all 0.15s ease",
                                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.background = isDark ? "rgba(201,168,76,0.18)" : "rgba(233,196,106,0.28)"
                                                e.currentTarget.style.color = isDark ? "#C9A84C" : "#7a3800"
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.background = isDark ? "rgba(255,255,255,0.10)" : "rgba(255,255,255,0.28)"
                                                e.currentTarget.style.color = isDark ? "rgba(255,255,255,0.72)" : "#5a3a08"
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
                            fontSize: "13px", textAlign: "center", marginTop: "8px", marginBottom: "16px",
                            borderRadius: "12px", padding: "12px 16px",
                            color: isDark ? "#ff8c7a" : "#8b3520",
                            background: isDark ? "rgba(255,100,80,0.10)" : "rgba(139,53,32,0.10)",
                            border: isDark ? "1px solid rgba(255,100,80,0.22)" : "1px solid rgba(139,53,32,0.22)",
                            display: "flex", alignItems: "center", justifyContent: "center", gap: "12px",
                            flexWrap: "wrap",
                        }}>
                            <span>{error}</span>
                            <button
                                onClick={() => {
                                    clearError()
                                    router.replace("/")
                                }}
                                style={{
                                    fontSize: "12px", fontWeight: 600, padding: "5px 12px",
                                    borderRadius: "8px", cursor: "pointer",
                                    background: isDark ? "rgba(255,100,80,0.20)" : "rgba(139,53,32,0.14)",
                                    border: isDark ? "1px solid rgba(255,100,80,0.40)" : "1px solid rgba(139,53,32,0.35)",
                                    color: isDark ? "#ff8c7a" : "#8b3520",
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                }}
                            >
                                Sign in
                            </button>
                        </div>
                    )}
                </div>

                {/* Input */}
                <div style={{
                    padding: isMobile ? "12px 12px 18px" : "12px 22px 16px", borderTop: "0.5px solid rgba(255,255,255,0.28)",
                    flexShrink: 0, background: "rgba(255,255,255,0.04)"
                }}>
                    <ChatInput onSend={onSend} disabled={isStreaming} onFocusRef={inputFocusRef}/>
                    <p style={{
                        fontSize: isMobile ? 9 : 10,
                        color: isDark ? "rgba(255,255,255,0.32)" : "rgba(46,31,8,0.35)",
                        fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                        margin: "8px 0 0",
                        textAlign: "center",
                        lineHeight: 1,
                    }}>
                        For research purposes only. Not legal advice.
                    </p>
                </div>
            </div>

            {/* ── Document preview panel — same flex:1, slides in alongside chat ── */}
            <AnimatePresence>
                {showPreview && (
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
                                background: isDark ? "rgba(13,21,32,0.82)" : "rgba(255,252,242,0.75)",
                                backdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                WebkitBackdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.18)" : "0.5px solid rgba(255,255,255,0.55)",
                                boxShadow: isDark
                                    ? "0 -12px 48px rgba(0,0,0,0.50), inset 0 1px 0 rgba(255,255,255,0.08)"
                                    : "0 -12px 48px rgba(100,50,0,0.15), inset 0 1.5px 0 rgba(255,255,255,0.85)",
                            } : {
                                flex: layoutMode === "source" ? 2 : layoutMode === "chat" ? 1 : 1,
                                position: "relative",
                                zIndex: 1,
                                flexShrink: 0,
                                ...makeGlassPanel(isDark),
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
                            <div style={{display: "flex", justifyContent: "center", padding: "8px 0 0"}}>
                                <div style={{
                                    width: 36, height: 4, borderRadius: 2,
                                    background: isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.20)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? "10px 16px" : "14px 22px",
                            borderBottom: "0.5px solid rgba(255,255,255,0.30)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: "rgba(255,255,255,0.06)",
                        }}>
              <span style={{
                  fontSize: "12px", fontWeight: 600,
                  color: isDark ? "rgba(255,255,255,0.55)" : "rgba(46,31,8,0.55)",
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                  textTransform: "uppercase", letterSpacing: "0.10em"
              }}>
                Source Document
              </span>
                            <button
                                onClick={() => setPreviewIndex(null)}
                                style={{
                                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                                    cursor: "pointer",
                                    padding: isMobile ? 6 : 4,
                                    color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
                                    borderRadius: 8,
                                    display: "flex"
                                }}
                            >
                                <X size={14} strokeWidth={2}/>
                            </button>
                        </div>

                        {/* FakePdf fills remaining height */}
                        <div style={{flex: 1, padding: "16px", minHeight: 0, overflow: "hidden"}}>
                            <div style={{height: "100%", position: "relative"}}>
                                <FakePdf
                                    scenario={previewScenarios[previewIndex!]}
                                    showHighlights={true}
                                />
                            </div>
                        </div>

                        {/* Ask button */}
                        <div style={{
                            padding: isMobile ? "12px 20px 80px" : "12px 20px 16px",
                            borderTop: "0.5px solid rgba(255,255,255,0.28)",
                            flexShrink: 0, background: "rgba(255,255,255,0.04)"
                        }}>
                            <button
                                onClick={() => onSend(presetQuestions[previewIndex!].full)}
                                style={{
                                    width: "100%", padding: "11px", borderRadius: 14,
                                    background: "#5c2e08", color: "#fff8ee",
                                    border: "none", cursor: "pointer",
                                    fontSize: "13px", fontWeight: 600,
                                    fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                                    boxShadow: "0 2px 12px rgba(92,46,8,0.30)",
                                    transition: "opacity 0.14s",
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

            {/* ── Source grounding panel — glass panel beside the chat, same style as preview ── */}
            <AnimatePresence>
                {drawerOpen && drawerData.sources.length > 0 && (
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
                                background: isDark ? "rgba(13,21,32,0.82)" : "rgba(255,252,242,0.75)",
                                backdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                WebkitBackdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.18)" : "0.5px solid rgba(255,255,255,0.55)",
                                boxShadow: isDark
                                    ? "0 -12px 48px rgba(0,0,0,0.50), inset 0 1px 0 rgba(255,255,255,0.08)"
                                    : "0 -12px 48px rgba(100,50,0,0.15), inset 0 1.5px 0 rgba(255,255,255,0.85)",
                            } : {
                                flex: layoutMode === "source" ? 2 : layoutMode === "chat" ? 1 : 1,
                                position: "relative",
                                flexShrink: 0,
                                ...makeGlassPanel(isDark),
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
                            <div style={{display: "flex", justifyContent: "center", padding: "8px 0 0"}}>
                                <div style={{
                                    width: 36, height: 4, borderRadius: 2,
                                    background: isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.20)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? "10px 16px" : "14px 22px",
                            borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.06)",
                        }}>
              <span style={{
                  fontSize: "12px", fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: isDark ? "rgba(201,168,76,0.80)" : "#7a4a00",
                  fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
              }}>
                Source Grounding
              </span>
                            <div style={{display: "flex", alignItems: "center", gap: 4}}>
                                {/* Layout toggle buttons — hide on mobile since it's full-screen */}
                                {!isMobile && (["chat", "split", "source"] as const).map((mode) => (
                                    <button
                                        key={mode}
                                        onClick={() => setLayoutMode(mode)}
                                        title={mode === "chat" ? "Chat focused" : mode === "split" ? "Equal split" : "Sources focused"}
                                        style={{
                                            display: "flex", alignItems: "center", gap: 1,
                                            padding: "3px 5px", borderRadius: 5,
                                            background: layoutMode === mode
                                                ? isDark ? "rgba(201,168,76,0.18)" : "rgba(196,124,0,0.14)"
                                                : isDark ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.18)",
                                            border: layoutMode === mode
                                                ? isDark ? "0.5px solid rgba(201,168,76,0.35)" : "0.5px solid rgba(196,124,0,0.30)"
                                                : isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.40)",
                                            cursor: "pointer",
                                            transition: "all 0.12s",
                                        }}
                                    >
                                        {/* Left rectangle (chat) */}
                                        <span style={{
                                            display: "block",
                                            width: mode === "chat" ? 10 : mode === "split" ? 7 : 4,
                                            height: 10, borderRadius: 1.5,
                                            background: layoutMode === mode
                                                ? isDark ? "rgba(201,168,76,0.70)" : "rgba(196,124,0,0.55)"
                                                : isDark ? "rgba(255,255,255,0.25)" : "rgba(46,31,8,0.25)",
                                            transition: "all 0.12s",
                                        }}/>
                                        {/* Right rectangle (sources) */}
                                        <span style={{
                                            display: "block",
                                            width: mode === "chat" ? 4 : mode === "split" ? 7 : 10,
                                            height: 10, borderRadius: 1.5,
                                            background: layoutMode === mode
                                                ? isDark ? "rgba(201,168,76,0.70)" : "rgba(196,124,0,0.55)"
                                                : isDark ? "rgba(255,255,255,0.25)" : "rgba(46,31,8,0.25)",
                                            transition: "all 0.12s",
                                        }}/>
                                    </button>
                                ))}
                                <button
                                    onClick={() => setDrawerOpen(false)}
                                    style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: isMobile ? 34 : 28, height: isMobile ? 34 : 28,
                                        borderRadius: 8, marginLeft: 4,
                                        background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                                        border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                                        cursor: "pointer",
                                        color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
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
                                background: isDark ? "rgba(13,21,32,0.82)" : "rgba(255,252,242,0.75)",
                                backdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                WebkitBackdropFilter: "blur(48px) saturate(180%) brightness(106%)",
                                border: isDark ? "0.5px solid rgba(255,255,255,0.18)" : "0.5px solid rgba(255,255,255,0.55)",
                                boxShadow: isDark
                                    ? "0 -12px 48px rgba(0,0,0,0.50), inset 0 1px 0 rgba(255,255,255,0.08)"
                                    : "0 -12px 48px rgba(100,50,0,0.15), inset 0 1.5px 0 rgba(255,255,255,0.85)",
                            } : makeGlassPanel(isDark)),
                        }}
                    >
                        {/* Mobile drag handle */}
                        {isMobile && (
                            <div style={{display: "flex", justifyContent: "center", padding: "8px 0 0"}}>
                                <div style={{
                                    width: 36, height: 4, borderRadius: 2,
                                    background: isDark ? "rgba(255,255,255,0.20)" : "rgba(46,31,8,0.20)",
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? "10px 16px" : "14px 16px",
                            borderBottom: isDark ? "0.5px solid rgba(255,255,255,0.10)" : "0.5px solid rgba(255,255,255,0.30)",
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark ? "rgba(255,255,255,0.03)" : "rgba(255,255,255,0.06)",
                        }}>
                            <span style={{
                                fontSize: 11, fontWeight: 700, textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: isDark ? "rgba(201,168,76,0.80)" : "#7a4a00",
                                fontFamily: "-apple-system, BlinkMacSystemFont, system-ui, sans-serif",
                            }}>
                                Sources ({documentIndex.length})
                            </span>
                            <button
                                onClick={() => setIndexOpen(false)}
                                style={{
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    width: isMobile ? 34 : 28, height: isMobile ? 34 : 28,
                                    borderRadius: 8,
                                    background: isDark ? "rgba(255,255,255,0.08)" : "rgba(255,255,255,0.25)",
                                    border: isDark ? "0.5px solid rgba(255,255,255,0.12)" : "0.5px solid rgba(255,255,255,0.50)",
                                    cursor: "pointer",
                                    color: isDark ? "rgba(255,255,255,0.50)" : "rgba(46,31,8,0.50)",
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
