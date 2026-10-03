import { useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

const STORAGE_KEY = "idx-leadership-local-profile";
function readName(): string {
  try { return (localStorage.getItem(STORAGE_KEY) ?? "").slice(0, 40); } catch { return ""; }
}

export default function LocalProfile({ compact = false }: { compact?: boolean }) {
  const titleId = useId();
  const [name, setName] = useState(readName);
  const [draft, setDraft] = useState(name);
  const [error, setError] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const initials = name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase() || "ME";
  return (
    <>
      <button type="button" className="local-profile-button" aria-label="Open local profile" aria-haspopup="dialog"
        title={name || "Local profile"} onClick={() => {
          const saved = readName(); setName(saved); setDraft(saved); setError(""); dialog.current?.showModal();
        }}>
        <span className="profile-avatar" aria-hidden="true">{initials}</span>
        {!compact && <span>{name || "Local profile"}</span>}
      </button>
      {createPortal(<dialog ref={dialog} className="local-profile-dialog" aria-labelledby={titleId}>
        <form onSubmit={event => {
          event.preventDefault();
          try {
            localStorage.setItem(STORAGE_KEY, draft.trim()); setName(draft.trim()); dialog.current?.close();
          } catch { setError("Your browser could not save the profile. Please allow local storage and try again."); }
        }}>
          <h2 id={titleId}>Local profile</h2>
          <p>Your name and initials are saved on this device.</p>
          <label>Display name<input autoFocus value={draft} maxLength={40} onChange={event => setDraft(event.target.value)} /></label>
          {error && <p role="alert">{error}</p>}
          <div className="profile-actions">
            <button type="button" onClick={() => dialog.current?.close()}>Cancel</button>
            <button type="submit">Save profile</button>
          </div>
        </form>
      </dialog>, document.body)}
    </>
  );
}
