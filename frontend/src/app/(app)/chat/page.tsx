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
import {FONT, TYPE_SCALE, SPACE, COLOR, GLASS, RADIUS, TIMING, EASE, TEXT_DARK, TEXT_LIGHT} from "@/lib/design-tokens"

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

const CUSTOM_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "Custom",
        question: "Summarize the key provisions in my uploaded documents",
        answer: "",
        pdfTitle: "Your Uploaded Document",
        pdfArticleHeader: "Section 1 — Key Provisions",
        pdfClauses: [
            {id: "1.1", text: "Upload your contracts, agreements, or legal documents to get AI-powered analysis with source citations."},
            {id: "1.2", text: "Vitreon Legal will search through your documents, identify relevant clauses, and provide grounded answers."},
            {id: "1.3", text: "All analysis is performed privately — your documents are never shared or used for training."},
        ],
        highlightRange: [0, 1],
        sourceBadge: "Your Documents",
        pageBadge: "",
    },
    {
        jurisdiction: "Custom",
        question: "What obligations does this agreement impose on the parties?",
        answer: "",
        pdfTitle: "Your Uploaded Document",
        pdfArticleHeader: "Article 5 — Obligations of the Parties",
        pdfClauses: [
            {id: "5.1", text: "Each party shall perform its obligations under this Agreement in good faith and in accordance with applicable law."},
            {id: "5.2", text: "The Service Provider shall deliver all work product in accordance with the specifications set out in Schedule A."},
            {id: "5.3", text: "The Client shall provide timely feedback and all necessary information to enable performance of the Services."},
        ],
        highlightRange: [1, 2],
        sourceBadge: "Your Documents",
        pageBadge: "",
    },
]

const UK_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "United Kingdom",
        question: "What are the statutory duties of a director under the Companies Act 2006?",
        answer: "",
        pdfTitle: "Companies Act 2006",
        pdfArticleHeader: "Section 172 — Duty to promote the success of the company",
        pdfClauses: [
            {
                id: "172(1)",
                text: "A director of a company must act in the way he considers, in good faith, would be most likely to promote the success of the company for the benefit of its members as a whole."
            },
            {
                id: "172(1)(a)",
                text: "In doing so, he must have regard to the likely consequences of any decision in the long term."
            },
            {
                id: "172(1)(b)",
                text: "The interests of the company's employees, the impact on the community and the environment, and the desirability of maintaining a reputation for high standards of business conduct."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Companies Act 2006 · s.172 · p.329",
        pageBadge: "Page 329",
    },
    {
        jurisdiction: "United Kingdom",
        question: "What constitutes unfair dismissal under the Employment Rights Act 1996?",
        answer: "",
        pdfTitle: "Employment Rights Act 1996",
        pdfArticleHeader: "Section 98 — General right not to be unfairly dismissed",
        pdfClauses: [
            {
                id: "98(1)",
                text: "In determining whether the dismissal of an employee is fair or unfair, it is for the employer to show the reason for the dismissal."
            },
            {
                id: "98(2)",
                text: "A reason falls within this subsection if it relates to the capability or qualifications of the employee, the conduct of the employee, or that the employee was redundant."
            },
            {
                id: "98(4)",
                text: "The determination of whether the dismissal is fair or unfair shall depend on whether the employer acted reasonably in treating it as a sufficient reason."
            },
        ],
        highlightRange: [0, 2],
        sourceBadge: "Employment Rights Act 1996 · s.98 · p.432",
        pageBadge: "Page 432",
    },
]

const AU_SCENARIOS: DemoScenario[] = [
    {
        jurisdiction: "Australia",
        question: "What is the insolvent trading duty under the Corporations Act 2001?",
        answer: "",
        pdfTitle: "Corporations Act 2001",
        pdfArticleHeader: "Section 588G — Director's duty to prevent insolvent trading",
        pdfClauses: [
            {
                id: "588G(1)",
                text: "This section applies if a company incurs a debt at a time when the company is insolvent, or becomes insolvent by incurring that debt."
            },
            {
                id: "588G(2)",
                text: "The director contravenes this section if the director was aware that there were grounds for suspecting the company was insolvent, or a reasonable person would have been so aware."
            },
            {
                id: "588G(3)",
                text: "A person who contravenes this section commits an offence punishable by imprisonment for up to 5 years or 200 penalty units."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "Corporations Act 2001 · s.588G · p.5290",
        pageBadge: "Page 5290",
    },
    {
        jurisdiction: "Australia",
        question: "What constitutes unconscionable conduct under Australian Consumer Law?",
        answer: "",
        pdfTitle: "Competition and Consumer Act 2010 — Schedule 2",
        pdfArticleHeader: "Section 21 — Unconscionable conduct in connection with goods or services",
        pdfClauses: [
            {
                id: "21(1)",
                text: "A person must not, in trade or commerce, in connection with the supply or acquisition of goods or services, engage in conduct that is, in all the circumstances, unconscionable."
            },
            {
                id: "21(4)(a)",
                text: "The court may have regard to the relative bargaining strengths of the parties and whether any conditions were reasonably necessary for the protection of legitimate interests."
            },
            {
                id: "21(4)(b)",
                text: "Whether the consumer was able to understand any documents relating to the supply or acquisition of the goods or services."
            },
        ],
        highlightRange: [0, 1],
        sourceBadge: "ACL Schedule 2 · s.21 · p.2396",
        pageBadge: "Page 2396",
    },
]

const PREVIEW_SCENARIOS_MAP: Record<string, DemoScenario[]> = {
    difc: DIFC_SCENARIOS,
    cz: CZ_SCENARIOS,
    uk: UK_SCENARIOS,
    au: AU_SCENARIOS,
    custom: CUSTOM_SCENARIOS,
}

function makeGlassPanel(isDark: boolean) {
    return isDark ? {
        background: GLASS.dark.bg,
        backdropFilter: GLASS.dark.blur,
        WebkitBackdropFilter: GLASS.dark.blur,
        border: `0.5px solid ${GLASS.dark.border}`,
        borderRadius: `${RADIUS['2xl']}px`,
        boxShadow: `${GLASS.dark.innerGlow}, ${GLASS.dark.shadow}`,
        willChange: "transform",
        transform: "translateZ(0)",
    } : {
        background: "rgba(255,252,242,0.18)",
        backdropFilter: GLASS.light.blur,
        WebkitBackdropFilter: GLASS.light.blur,
        border: `0.5px solid ${GLASS.light.border}`,
        borderRadius: `${RADIUS['2xl']}px`,
        boxShadow: `${GLASS.light.innerGlow}, inset 1px 0 0 rgba(255,255,255,0.30), 0 16px 48px rgba(100,50,0,0.12)`,
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
    const [layoutMode, setLayoutMode] = useState<"chat" | "split" | "source">("split")
    const [customCorpus, setCustomCorpus] = useState("")
    const [corpusWarning, setCorpusWarning] = useState<{corpus: string, jurisdiction: Jurisdiction} | null>(null)
    const [corpusBlocked, setCorpusBlocked] = useState(false)
    const [hideCorpusWarning, setHideCorpusWarning] = useState(false)
    const [availableCorpora, setAvailableCorpora] = useState<CorpusEntry[]>([])
    const [corporaLoading, setCorporaLoading] = useState(false)
    const {resolvedTheme} = useTheme()
    const [mounted, setMounted] = useState(false)
    useEffect(() => setMounted(true), [])
    const isDark = mounted && resolvedTheme === "dark"
    const isMobile = useIsMobile()
    const documentIndex = useDocumentIndex(messages)

    // Law selector: fetch available laws from backend based on jurisdiction
    const [availableLaws, setAvailableLaws] = useState<{id: string; name: string; name_en: string}[]>([])
    useEffect(() => {
        const corpus = jurisdiction === "cz" ? "czech" : jurisdiction === "uk" ? "uk" : jurisdiction === "au" ? "au" : ""
        if (!corpus) { setAvailableLaws([]); setLawPaneOpen(false); return }
        const sseBase = process.env.NEXT_PUBLIC_SSE_URL ?? ""
        fetch(`${sseBase}/api/v1/laws?corpus=${corpus}`)
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
            .catch(() => { setAvailableLaws([]); setLawPaneOpen(false) })
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

    const onSend = useCallback((question: string) => {
        setPreviewIndex(null)
        const result = handleSend(question)
        if (result === "blocked") {
            setCorpusBlocked(true)
            setTimeout(() => setCorpusBlocked(false), 4000)
        }
        // "streaming" means previous query still running — silently ignore
    }, [handleSend])

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

    return (
        <div className="p-2 sm:p-4" style={{
            height: "100%",
            display: "flex",
            alignItems: "stretch",
            gap: isMobile ? 0 : SPACE['2'],
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
                                boxShadow: isDark ? GLASS.dark.innerGlow : GLASS.light.innerGlow,
                                border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                            } : makeGlassPanel(isDark)),
                        }}
                    >
                        {/* History header */}
                        <div style={{
                            padding: `${SPACE['4']}px ${SPACE['4']}px`,
                            paddingTop: isMobile ? `max(${SPACE['4']}px, env(safe-area-inset-top))` : SPACE['4'],
                            borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        }}>
              <span style={{
                  fontSize: TYPE_SCALE.xs, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.tertiary,
                  fontFamily: FONT.sans,
              }}>Chats</span>
                            <div style={{display: "flex", alignItems: "center", gap: SPACE['2']}}>
                            <button onClick={() => {
                                newChat();
                                setHistoryOpen(false)
                            }} title="New chat" style={{
                                display: "flex", alignItems: "center", gap: SPACE['1'],
                                padding: `${SPACE['1']}px ${SPACE['2']}px`, borderRadius: RADIUS.md, fontSize: TYPE_SCALE.xs, fontWeight: 500,
                                background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                cursor: "pointer", transition: `all ${TIMING.instant}`,
                                fontFamily: FONT.sans,
                            }}>
                                <SquarePen size={TYPE_SCALE.xs} strokeWidth={1.8}/>
                                New
                            </button>
                            {isMobile && (
                                <button
                                    onClick={() => setHistoryOpen(false)}
                                    title="Close"
                                    style={{
                                        display: "flex", alignItems: "center", justifyContent: "center",
                                        width: 28, height: 28, borderRadius: RADIUS.md,
                                        background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                        border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.border}`,
                                        cursor: "pointer",
                                        color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                    }}
                                >
                                    <X size={14} strokeWidth={2}/>
                                </button>
                            )}
                            </div>
                        </div>
                        {/* Sessions list */}
                        <div style={{flex: 1, overflowY: "auto", padding: SPACE['2']}}>
                            {sessions.length === 0 ? (
                                <p style={{
                                    fontSize: TYPE_SCALE.sm, textAlign: "center", padding: `${SPACE['6']}px ${SPACE['3']}px`,
                                    color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                    fontFamily: FONT.sans,
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
                                                    padding: `${SPACE['2']}px ${SPACE['8']}px ${SPACE['2']}px ${SPACE['3']}px`, borderRadius: RADIUS.lg,
                                                    fontSize: TYPE_SCALE.sm,
                                                    color: isActive
                                                        ? isDark ? TEXT_DARK.primary : TEXT_LIGHT.primary
                                                        : isDark ? TEXT_DARK.secondary : TEXT_LIGHT.secondary,
                                                    background: isActive
                                                        ? isDark ? COLOR.gold.tint : "rgba(255,255,255,0.38)"
                                                        : "transparent",
                                                    border: isActive
                                                        ? isDark ? `0.5px solid ${COLOR.gold.border}` : `0.5px solid ${GLASS.light.border}`
                                                        : "0.5px solid transparent",
                                                    cursor: "pointer",
                                                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                                                    fontFamily: FONT.sans,
                                                    transition: `background ${TIMING.instant}, border-color ${TIMING.instant}, box-shadow ${TIMING.instant}, color ${TIMING.instant}`,
                                                    fontWeight: isActive ? 600 : 400,
                                                }}
                                                onMouseEnter={e => {
                                                    if (!isActive) {
                                                        e.currentTarget.style.background = isDark ? GLASS.dark.bg : "rgba(255,255,255,0.28)"
                                                        e.currentTarget.style.borderColor = isDark ? GLASS.dark.borderSubtle : GLASS.light.borderSubtle
                                                        e.currentTarget.style.boxShadow = isDark
                                                            ? `${GLASS.dark.innerGlow}, 0 2px 8px rgba(0,0,0,0.15)`
                                                            : `${GLASS.light.innerGlow}, 0 2px 8px rgba(100,50,0,0.08)`
                                                        e.currentTarget.style.backdropFilter = GLASS.dark.blurLight
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
                                                    right: SPACE['2'],
                                                    top: "50%",
                                                    /* Negate the global button:active scale by always including translateY centering */
                                                    transform: "translateY(-50%)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    width: 22,
                                                    height: 22,
                                                    borderRadius: RADIUS.sm,
                                                    background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                                    border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                                    cursor: "pointer",
                                                    color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                                    transition: `opacity ${TIMING.instant}, background ${TIMING.instant}, color ${TIMING.instant}`,
                                                    padding: 0,
                                                    zIndex: 1,
                                                    flexShrink: 0,
                                                }}
                                                onMouseEnter={e => {
                                                    e.currentTarget.style.background = isDark ? "rgba(255,80,60,0.18)" : "rgba(200,50,30,0.12)"
                                                    e.currentTarget.style.color = isDark ? "rgba(255,120,100,0.90)" : "rgba(180,40,20,0.80)"
                                                }}
                                                onMouseLeave={e => {
                                                    e.currentTarget.style.background = isDark ? GLASS.dark.bg : GLASS.light.bgSubtle
                                                    e.currentTarget.style.color = isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary
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
                overflow: "hidden",
                contain: "style",
                transition: `all ${TIMING.slow} ${EASE.out}`,
                ...makeGlassPanel(isDark),
            }}>
                {/* Header */}
                <div style={{
                    padding: isMobile ? `${SPACE['3']}px ${SPACE['3']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                    borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                    display: "flex", alignItems: "center", gap: isMobile ? SPACE['2'] : SPACE['3'], flexShrink: 0,
                    background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                    overflow: "visible", position: "relative", zIndex: 10,
                }}>
                    <div style={{
                        width: isMobile ? 26 : 30, height: isMobile ? 26 : 30, borderRadius: isMobile ? RADIUS.md : RADIUS.lg,
                        background: isDark ? COLOR.gold.tint : "rgba(196,124,0,0.18)",
                        border: isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.38)",
                        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.65)",
                    }}>
            <span style={{
                fontSize: isMobile ? TYPE_SCALE.sm : TYPE_SCALE.md, fontWeight: 700, color: isDark ? COLOR.gold.base : "#7a4a00", lineHeight: 1,
                fontFamily: FONT.brand
            }}>N</span>
                    </div>
                    {!isMobile && <span style={{
                        fontWeight: 700, fontSize: TYPE_SCALE.md, color: isDark ? TEXT_DARK.primary : TEXT_LIGHT.primary,
                        fontFamily: FONT.brand, letterSpacing: "-0.04em"
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
                        {(["difc", "cz", "eu", "uk", "us", "au", "custom"] as Jurisdiction[]).map((key) => {
                            const config = JURISDICTIONS[key]
                            const isActive = jurisdiction === key
                            const isEnabled = key === "difc" || key === "cz" || key === "uk" || key === "au" || key === "custom"
                            const hasLawPane = (key === "cz" || key === "uk" || key === "au") && availableLaws.length > 0 && jurisdiction === key
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
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : "rgba(255,255,255,0.24)"
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.border : GLASS.light.borderSubtle
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.transform = "scale(1)"
                                        if (!isActive && isEnabled) {
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bg : "rgba(255,255,255,0.14)"
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.border : GLASS.light.borderSubtle
                                        }
                                    }}
                                    style={{
                                        display: "inline-flex", alignItems: "center", gap: 2,
                                        fontSize: TYPE_SCALE.xs, fontWeight: isActive ? 700 : 500,
                                        padding: isMobile ? `2px ${SPACE['2']}px` : `3px ${SPACE['2']}px`, borderRadius: RADIUS.sm,
                                        cursor: isEnabled ? "pointer" : "not-allowed",
                                        opacity: isEnabled ? 1 : 0.38,
                                        background: isActive
                                            ? COLOR.gold.solid
                                            : isDark ? GLASS.dark.bg : "rgba(255,255,255,0.14)",
                                        border: isActive
                                            ? `0.5px solid ${COLOR.gold.border}`
                                            : isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                        color: isActive
                                            ? TEXT_DARK.primary
                                            : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                                color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                whiteSpace: "nowrap",
                                flexShrink: 0,
                                fontFamily: FONT.sans,
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
                                padding: isMobile ? `2px ${SPACE['2']}px` : `3px ${SPACE['2']}px`, borderRadius: RADIUS.sm,
                                fontSize: TYPE_SCALE.xs, fontWeight: useInternet ? 700 : 500, lineHeight: 1,
                                fontFamily: FONT.sans,
                                background: useInternet
                                    ? isDark ? COLOR.teal.tint : "rgba(0,128,128,0.10)"
                                    : isDark ? GLASS.dark.bg : "rgba(255,255,255,0.14)",
                                border: useInternet
                                    ? isDark ? `0.5px solid ${COLOR.teal.border}` : "0.5px solid rgba(0,128,128,0.25)"
                                    : isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                color: useInternet
                                    ? isDark ? COLOR.teal.base : "#0d7377"
                                    : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                                ? isDark ? COLOR.gold.tint : "rgba(196,124,0,0.12)"
                                : isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)",
                            border: historyOpen
                                ? isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.28)"
                                : isDark ? `0.5px solid ${GLASS.dark.border}` : "0.5px solid rgba(255,255,255,0.42)",
                            color: historyOpen
                                ? isDark ? COLOR.gold.base : "#7a4a00"
                                : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                            cursor: "pointer", transition: `all ${TIMING.instant}`,
                            fontFamily: FONT.sans,
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
                                    ? isDark ? COLOR.gold.tint : "rgba(196,124,0,0.12)"
                                    : isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)",
                                border: indexOpen
                                    ? isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.28)"
                                    : isDark ? `0.5px solid ${GLASS.dark.border}` : "0.5px solid rgba(255,255,255,0.42)",
                                color: indexOpen
                                    ? isDark ? COLOR.gold.base : "#7a4a00"
                                    : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                cursor: "pointer", transition: `all ${TIMING.instant}`,
                                fontFamily: FONT.sans,
                            }}
                        >
                            <BookOpen size={TYPE_SCALE.sm} strokeWidth={1.8}/>
                            {/* Badge with count */}
                            <span style={{
                                display: "inline-flex", alignItems: "center", justifyContent: "center",
                                minWidth: SPACE['4'], height: SPACE['4'], borderRadius: RADIUS.md,
                                padding: `0 ${SPACE['1']}px`,
                                fontSize: TYPE_SCALE.xs, fontWeight: 700,
                                background: isDark ? COLOR.gold.glow : "rgba(196,124,0,0.16)",
                                color: isDark ? COLOR.gold.base : "#7a4a00",
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
                                background: isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)",
                                border: isDark ? `0.5px solid ${GLASS.dark.border}` : "0.5px solid rgba(255,255,255,0.42)",
                                color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                cursor: "pointer", transition: `all ${TIMING.instant}`,
                                fontFamily: FONT.sans,
                            }}
                            onMouseEnter={e => {
                                e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : "rgba(255,255,255,0.28)";
                                e.currentTarget.style.color = isDark ? TEXT_DARK.primary : TEXT_LIGHT.secondary
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.background = isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)";
                                e.currentTarget.style.color = isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary
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
                        background: isDark ? COLOR.gold.tint : "rgba(196,124,0,0.08)",
                        border: isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.25)",
                        borderRadius: 0,
                        borderBottom: isDark ? `0.5px solid ${COLOR.gold.glow}` : "0.5px solid rgba(196,124,0,0.18)",
                        display: "flex", alignItems: "center", gap: SPACE['3'], flexWrap: "wrap",
                        fontSize: TYPE_SCALE.sm,
                        color: isDark ? TEXT_DARK.primary : TEXT_LIGHT.secondary,
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
                                    const hasLawPane = j === "cz" && availableLaws.length > 0
                                    setJurisdiction(j)
                                    if (hasLawPane) setLawPaneOpen(true)
                                    else setLawPaneOpen(false)
                                    setCorpusWarning(null)
                                }}
                                style={{
                                    fontSize: TYPE_SCALE.xs, fontWeight: 600,
                                    padding: `${SPACE['1']}px ${SPACE['3']}px`, borderRadius: RADIUS.md,
                                    cursor: "pointer",
                                    background: isDark ? COLOR.gold.glow : "rgba(196,124,0,0.16)",
                                    border: isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.35)",
                                    color: isDark ? COLOR.gold.base : "#7a4a00",
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
                                    background: isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)",
                                    border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                    color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                            transition={{duration: 0.2}}
                            style={{overflow: "hidden", flexShrink: 0}}
                        >
                            <div style={{
                                padding: `${SPACE['3']}px ${SPACE['5']}px`,
                                background: isDark ? "rgba(255,80,60,0.10)" : "rgba(180,40,20,0.07)",
                                borderBottom: isDark ? "0.5px solid rgba(255,80,60,0.25)" : "0.5px solid rgba(180,40,20,0.20)",
                                fontSize: TYPE_SCALE.sm,
                                color: isDark ? "rgba(255,140,122,0.90)" : "#7a2010",
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
                                        background: isDark ? "rgba(255,80,60,0.18)" : "rgba(180,40,20,0.12)",
                                        border: isDark ? "0.5px solid rgba(255,80,60,0.35)" : "0.5px solid rgba(180,40,20,0.25)",
                                        color: isDark ? "rgba(255,140,122,0.90)" : "#7a2010",
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

                {/* Czech law selector pills — toggle via country pill click */}
                {(jurisdiction === "cz" || jurisdiction === "uk" || jurisdiction === "au") && lawPaneOpen && availableLaws.length > 0 && (
                    <div style={{
                        padding: isMobile ? `${SPACE['1']}px ${SPACE['3']}px` : `${SPACE['1']}px ${SPACE['6']}px`,
                        borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.bgSubtle}`,
                        display: "flex",
                        alignItems: "center",
                        gap: isMobile ? 3 : SPACE['1'],
                        overflowX: "auto",
                        flexShrink: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                        background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                    }}>
                        <span style={{
                            fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                            color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
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
                                            ? COLOR.gold.solid
                                            : isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)",
                                        border: isActive
                                            ? `0.5px solid ${COLOR.gold.border}`
                                            : isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : "0.5px solid rgba(255,255,255,0.28)",
                                        color: isActive
                                            ? TEXT_DARK.primary
                                            : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                        fontFamily: FONT.sans,
                                        transition: `all ${TIMING.fast} ${EASE.spring}`,
                                    }}
                                    onMouseEnter={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : GLASS.light.bgSubtle
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.border : GLASS.light.borderSubtle
                                        }
                                    }}
                                    onMouseLeave={(e) => {
                                        if (!isActive) {
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)"
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.borderSubtle : "rgba(255,255,255,0.28)"
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
                                    background: isDark ? GLASS.dark.bg : "rgba(255,255,255,0.14)",
                                    border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                                    color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                        borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.bgSubtle}`,
                        display: "flex",
                        alignItems: "center",
                        gap: SPACE['2'],
                        overflowX: "auto",
                        flexShrink: 0,
                        scrollbarWidth: "none",
                        WebkitOverflowScrolling: "touch",
                        background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                    }}>
                        <span style={{
                            fontSize: TYPE_SCALE.xs, fontWeight: 600, textTransform: "uppercase",
                            letterSpacing: "0.08em", whiteSpace: "nowrap", flexShrink: 0,
                            color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                            fontFamily: FONT.sans,
                        }}>
                            Collections
                        </span>
                        {corporaLoading ? (
                            <span style={{
                                fontSize: TYPE_SCALE.sm,
                                color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
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
                                        ? COLOR.gold.solid
                                        : isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)",
                                    border: active
                                        ? `0.5px solid ${COLOR.gold.border}`
                                        : isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : "0.5px solid rgba(255,255,255,0.28)",
                                    color: active
                                        ? TEXT_DARK.primary
                                        : isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.fast} ${EASE.spring}`,
                                })

                                const hoverHandlers = (active: boolean) => ({
                                    onMouseEnter: (e: React.MouseEvent<HTMLButtonElement>) => {
                                        if (!active) {
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : GLASS.light.bgSubtle
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.border : GLASS.light.borderSubtle
                                        }
                                    },
                                    onMouseLeave: (e: React.MouseEvent<HTMLButtonElement>) => {
                                        if (!active) {
                                            e.currentTarget.style.background = isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)"
                                            e.currentTarget.style.borderColor = isDark ? GLASS.dark.borderSubtle : "rgba(255,255,255,0.28)"
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
                                    background: isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)",
                                    border: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : "0.5px solid rgba(255,255,255,0.28)",
                                    color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                                    fontFamily: FONT.sans,
                                    transition: `all ${TIMING.fast} ${EASE.spring}`,
                                }}
                                onMouseEnter={(e) => {
                                    e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : GLASS.light.bgSubtle
                                    e.currentTarget.style.borderColor = isDark ? GLASS.dark.border : GLASS.light.borderSubtle
                                }}
                                onMouseLeave={(e) => {
                                    e.currentTarget.style.background = isDark ? GLASS.dark.bgSubtle : "rgba(255,255,255,0.12)"
                                    e.currentTarget.style.borderColor = isDark ? GLASS.dark.borderSubtle : "rgba(255,255,255,0.28)"
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
                                initial={{opacity: 0, y: SPACE['3'], scale: 0.98}}
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
                                    streamingProgress={isStreaming && m.id === activeAssistantId.current ? streamingProgress : null}
                                    streamingThinkingPreview={isStreaming && m.id === activeAssistantId.current ? thinkingPreview : null}
                                    trace={m.trace}
                                    onSourceClick={handleSourceClick}
                                    isDark={isDark}
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
                                        background: isDark ? GLASS.dark.bgHover : "rgba(255,255,255,0.28)",
                                        border: isDark ? `1px solid ${GLASS.dark.border}` : `1px solid ${GLASS.light.border}`,
                                        color: isDark ? TEXT_DARK.secondary : "#5a3a08",
                                        transition: `all ${TIMING.fast}`,
                                        fontFamily: FONT.sans,
                                    }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.background = isDark ? COLOR.gold.tint : "rgba(233,196,106,0.28)"
                                                e.currentTarget.style.color = isDark ? COLOR.gold.base : "#7a3800"
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.background = isDark ? GLASS.dark.bgHover : "rgba(255,255,255,0.28)"
                                                e.currentTarget.style.color = isDark ? TEXT_DARK.secondary : "#5a3a08"
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
                            color: isDark ? "#ff8c7a" : "#8b3520",
                            background: isDark ? "rgba(255,100,80,0.10)" : "rgba(139,53,32,0.10)",
                            border: isDark ? "1px solid rgba(255,100,80,0.22)" : "1px solid rgba(139,53,32,0.22)",
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
                                    background: isDark ? "rgba(255,100,80,0.20)" : "rgba(139,53,32,0.14)",
                                    border: isDark ? "1px solid rgba(255,100,80,0.40)" : "1px solid rgba(139,53,32,0.35)",
                                    color: isDark ? "#ff8c7a" : "#8b3520",
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
                    borderTop: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
                    flexShrink: 0, background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                }}>
                    <ChatInput onSend={onSend} disabled={isStreaming} onFocusRef={inputFocusRef}/>
                    <p style={{
                        fontSize: TYPE_SCALE.xs,
                        color: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                        fontFamily: FONT.sans,
                        margin: `${SPACE['2']}px 0 0`,
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
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                            borderBottom: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        }}>
              <span style={{
                  fontSize: TYPE_SCALE.sm, fontWeight: 600,
                  color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
                  fontFamily: FONT.sans,
                  textTransform: "uppercase", letterSpacing: "0.10em"
              }}>
                Source Document
              </span>
                            <button
                                onClick={() => setPreviewIndex(null)}
                                style={{
                                    background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                    border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.border}`,
                                    cursor: "pointer",
                                    padding: isMobile ? SPACE['2'] : SPACE['1'],
                                    color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                            borderTop: `0.5px solid ${isDark ? GLASS.dark.border : GLASS.light.borderSubtle}`,
                            flexShrink: 0, background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        }}>
                            <button
                                onClick={() => onSend(presetQuestions[previewIndex!].full)}
                                style={{
                                    width: "100%", padding: SPACE['3'], borderRadius: RADIUS.xl,
                                    background: "#5c2e08", color: "#fff8ee",
                                    border: "none", cursor: "pointer",
                                    fontSize: TYPE_SCALE.sm, fontWeight: 600,
                                    fontFamily: FONT.sans,
                                    boxShadow: "0 2px 12px rgba(92,46,8,0.30)",
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
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['6']}px`,
                            borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0, background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        }}>
              <span style={{
                  fontSize: TYPE_SCALE.sm, fontWeight: 700, textTransform: "uppercase",
                  letterSpacing: "0.12em",
                  color: isDark ? COLOR.gold.base : "#7a4a00",
                  fontFamily: FONT.sans,
              }}>
                Source Grounding
              </span>
                            <div style={{display: "flex", alignItems: "center", gap: SPACE['1']}}>
                                {/* Layout toggle buttons — hide on mobile since it's full-screen */}
                                {!isMobile && (["chat", "split", "source"] as const).map((mode) => (
                                    <button
                                        key={mode}
                                        onClick={() => setLayoutMode(mode)}
                                        title={mode === "chat" ? "Chat focused" : mode === "split" ? "Equal split" : "Sources focused"}
                                        style={{
                                            display: "flex", alignItems: "center", gap: 1,
                                            padding: `3px ${SPACE['1']}px`, borderRadius: RADIUS.sm,
                                            background: layoutMode === mode
                                                ? isDark ? COLOR.gold.tint : "rgba(196,124,0,0.14)"
                                                : isDark ? GLASS.dark.bg : "rgba(255,255,255,0.18)",
                                            border: layoutMode === mode
                                                ? isDark ? `0.5px solid ${COLOR.gold.border}` : "0.5px solid rgba(196,124,0,0.30)"
                                                : isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : "0.5px solid rgba(255,255,255,0.40)",
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
                                                ? isDark ? COLOR.gold.solid : "rgba(196,124,0,0.55)"
                                                : isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                            transition: `all ${TIMING.instant}`,
                                        }}/>
                                        {/* Right rectangle (sources) */}
                                        <span style={{
                                            display: "block",
                                            width: mode === "chat" ? SPACE['1'] : mode === "split" ? 7 : 10,
                                            height: 10, borderRadius: 1.5,
                                            background: layoutMode === mode
                                                ? isDark ? COLOR.gold.solid : "rgba(196,124,0,0.55)"
                                                : isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
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
                                        background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                        border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.border}`,
                                        cursor: "pointer",
                                        color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
                            <div style={{display: "flex", justifyContent: "center", padding: `${SPACE['2']}px 0 0`}}>
                                <div style={{
                                    width: 36, height: SPACE['1'], borderRadius: 2,
                                    background: isDark ? TEXT_DARK.quaternary : TEXT_LIGHT.quaternary,
                                }}/>
                            </div>
                        )}
                        {/* Panel header */}
                        <div style={{
                            padding: isMobile ? `${SPACE['3']}px ${SPACE['4']}px` : `${SPACE['4']}px ${SPACE['4']}px`,
                            borderBottom: isDark ? `0.5px solid ${GLASS.dark.borderSubtle}` : `0.5px solid ${GLASS.light.borderSubtle}`,
                            display: "flex", alignItems: "center", justifyContent: "space-between",
                            flexShrink: 0,
                            background: isDark ? GLASS.dark.bgSubtle : GLASS.light.bgSubtle,
                        }}>
                            <span style={{
                                fontSize: TYPE_SCALE.xs, fontWeight: 700, textTransform: "uppercase",
                                letterSpacing: "0.12em",
                                color: isDark ? COLOR.gold.base : "#7a4a00",
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
                                    background: isDark ? GLASS.dark.bg : GLASS.light.bgSubtle,
                                    border: isDark ? `0.5px solid ${GLASS.dark.border}` : `0.5px solid ${GLASS.light.border}`,
                                    cursor: "pointer",
                                    color: isDark ? TEXT_DARK.tertiary : TEXT_LIGHT.tertiary,
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
