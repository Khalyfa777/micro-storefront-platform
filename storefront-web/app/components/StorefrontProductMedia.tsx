"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type SyntheticEvent,
} from "react";

import {
  resolveStorefrontMediaUrl,
} from "../lib/api-url";


type MediaPresentation =
  | "tall"
  | "standard"
  | "landscape";
type MediaStatus =
  | "loading"
  | "ready"
  | "failed"
  | "missing";

type MediaState = {
  source: string;
  status: MediaStatus;
  presentation: MediaPresentation | null;
  aspectRatio: number | null;
};

type ProductMediaFrameStyle =
  CSSProperties & {
    "--storefront-product-media-aspect"?: number;
  };

function initialMediaState(
  source: string,
): MediaState {
  return {
    source,
    status: source ? "loading" : "missing",
    presentation: null,
    aspectRatio: null,
  };
}

function getAspectRatio(
  naturalWidth: number,
  naturalHeight: number,
): number | null {
  if (
    !Number.isFinite(naturalWidth) ||
    !Number.isFinite(naturalHeight) ||
    naturalWidth <= 0 ||
    naturalHeight <= 0
  ) {
    return null;
  }

  return naturalWidth / naturalHeight;
}

export function getMediaPresentation(
  naturalWidth: number,
  naturalHeight: number,
): MediaPresentation | null {
  const aspectRatio = getAspectRatio(
    naturalWidth,
    naturalHeight,
  );

  if (aspectRatio === null) {
    return null;
  }

  if (aspectRatio < 0.7) {
    return "tall";
  }

  if (aspectRatio <= 1.35) {
    return "standard";
  }

  return "landscape";
}

function getReadyMediaState(
  current: MediaState,
  resolvedSource: string,
  naturalWidth: number,
  naturalHeight: number,
): MediaState {
  if (current.source !== resolvedSource) {
    return current;
  }

  const aspectRatio = getAspectRatio(
    naturalWidth,
    naturalHeight,
  );
  const presentation = getMediaPresentation(
    naturalWidth,
    naturalHeight,
  );

  if (
    aspectRatio === null ||
    presentation === null
  ) {
    return {
      source: resolvedSource,
      status: "failed",
      presentation: null,
      aspectRatio: null,
    };
  }

  if (
    current.status === "ready" &&
    current.presentation === presentation &&
    current.aspectRatio === aspectRatio
  ) {
    return current;
  }

  return {
    source: resolvedSource,
    status: "ready",
    presentation,
    aspectRatio,
  };
}

function getFailedMediaState(
  current: MediaState,
  resolvedSource: string,
): MediaState {
  if (current.source !== resolvedSource) {
    return current;
  }

  if (
    current.status === "failed" &&
    current.presentation === null &&
    current.aspectRatio === null
  ) {
    return current;
  }

  return {
    source: resolvedSource,
    status: "failed",
    presentation: null,
    aspectRatio: null,
  };
}

export default function StorefrontProductMedia({
  imageUrl,
}: {
  imageUrl?: string | null;
}) {
  const resolvedSource = useMemo(
    () => resolveStorefrontMediaUrl(imageUrl),
    [imageUrl],
  );

  const [state, setState] = useState<MediaState>(
    () => initialMediaState(resolvedSource),
  );

  const imageRef =
    useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    setState((current) => {
      if (current.source === resolvedSource) {
        return current;
      }

      return initialMediaState(resolvedSource);
    });
  }, [resolvedSource]);

  useEffect(() => {
    const synchronizeImageState = () => {
      const image = imageRef.current;

      if (!image || !image.complete) {
        return;
      }

      const {
        naturalWidth,
        naturalHeight,
      } = image;

      setState((current) =>
        naturalWidth > 0 &&
        naturalHeight > 0
          ? getReadyMediaState(
              current,
              resolvedSource,
              naturalWidth,
              naturalHeight,
            )
          : getFailedMediaState(
              current,
              resolvedSource,
            ),
      );
    };

    synchronizeImageState();

    window.addEventListener(
      "pageshow",
      synchronizeImageState,
    );

    return () => {
      window.removeEventListener(
        "pageshow",
        synchronizeImageState,
      );
    };
  }, [resolvedSource]);

  const effectiveState =
    state.source === resolvedSource
      ? state
      : initialMediaState(resolvedSource);

  const handleLoad = (
    event: SyntheticEvent<
      HTMLImageElement,
      Event
    >,
  ) => {
    const {
      naturalWidth,
      naturalHeight,
    } = event.currentTarget;

    setState((current) =>
      getReadyMediaState(
        current,
        resolvedSource,
        naturalWidth,
        naturalHeight,
      ),
    );
  };

  const handleError = () => {
    setState((current) =>
      getFailedMediaState(
        current,
        resolvedSource,
      ),
    );
  };

  const showImage =
    Boolean(resolvedSource) &&
    effectiveState.status !== "failed";

  const showFallback =
    effectiveState.status === "failed" ||
    effectiveState.status === "missing";

  const frameStyle:
    ProductMediaFrameStyle | undefined =
      effectiveState.presentation === "landscape" &&
      effectiveState.aspectRatio !== null
        ? {
            "--storefront-product-media-aspect":
              effectiveState.aspectRatio,
          }
        : undefined;

  return (
    <span
      className={
        `storefront-product-media ` +
        `storefront-product-media--${effectiveState.status}`
      }
      data-presentation={
        effectiveState.presentation || undefined
      }
    >
      <span
        className="storefront-product-media-inner"
      >
        <span
          className="storefront-product-media-frame"
          style={frameStyle}
        >
          {showImage && (
            <img
              alt=""
              className="storefront-product-media-image"
              decoding="async"
              draggable={false}
              loading="lazy"
              onError={handleError}
              onLoad={handleLoad}
              ref={imageRef}
              src={resolvedSource}
            />
          )}
        </span>
      </span>

      {effectiveState.status === "loading" && (
        <span
          aria-hidden="true"
          className="storefront-product-media-skeleton"
        />
      )}

      {showFallback && (
        <span
          className="storefront-product-media-fallback"
        >
          <svg
            aria-hidden="true"
            focusable="false"
            viewBox="0 0 24 24"
          >
            <path
              d="M4.75 6.75A2.75 2.75 0 0 1 7.5 4h9A2.75 2.75 0 0 1 19.25 6.75v10.5A2.75 2.75 0 0 1 16.5 20h-9a2.75 2.75 0 0 1-2.75-2.75V6.75Zm2.75-1.25c-.69 0-1.25.56-1.25 1.25v7.47l2.77-2.77a1.75 1.75 0 0 1 2.48 0l1.4 1.4 1.02-1.02a1.75 1.75 0 0 1 2.48 0l1.35 1.35V6.75c0-.69-.56-1.25-1.25-1.25h-9Zm10.25 9.8-2.4-2.4a.25.25 0 0 0-.36 0l-1.55 1.55a.75.75 0 0 1-1.06 0l-1.93-1.93a.25.25 0 0 0-.36 0l-3.84 3.84v.89c0 .69.56 1.25 1.25 1.25h9c.69 0 1.25-.56 1.25-1.25V15.3ZM9 9.25a1.25 1.25 0 1 1 2.5 0 1.25 1.25 0 0 1-2.5 0Z"
              fill="currentColor"
            />
          </svg>
          <span>Image unavailable</span>
        </span>
      )}
    </span>
  );
}
