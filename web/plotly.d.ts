declare module "plotly.js-dist-min" {
  const Plotly: {
    newPlot: (
      el: HTMLElement,
      data: unknown[],
      layout?: unknown,
      config?: unknown,
    ) => Promise<void>;
    react: (
      el: HTMLElement,
      data: unknown[],
      layout?: unknown,
      config?: unknown,
    ) => Promise<void>;
    purge: (el: HTMLElement) => void;
    Plots: { resize: (el: HTMLElement) => void };
  };
  export default Plotly;
}
