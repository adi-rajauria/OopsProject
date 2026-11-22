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
  processLocally?: boolean; // experimental: on-device recognition (newer Chrome / Edge)
  onresult: ((event: SpeechResultEvent) => void) | null;
  onerror: ((event: SpeechErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
type LocalStatus = "available" | "downloadable" | "downloading" | "unavailable";
interface LocalOptions {
  langs: string[];
  processLocally: true;
}
interface RecognizerConstructor {
  new (): Recognizer;
  available?: (options: LocalOptions) => Promise<LocalStatus>;
  install?: (options: LocalOptions) => Promise<boolean>;
}

function recognizerClass(): RecognizerConstructor | undefined {
  const w = window as unknown as { SpeechRecognition?: RecognizerConstructor; webkitSpeechRecognition?: RecognizerConstructor };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

/** Chromium browsers that ship the API without a speech service behind it (it always fails with "network"). */
function browserWithoutSpeechService(): string | null {
  const n = navigator as Navigator & { brave?: unknown };
  if (n.brave) return "Brave";
  if (/\bOPR\//.test(navigator.userAgent)) return "Opera";
  if (/\bVivaldi\//.test(navigator.userAgent)) return "Vivaldi";
  return null;
}

/** On-device recognition for the first language that has (or can download) a local model. */
async function localSupport(Recognition: RecognizerConstructor): Promise<{ lang: string; status: LocalStatus } | null> {
  if (!Recognition.available) return null;
  for (const lang of [...new Set([navigator.language || "en-US", "en-US"])]) {
    try {
      const status = await Recognition.available({ langs: [lang], processLocally: true });
      if (status !== "unavailable") return { lang, status };
    } catch {
      return null; // API shape differs in this browser version: just use the normal service
    }
  }
  return null;
}

const ERRORS: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in the browser's address bar and try again.",
  "no-speech": "No speech was heard. Try again a little closer to the microphone.",
  "audio-capture": "No microphone was found.",
  "language-not-supported": "This browser cannot recognise speech in your language.",
};

function networkMessage(): string {
  const browser = browserWithoutSpeechService();
  if (browser) return `${browser} does not include a speech recognition service. Use Google Chrome or Microsoft Edge, or type instead.`;
  return "The browser's speech service could not be reached. This is usually not your internet connection: some networks, VPNs, "
    + "proxies or ad blockers block it. Try another network, or type instead.";
}

/**
 * Dictation through the browser's speech recognition (Chrome / Edge). Uses the on-device model when the browser has
 * one, so it also works where the cloud speech service is blocked. Final phrases go to onText; `interim` shows what
 * is being heard right now.
 */
export function useSpeechRecognition(onText: (text: string) => void) {
  const Recognition = recognizerClass();
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string>();
  const [offlineLang, setOfflineLang] = useState<string | null>(null); // a local model that can be downloaded
  const [installing, setInstalling] = useState(false);
  const recognizer = useRef<Recognizer | null>(null);
  const onTextRef = useRef(onText);
  useEffect(() => {
    onTextRef.current = onText;
  }, [onText]);

  const stop = useCallback(() => recognizer.current?.stop(), []);

  const start = useCallback(async () => {
    if (!Recognition || recognizer.current) return;
    const r = new Recognition();
    recognizer.current = r;
    setError(undefined);
    setOfflineLang(null);
    const local = await localSupport(Recognition);
    r.lang = local?.status === "available" ? local.lang : navigator.language || "en-US";
    if (local?.status === "available") r.processLocally = true;
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
    r.onerror = (event) => {
      if (event.error === "network") {
        setError(networkMessage());
        if (local && local.status !== "available" && Recognition.install) setOfflineLang(local.lang);
      } else {
        setError(ERRORS[event.error] ?? `Speech recognition stopped (${event.error}).`);
      }
    };
    r.onend = () => {
      recognizer.current = null;
      setListening(false);
      setInterim("");
    };
    try {
      r.start();
      setListening(true);
    } catch {
      recognizer.current = null;
      setError("Speech recognition could not start. Try again, or type instead.");
    }
  }, [Recognition]);

  /** One-time download of the browser's on-device speech model, then dictation starts again. */
  const installOffline = useCallback(async () => {
    if (!Recognition?.install || !offlineLang) return;
    setInstalling(true);
    try {
      const ok = await Recognition.install({ langs: [offlineLang], processLocally: true });
      if (ok) {
        setOfflineLang(null);
        await start();
      } else {
        setError("The offline speech model could not be downloaded in this browser.");
      }
    } catch {
      setError("The offline speech model could not be downloaded in this browser.");
    } finally {
      setInstalling(false);
    }
  }, [Recognition, offlineLang, start]);

  useEffect(() => () => recognizer.current?.stop(), []);

  return {
    supported: Recognition !== undefined,
    listening,
    interim,
    error,
    start,
    stop,
    offlineAvailable: offlineLang !== null,
    installing,
    installOffline,
  };
}
