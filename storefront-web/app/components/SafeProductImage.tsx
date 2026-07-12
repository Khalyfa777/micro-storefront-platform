"use client";

import { useEffect, useState } from "react";

type SafeProductImageProps = {
  imageUrl?: string | null;
  productName: string;
  className?: string;
};

type ImageStatus = "idle" | "loading" | "ready" | "failed";

function getInitial(productName: string) {
  const cleanName = String(productName || "").trim();
  return cleanName.charAt(0).toUpperCase() || "P";
}

function resolveImageUrl(raw?: string | null) {
  const value = String(raw ?? "").trim();

  if (!value || value === "null" || value === "undefined") {
    return "";
  }

  if (value.startsWith("data:image/")) return value;
  if (/^https?:\/\//i.test(value)) return value;

  const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
  let apiOrigin = "";

  try {
    apiOrigin = new URL(apiUrl).origin;
  } catch {
    apiOrigin = "";
  }

  if (apiOrigin && (value.startsWith("/static/") || value.startsWith("/uploads/"))) {
    return apiOrigin + value;
  }

  return "";
}

export default function SafeProductImage({
  imageUrl,
  productName,
  className = "",
}: SafeProductImageProps) {
  const [status, setStatus] = useState<ImageStatus>("idle");
  const [safeSrc, setSafeSrc] = useState("");

  const imageClassName = ["product-image", className].filter(Boolean).join(" ");

  useEffect(() => {
    const resolved = resolveImageUrl(imageUrl);

    if (!resolved) {
      setSafeSrc("");
      setStatus("failed");
      return;
    }

    let mounted = true;
    const image = new window.Image();

    setSafeSrc("");
    setStatus("loading");

    image.onload = () => {
      if (!mounted) return;
      setSafeSrc(resolved);
      setStatus("ready");
    };

    image.onerror = () => {
      if (!mounted) return;
      setSafeSrc("");
      setStatus("failed");
    };

    image.src = resolved;

    return () => {
      mounted = false;
      image.onload = null;
      image.onerror = null;
    };
  }, [imageUrl]);

  if (status !== "ready" || !safeSrc) {
    return (
      <div
        className={`${imageClassName} product-image-placeholder safe-product-placeholder safe-product-${status}`}
      >
        <span>{getInitial(productName)}</span>
      </div>
    );
  }

  return (
    <img
      className={imageClassName}
      src={safeSrc}
      alt={productName}
      loading="lazy"
    />
  );
}
