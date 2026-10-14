import { ORGANS, organSlug } from "@/lib/organs";
import OrganDetail from "./OrganDetail";

// Pre-render one page per organ so the site can be exported as static files.
export const dynamicParams = false;

export function generateStaticParams() {
  return ORGANS.map((organ) => ({ slug: organSlug(organ) }));
}

export default function Page() {
  return <OrganDetail />;
}
