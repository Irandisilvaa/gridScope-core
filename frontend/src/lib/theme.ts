/**
 * GridScope Design Tokens & Palette System
 * Centralized design system constants - avoids hardcoded hex color codes across components.
 */

export const THEME_COLORS = {
  brand: {
    yellow: "#FFD400",
    yellowHover: "#FFE033",
    yellowMuted: "rgba(255, 212, 0, 0.12)",
  },
  surface: {
    black: "#050505",
    surface: "#0A0A0A",
    surfaceAlt: "#0B0B0B",
    surfaceModal: "#070707",
    raised: "#121212",
    elevated: "#141414",
    elevatedAlt: "#161616",
    graphite: "#181818",
    graphiteLight: "#222222",
  },
  border: {
    subtle: "#1C1C1C",
    subtleAlt: "#202020",
    surface: "#242424",
    default: "#262626",
    card: "#2B2B2B",
    strong: "#383838",
  },
  text: {
    white: "#FFFFFF",
    subtle: "#CCCCCC",
    light: "#A0A0A0",
    gray: "#8A8A8A",
    muted: "#777777",
    dim: "#666666",
    placeholder: "#555555",
    dark: "#4A4A4A",
  },
  status: {
    success: "#22C55E",
    danger: "#EF4444",
    warning: "#F59E0B",
    info: "#3B82F6",
    purple: "#8B5CF6",
  },
} as const;

export type ThemeColors = typeof THEME_COLORS;
