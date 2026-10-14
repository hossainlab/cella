"use client";

import { useEffect, useState } from "react";

/** What the user picked; "system" follows the OS setting. */
export type ThemeChoice = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

export const THEME_STORAGE_KEY = "cella-theme";

/**
 * Runs inline in <head> before first paint so a stored choice never flashes the
 * other theme. Kept as a string because it must not wait for React to load.
 */
export const THEME_INIT_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();`;

export function readChoice(): ThemeChoice {
  try {
    const t = localStorage.getItem(THEME_STORAGE_KEY);
    return t === "light" || t === "dark" ? t : "system";
  } catch {
    return "system";
  }
}

export function applyChoice(choice: ThemeChoice): void {
  const root = document.documentElement;
  if (choice === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", choice);
  try {
    if (choice === "system") localStorage.removeItem(THEME_STORAGE_KEY);
    else localStorage.setItem(THEME_STORAGE_KEY, choice);
  } catch {
    // Storage blocked (private mode): the choice still applies for this page view.
  }
}

function resolve(): ResolvedTheme {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

/** The theme actually on screen; re-renders when the toggle or the OS changes it. */
export function useResolvedTheme(): ResolvedTheme {
  const [theme, setTheme] = useState<ResolvedTheme>("dark");
  useEffect(() => {
    const update = () => setTheme(resolve());
    update();
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    mq.addEventListener("change", update);
    const obs = new MutationObserver(update);
    obs.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });
    return () => {
      mq.removeEventListener("change", update);
      obs.disconnect();
    };
  }, []);
  return theme;
}

/** Current value of a CSS custom property, for canvas/Plotly code that can't use var(). */
export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
}

/** Layout overrides that make a Plotly figure follow the active theme. */
export function plotlyThemeLayout(): Record<string, unknown> {
  const text = cssVar("--plot-text");
  const grid = cssVar("--plot-grid");
  const axis = {
    color: text,
    gridcolor: grid,
    zerolinecolor: grid,
    linecolor: grid,
  };
  return {
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: text },
    legend: { font: { color: text }, bgcolor: "rgba(0,0,0,0)" },
    hoverlabel: {
      bgcolor: cssVar("--plot-hover-bg"),
      font: { color: cssVar("--plot-hover-text") },
    },
    xaxis: axis,
    yaxis: axis,
  };
}
