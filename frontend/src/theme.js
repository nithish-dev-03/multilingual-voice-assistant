import { createTheme } from "@mui/material/styles";

export function buildTheme(mode) {
  const isDark = mode === "dark";

  return createTheme({
    palette: {
      mode,
      primary: {
        main: isDark ? "#38bdf8" : "#0284c7",
      },
      secondary: {
        main: isDark ? "#2dd4bf" : "#0d9488",
      },
      background: {
        default: isDark ? "#0b1120" : "#f4f7fb",
        paper: isDark ? "#111827" : "#ffffff",
      },
    },
    shape: {
      borderRadius: 14,
    },
    typography: {
      fontFamily: [
        "Inter",
        "-apple-system",
        "BlinkMacSystemFont",
        '"Segoe UI"',
        "Roboto",
        "sans-serif",
      ].join(","),
    },
    components: {
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: "none",
          },
        },
      },
    },
  });
}
