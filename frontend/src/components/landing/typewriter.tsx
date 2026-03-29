"use client";

import {useState, useEffect, useRef} from "react";

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
    onCompleteRef.current = onComplete;

    useEffect(() => {
        indexRef.current = 0;
        setDisplayed("");
        setDone(false);

        const startTimer = setTimeout(() => {
            const interval = setInterval(() => {
                const next = indexRef.current + 1;
                setDisplayed(text.slice(0, next));
                indexRef.current = next;
                if (next >= text.length) {
                    clearInterval(interval);
                    setDone(true);
                    onCompleteRef.current?.();
                }
            }, speed);
            return () => clearInterval(interval);
        }, startDelay);

        return () => clearTimeout(startTimer);
    }, [text, speed, startDelay]);

    return {displayed, done};
}
