import React from "react";

const ThemeContext = React.createContext({ dark: false, toggle: () => {} });

export const ThemeProvider = ({ children }) => {
  const [dark, setDark] = React.useState(() => {
    const saved = localStorage.getItem("capx-dark-mode");
    return saved === "true";
  });
  React.useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
    localStorage.setItem("capx-dark-mode", dark);
  }, [dark]);
  const toggle = () => setDark((d) => !d);
  return <ThemeContext.Provider value={{ dark, toggle }}>{children}</ThemeContext.Provider>;
};

export const useTheme = () => React.useContext(ThemeContext);

export default ThemeContext;
