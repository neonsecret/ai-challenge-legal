import {ImageResponse} from "next/og";

export const runtime = "edge";
export const alt = "Vitreon Legal — AI-Powered Legal Research Platform";
export const size = {width: 1200, height: 630};
export const contentType = "image/png";

export default function OGImage() {
    return new ImageResponse(
        (
            <div
                style={{
                    width: "100%",
                    height: "100%",
                    display: "flex",
                    flexDirection: "column",
                    justifyContent: "center",
                    alignItems: "center",
                    background: "linear-gradient(145deg, #0a0a0f 0%, #111118 50%, #0d0d14 100%)",
                    fontFamily: "Georgia, serif",
                    position: "relative",
                    overflow: "hidden",
                }}
            >
                {/* Subtle gold accent line at top */}
                <div
                    style={{
                        position: "absolute",
                        top: 0,
                        left: 0,
                        right: 0,
                        height: "3px",
                        background: "linear-gradient(90deg, transparent 10%, #c9a84c 50%, transparent 90%)",
                    }}
                />

                {/* Logo mark */}
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        width: "72px",
                        height: "72px",
                        borderRadius: "16px",
                        background: "rgba(201, 168, 76, 0.12)",
                        border: "1px solid rgba(201, 168, 76, 0.25)",
                        marginBottom: "28px",
                    }}
                >
                    <span
                        style={{
                            fontSize: "36px",
                            fontWeight: 700,
                            color: "#c9a84c",
                            fontFamily: "Georgia, serif",
                        }}
                    >
                        V
                    </span>
                </div>

                {/* Title */}
                <h1
                    style={{
                        fontSize: "52px",
                        fontWeight: 700,
                        color: "#e8e4de",
                        letterSpacing: "-0.03em",
                        margin: "0 0 12px",
                        textAlign: "center",
                    }}
                >
                    Vitreon Legal
                </h1>

                {/* Subtitle */}
                <p
                    style={{
                        fontSize: "22px",
                        color: "rgba(232, 228, 222, 0.55)",
                        margin: "0 0 36px",
                        textAlign: "center",
                        maxWidth: "700px",
                        lineHeight: 1.5,
                    }}
                >
                    AI-powered legal research with source-grounded answers from statutes and court decisions
                </p>

                {/* Stats row */}
                <div
                    style={{
                        display: "flex",
                        gap: "48px",
                        alignItems: "center",
                    }}
                >
                    <div style={{display: "flex", flexDirection: "column", alignItems: "center"}}>
                        <span style={{fontSize: "28px", fontWeight: 700, color: "#c9a84c"}}>0.824</span>
                        <span style={{fontSize: "12px", color: "rgba(232, 228, 222, 0.35)", marginTop: "4px"}}>
                            GaRAGe RAF
                        </span>
                    </div>
                    <div style={{width: "1px", height: "40px", background: "rgba(201, 168, 76, 0.2)"}} />
                    <div style={{display: "flex", flexDirection: "column", alignItems: "center"}}>
                        <span style={{fontSize: "28px", fontWeight: 700, color: "#c9a84c"}}>100%</span>
                        <span style={{fontSize: "12px", color: "rgba(232, 228, 222, 0.35)", marginTop: "4px"}}>
                            Citation Accuracy
                        </span>
                    </div>
                    <div style={{width: "1px", height: "40px", background: "rgba(201, 168, 76, 0.2)"}} />
                    <div style={{display: "flex", flexDirection: "column", alignItems: "center"}}>
                        <span style={{fontSize: "28px", fontWeight: 700, color: "#c9a84c"}}>4</span>
                        <span style={{fontSize: "12px", color: "rgba(232, 228, 222, 0.35)", marginTop: "4px"}}>
                            Jurisdictions
                        </span>
                    </div>
                </div>

                {/* Domain */}
                <p
                    style={{
                        position: "absolute",
                        bottom: "28px",
                        fontSize: "14px",
                        color: "rgba(201, 168, 76, 0.45)",
                        letterSpacing: "0.08em",
                    }}
                >
                    vitreon.app
                </p>
            </div>
        ),
        {
            ...size,
        },
    );
}
