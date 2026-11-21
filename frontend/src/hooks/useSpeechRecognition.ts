import { useCallback, useEffect, useRef, useState } from "react";

/** The Web Speech API is not in TypeScript's DOM types yet; these are the parts we use. */
interface SpeechResult {
  readonly isFinal: boolean;
  readonly 0: { readonly transcript: string };
}
interface SpeechResultEvent {
  readonly resultIndex: number;
  readonly results: ArrayLike<SpeechResult>;
}
interface SpeechErrorEvent {
  readonly error: string;
}
interface Recognizer {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type RecognizerConstructor = new () => Recognizer;

function recognizerClass(): RecognizerConstructor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognizerConstructor; webkitSpeechRecognition?: RecognizerConstructor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in the browser's address bar and try again.",
  "no-speech": "No speech was heard. Try again a little closer to the microphone.",
  "audio-capture": "No microphone was found.",
  network: "Speech recognition needs an internet connection in this browser.",
};

/**
 * Dictation through the browser's speech recognition (Chrome / Edge).
 * Final phrases are handed to onText; `interim` shows what is being heard right now.
 */
export function useSpeechRecognition(onText: (text: string) => void) {
  const Recognition = recognizerClass();
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string>();
  const recognizer = useRef<Recognizer | null>(null);
  const onTextRef = useRef(onText);
  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  const stop = useCallback(() => recognizer.current?.stop(), []);

  const start = useCallback(() => {
    if (!Recognition || recognizer.current) return;
    const r = new Recognition();
    r.lang = navigator.language || "en-US";
    r.continuous = true;
    r.interimResults = true;
    r.onresult = (event) => {
      let heard = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) onTextRef.current(result[0].transcript.trim());
        else heard += result[0].transcript;
      }
      setInterim(heard);
    };
    r.onerror = (event) => setError(ERRORS[event.error] ?? `Speech recognition stopped (${event.error}).`);
    r.onend = () => {
      recognizer.current = null;
      setListening(false);
      setInterim("");
    };
    setError(undefined);
    recognizer.current = r;
    r.start();
    setListening(true);
  }, [Recognition]);

  useEffect(() => () => recognizer.current?.stop(), []);

  return { supported: Recognition !== undefined, listening, interim, error, start, stop };
}
