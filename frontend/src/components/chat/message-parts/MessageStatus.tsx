"use client"

import {StreamingStatus} from "@/components/chat/streaming-status"
import type {Progress} from "@/components/chat/use-query-stream"

interface MessageStatusProps {
    content: string | null
    isStreaming: boolean
    streamingStatus?: string | null
    streamingProgress?: Progress | null
    streamingThinkingPreview?: string | null
}

/**
 * Renders the streaming status placeholder or a recognised pipeline-status
 * sentinel string. Returns null when content is ordinary answer text.
 */
export function MessageStatus({
    content,
    isStreaming,
    streamingStatus,
    streamingProgress,
    streamingThinkingPreview,
}: MessageStatusProps) {
    if (content === "__polling_pipeline_status__") {
        return <StreamingStatus status="Processing..." />
    }
    if (content?.startsWith("__pipeline_status:")) {
        return <StreamingStatus status={content.slice("__pipeline_status:".length)} />
    }
    if (!content && isStreaming) {
        return (
            <StreamingStatus
                status={streamingStatus}
                progress={streamingProgress}
                thinkingPreview={streamingThinkingPreview}
            />
        )
    }
    return null
}
