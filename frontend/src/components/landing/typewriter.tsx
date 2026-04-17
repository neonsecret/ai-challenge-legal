"use client";

import {useState, useEffect, useRef, startTransition} from "react";

interface UseTypewriterOptions {
    text: string;
    speed?: number;
    startDelay?: number;
    onComplete?: () => void;
}

export function useTypewriter({
                                  text,
                                  speed = 40,
                                  startDelay = 0,
                                  onComplete,
                              }: UseTypewriterOptions) {
    const [displayed, setDisplayed] = useState("");
    const [done, setDone] = useState(false);
    const indexRef = useRef(0);
    const onCompleteRef = useRef(onComplete);
    useEffect(() => { onCompleteRef.current = onComplete });

    useEffect(() => {
        indexRef.current = 0;
        startTransition(() => {
            setDisplayed("");
            setDone(false);
        });

        let intervalId: ReturnType<typeof setInterval> | null = null;

        const startTimer = setTimeout(() => {
            intervalId = setInterval(() => {
                const next = indexRef.current + 1;
                setDisplayed(text.slice(0, next));
                indexRef.current = next;
                if (next >= text.length) {
                    if (intervalId) clearInterval(intervalId);
                    intervalId = null;
                    setDone(true);
                    onCompleteRef.current?.();
                }
            }, speed);
        }, startDelay);

        return () => {
            clearTimeout(startTimer);
            if (intervalId) clearInterval(intervalId);
        };
    }, [text, speed, startDelay]);

    return {displayed, done};
}
