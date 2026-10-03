import { useEffect, useState } from "react";

export default function ThemeToggle() {
  const [dark, setDark] = useState(() => localStorage.getItem("idx-theme") === "dark");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("idx-theme", dark ? "dark" : "light");
  }, [dark]);

  return <button
    type="button"
    onClick={() => setDark(value => !value)}
    aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
    title={dark ? "Light mode" : "Dark mode"}
    style={{ border: "1px solid var(--line)", background: "transparent", padding: "4px 8px", fontFamily: "Geist Mono", fontSize: 11, cursor: "pointer" }}
  >
    {dark ? "☀ LIGHT" : "◐ DARK"}
  </button>;
}
