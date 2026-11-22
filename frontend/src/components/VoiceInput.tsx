import { useEffect, useRef } from "react";
import { useSpeechRecognition } from "../hooks/useSpeechRecognition";
import { MicIcon } from "./icons";

type Voice = ReturnType<typeof useSpeechRecognition>;

/** Append a dictated phrase to existing text: capitalised, separated by a space, kept within maxLength. */
export function appendSpoken(current: string, spoken: string, maxLength = 5000): string {
  const sentence = spoken.charAt(0).toUpperCase() + spoken.slice(1);
  return (current.trim() ? `${current.trimEnd()} ${sentence}` : sentence).slice(0, maxLength);
}

/** Mic toggle for a text field; renders nothing where the browser has no speech recognition. */
export function VoiceButton({ voice, label = "Speak instead", className = "" }: { voice: Voice; label?: string; className?: string }) {
  if (!voice.supported) return null;
  return (
    <button type="button" onClick={() => (voice.listening ? voice.stop() : void voice.start())} aria-pressed={voice.listening}
            className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 text-[12.5px] ${
              voice.listening ? "border-critical-solid bg-critical-soft text-critical" : "border-line-strong text-muted hover:text-fg"} ${className}`}>
      <MicIcon size={14} />
      {voice.listening ? "Stop dictation" : label}
    </button>
  );
}

/** What is being heard right now, or why dictation stopped (with the one-time offline download where offered). */
export function VoiceStatus({ voice }: { voice: Voice }) {
  return (
    <>
      {voice.listening && (
        <p className="hint" aria-live="polite">Listening… {voice.interim && <em className="text-fg">{voice.interim}</em>}</p>
      )}
      {voice.error && (
        <p className="hint text-warning">
          {voice.error}
          {voice.offlineAvailable && (
            <>
              {" "}This browser can recognise speech on your computer instead.{" "}
              <button type="button" className="link" disabled={voice.installing} onClick={() => void voice.installOffline()}>
                {voice.installing ? "Downloading offline speech…" : "Download offline speech (one time)"}
              </button>
            </>
          )}
        </p>
      )}
    </>
  );
}

/** Button + status together, for a plain text box: each finished phrase is appended to the value via onChange. */
export function VoiceInput({ value, onChange, maxLength = 5000, label = "Dictate" }: {
  value: string;
  onChange: (text: string) => void;
  maxLength?: number;
  label?: string;
}) {
  // Latest text, updated immediately on each phrase, so two phrases arriving together are both kept.
  const latest = useRef(value);
  useEffect(() => {
    latest.current = value;
  }, [value]);
  const voice = useSpeechRecognition((spoken) => {
    if (!spoken) return;
    latest.current = appendSpoken(latest.current, spoken, maxLength);
    onChange(latest.current);
  });
  if (!voice.supported) return null;
  return (
    <div className="min-w-0">
      <VoiceButton voice={voice} label={label} />
      <VoiceStatus voice={voice} />
    </div>
  );
}
