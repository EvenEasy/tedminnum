import {
  createContext,
  useContext,
  useEffect,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from "react";
const ThemeContext = createContext<{
  theme: string;
  setTheme: Dispatch<SetStateAction<string>>;
} | null>(null);
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("theme") || "dark",
  );
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);
  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}
export function useTheme() {
  const theme = useContext(ThemeContext);
  if (!theme) throw new Error("ThemeProvider is required");
  return theme;
}
