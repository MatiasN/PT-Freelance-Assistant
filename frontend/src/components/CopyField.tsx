import { useState } from "react";

import type { PortalField } from "../api";

type CopyState = "idle" | "copied" | "failed";

const BUTTON_LABELS: Record<CopyState, string> = {
  idle: "Copy",
  copied: "Copied",
  failed: "Select & copy manually",
};

export function CopyField({ field }: { field: PortalField }) {
  const [state, setState] = useState<CopyState>("idle");

  async function copy() {
    try {
      // navigator.clipboard is undefined outside secure contexts (plain HTTP on the LAN).
      await navigator.clipboard.writeText(field.value);
      setState("copied");
    } catch {
      setState("failed");
    }
    window.setTimeout(() => setState("idle"), 2000);
  }

  return (
    <div className="copy-field">
      <dt>{field.portal_label}</dt>
      <dd>
        <code>{field.value || "—"}</code>
        <button
          type="button"
          onClick={copy}
          disabled={!field.value}
          aria-label={`Copy ${field.portal_label}`}
        >
          {BUTTON_LABELS[state]}
        </button>
        {field.hint && <small>{field.hint}</small>}
      </dd>
    </div>
  );
}
