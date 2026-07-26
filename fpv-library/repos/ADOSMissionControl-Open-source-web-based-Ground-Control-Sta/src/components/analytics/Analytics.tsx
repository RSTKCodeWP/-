import Script from "next/script";

export function Analytics() {
  const src = process.env.NEXT_PUBLIC_ANALYTICS_SCRIPT_URL;
  const id = process.env.NEXT_PUBLIC_ANALYTICS_WEBSITE_ID;
  if (!src || !id) return null;
  return <Script src={src} data-website-id={id} strategy="afterInteractive" defer />;
}
