/** A small inline-SVG icon set (16px grid, 1.6 stroke, currentColor). No icon library needed. */
import type { ReactNode, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 16, children, ...rest }: IconProps & { children: ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth={1.6}
         strokeLinecap="round" strokeLinejoin="round" aria-hidden focusable="false" {...rest}>
      {children}
    </svg>
  );
}

export const SunIcon = (p: IconProps) => (
  <Icon {...p}><circle cx="8" cy="8" r="3" /><path d="M8 1.5v1.3M8 13.2v1.3M1.5 8h1.3M13.2 8h1.3M3.4 3.4l.9.9M11.7 11.7l.9.9M3.4 12.6l.9-.9M11.7 4.3l.9-.9" /></Icon>
);
export const MoonIcon = (p: IconProps) => (
  <Icon {...p}><path d="M13.5 9.6A5.8 5.8 0 0 1 6.4 2.5a5.8 5.8 0 1 0 7.1 7.1Z" /></Icon>
);
export const MonitorIcon = (p: IconProps) => (
  <Icon {...p}><rect x="1.8" y="2.5" width="12.4" height="8.5" rx="1" /><path d="M5.5 14h5M8 11v3" /></Icon>
);
export const BellIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 11.5V7a4 4 0 1 1 8 0v4.5l1 1H3l1-1ZM6.5 14a1.5 1.5 0 0 0 3 0" /></Icon>
);
export const MenuIcon = (p: IconProps) => (
  <Icon {...p}><path d="M2.5 4h11M2.5 8h11M2.5 12h11" /></Icon>
);
export const CloseIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 4l8 8M12 4l-8 8" /></Icon>
);
export const ChevronUpIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 10l4-4 4 4" /></Icon>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Icon {...p}><path d="M6 4l4 4-4 4" /></Icon>
);
export const ArrowLeftIcon = (p: IconProps) => (
  <Icon {...p}><path d="M13 8H3M7 4L3 8l4 4" /></Icon>
);
export const PauseIcon = (p: IconProps) => (
  <Icon {...p}><path d="M5.5 3.5v9M10.5 3.5v9" /></Icon>
);
export const AlertIcon = (p: IconProps) => (
  <Icon {...p}><path d="M8 2.2 14.3 13H1.7L8 2.2ZM8 6.5v3M8 11.3v.2" /></Icon>
);
export const CheckIcon = (p: IconProps) => (
  <Icon {...p}><path d="M3 8.5l3 3 7-7" /></Icon>
);
export const ClockIcon = (p: IconProps) => (
  <Icon {...p}><circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.3 1.5" /></Icon>
);
export const PlusIcon = (p: IconProps) => (
  <Icon {...p}><path d="M8 3v10M3 8h10" /></Icon>
);
export const SearchIcon = (p: IconProps) => (
  <Icon {...p}><circle cx="7" cy="7" r="4.5" /><path d="M10.4 10.4 14 14" /></Icon>
);
export const GridIcon = (p: IconProps) => (
  <Icon {...p}><rect x="2" y="2" width="5" height="5" rx=".6" /><rect x="9" y="2" width="5" height="5" rx=".6" /><rect x="2" y="9" width="5" height="5" rx=".6" /><rect x="9" y="9" width="5" height="5" rx=".6" /></Icon>
);
export const InboxIcon = (p: IconProps) => (
  <Icon {...p}><path d="M2 9.5 3.8 3h8.4L14 9.5V13H2V9.5ZM2 9.5h3.5l1 1.5h3l1-1.5H14" /></Icon>
);
export const ListIcon = (p: IconProps) => (
  <Icon {...p}><path d="M5.5 4h8M5.5 8h8M5.5 12h8M2.5 4h.01M2.5 8h.01M2.5 12h.01" /></Icon>
);
export const UsersIcon = (p: IconProps) => (
  <Icon {...p}><circle cx="6" cy="5.5" r="2.5" /><path d="M1.5 13.5c.4-2.4 2.2-3.8 4.5-3.8s4.1 1.4 4.5 3.8M10.5 3.2a2.5 2.5 0 0 1 0 4.6M12.3 9.9c1.2.6 2 1.8 2.2 3.6" /></Icon>
);
export const GaugeIcon = (p: IconProps) => (
  <Icon {...p}><path d="M2.3 11.5a6 6 0 1 1 11.4 0" /><path d="M8 9.5 10.5 6" /><circle cx="8" cy="10" r=".9" /></Icon>
);
export const NetworkIcon = (p: IconProps) => (
  <Icon {...p}><rect x="6" y="1.8" width="4" height="3.2" rx=".5" /><rect x="1.8" y="11" width="4" height="3.2" rx=".5" /><rect x="10.2" y="11" width="4" height="3.2" rx=".5" /><path d="M8 5v3M3.8 11V8h8.4v3" /></Icon>
);
export const BarsIcon = (p: IconProps) => (
  <Icon {...p}><path d="M2.5 13.5h11M4.5 11V7M8 11V3.5M11.5 11V8.5" /></Icon>
);
export const SlidersIcon = (p: IconProps) => (
  <Icon {...p}><path d="M2.5 4.5h6M11.5 4.5h2M2.5 11.5h2M7.5 11.5h6" /><circle cx="10" cy="4.5" r="1.5" /><circle cx="6" cy="11.5" r="1.5" /></Icon>
);
export const FileIcon = (p: IconProps) => (
  <Icon {...p}><path d="M4 1.8h5.2L12.5 5v9.2H4V1.8Z" /><path d="M9 1.8V5h3.5M6 8h4.5M6 10.8h4.5" /></Icon>
);
export const LogOutIcon = (p: IconProps) => (
  <Icon {...p}><path d="M6 2.5H3v11h3M10 5l3 3-3 3M13 8H6" /></Icon>
);
export const StarIcon = ({ filled = false, ...p }: IconProps & { filled?: boolean }) => (
  <Icon {...p} fill={filled ? "currentColor" : "none"}><path d="m8 1.8 1.9 3.9 4.3.6-3.1 3 .7 4.3L8 11.6l-3.8 2 .7-4.3-3.1-3 4.3-.6L8 1.8Z" /></Icon>
);

/** Brand mark: an SLA clock ring with its gap - the product is about time to resolution. */
export function LogoMark({ size = 24, className = "" }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className={className}>
      <rect width="32" height="32" rx="6" fill="var(--c-brand)" />
      <path d="M16 7.5a8.5 8.5 0 1 1-8.5 8.5" stroke="var(--c-on-brand)" strokeWidth="3" fill="none" strokeLinecap="round" />
      <circle cx="16" cy="16" r="2.6" fill="var(--c-on-brand)" />
    </svg>
  );
}
