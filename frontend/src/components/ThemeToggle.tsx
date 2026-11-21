import { useState } from "react";
import { applyTheme, readTheme, type ThemeChoice } from "../lib/theme";
import { MonitorIcon, MoonIcon, SunIcon } from "./icons";

const OPTIONS: { value: ThemeChoice; label: string; Icon: typeof SunIcon }[] = [
  { value: "system", label: "Follow system theme", Icon: MonitorIcon },
  { value: "light", label: "Light theme", Icon: SunIcon },
  { value: "dark", label: "Dark theme", Icon: MoonIcon },
];

export function ThemeToggle() {
  const [choice, setChoice] = useState<ThemeChoice>(readTheme);
  return (
    <div className="inline-flex rounded border border-line bg-surface p-0.5" role="radiogroup" aria-label="Colour theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={choice === value}
          aria-label={label}
          title={label}
          onClick={() => {
            setChoice(value);
            applyTheme(value);
          }}
          className={`grid h-6 w-7 place-items-center rounded-sm transition-colors ${
            choice === value ? "bg-sunken text-fg" : "text-faint hover:text-fg"
          }`}
        >
          <Icon size={14} />
        </button>
      ))}
    </div>
  );
}
