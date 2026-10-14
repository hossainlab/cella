import type { Metadata } from "next";
import "./globals.css";
import Nav from "./components/Nav";
import { THEME_INIT_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Cella — cross-organ cell-type identity",
  description:
    "Cella surfaces the discriminative classifier weights behind the CellTypist organ atlases: what defines each cell type, and how it differs across 12 human organs.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Sets data-theme from the stored choice before paint (no flash). */}
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      {/* suppressHydrationWarning: browser extensions (e.g. TTS tools that inject
          a #pronounceRootElement node) mutate <body> before React hydrates,
          causing a benign server/client mismatch that is not from our markup. */}
      <body suppressHydrationWarning>
        <Nav />
        {children}
      </body>
    </html>
  );
}
