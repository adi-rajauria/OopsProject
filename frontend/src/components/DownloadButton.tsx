import { useState } from "react";
import { useToast } from "./Toasts";

/** "Download CSV" style button: shows progress and reports a failed download as a toast. */
export function DownloadButton({ label = "Download CSV", onDownload }: { label?: string; onDownload: () => Promise<void> }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try {
      await onDownload();
    } catch (err) {
      toast.error(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" className="btn-secondary btn-sm" disabled={busy} onClick={run}>
      {busy ? "Preparing…" : label}
    </button>
  );
}
