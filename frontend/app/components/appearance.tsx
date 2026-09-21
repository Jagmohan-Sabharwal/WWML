"use client";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

type Theme = "light" | "dark";
const ThemeContext = createContext({
  theme: "light" as Theme,
  changeTheme: (_theme: Theme) => {},
  persisted: true,
});
export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("light");
  const [persisted, setPersisted] = useState(true);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("wwml-theme");
      if (saved === "light" || saved === "dark") {
        setTheme(saved);
        document.documentElement.dataset.theme = saved;
      }
    } catch {
      setPersisted(false);
    }
  }, []);
  function changeTheme(value: Theme) {
    setTheme(value);
    document.documentElement.dataset.theme = value;
    try {
      localStorage.setItem("wwml-theme", value);
      setPersisted(true);
    } catch {
      setPersisted(false);
    }
  }
  return (
    <ThemeContext.Provider value={{ theme, changeTheme, persisted }}>
      {children}
    </ThemeContext.Provider>
  );
}
export function AppearanceSettings() {
  const { theme, changeTheme, persisted } = useContext(ThemeContext);
  return (
    <fieldset>
      <legend className="text-lg font-semibold">Appearance</legend>
      <p className="mt-2 text-sm text-muted">
        Choose the look of your workspace on this browser.
      </p>
      <div className="mt-5 flex gap-3">
        {(["light", "dark"] as const).map((value) => (
          <label
            key={value}
            className="flex cursor-pointer items-center gap-3 rounded-lg border border-line bg-canvas px-5 py-4 capitalize"
          >
            <input
              type="radio"
              name="theme"
              value={value}
              checked={theme === value}
              onChange={() => changeTheme(value)}
              className="size-4 accent-accent"
            />
            {value}
          </label>
        ))}
      </div>
      <p role="status" className="mt-4 text-xs text-muted">
        {persisted
          ? "Your preference is saved automatically on this browser."
          : "Browser storage is unavailable. Your preference applies for this visit."}
      </p>
    </fieldset>
  );
}
