// Distinct categorical colors for cell types. Golden-angle hue rotation with
// alternating saturation/lightness so even ~50 categories stay distinguishable.
export function categoryColor(i: number): string {
  const hue = (i * 137.508) % 360;
  const sat = 62 + (i % 3) * 10;
  const light = 55 + (i % 2) * 8;
  return `hsl(${hue.toFixed(0)} ${sat}% ${light}%)`;
}
