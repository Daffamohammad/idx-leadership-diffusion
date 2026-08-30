import { useState } from "react";

interface Props extends React.ImgHTMLAttributes<HTMLImageElement> {
  fallbackLabel?: string;
}

export default function ImageWithFallback({ alt, fallbackLabel = "Image unavailable", ...props }: Props) {
  const [failed, setFailed] = useState(false);
  if (failed) return <div role="img" aria-label={alt} style={{ display: "grid", placeItems: "center", height: "100%", color: "#686e73", fontSize: 12, background: "#ffffff" }}>{fallbackLabel}</div>;
  return <img {...props} alt={alt} onError={() => setFailed(true)} />;
}
