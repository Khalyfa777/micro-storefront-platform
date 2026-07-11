"use client";

import { useEffect, useState } from "react";


const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export default function PaymentProcessingPage() {
  const [status, setStatus] = useState("Verifying your payment...");
  const [orderNumber, setOrderNumber] = useState("");
  const [storeSlug, setStoreSlug] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    async function verify() {
      const params = new URLSearchParams(window.location.search);
      const reference = params.get("reference") || params.get("trxref");

      if (!reference) {
        setError("Payment reference not found.");
        setStatus("");
        return;
      }

      try {
        const res = await fetch(`${API_URL}/payments/verify/${reference}`);
        const data = await res.json();

        setStoreSlug(data.store_slug || "");

        if (!res.ok) {
          throw new Error(data.detail || "Could not verify payment");
        }

        if (data.status === "success") {
          setStatus("Payment successful.");
          setOrderNumber(data.order_number);
        } else {
          setStatus("Payment was not successful.");
          setOrderNumber(data.order_number || "");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong");
        setStatus("");
      }
    }

    verify();
  }, []);

  return (
    <main className="not-found">
      <div className="not-found-card">
        <h1>{status || "Payment verification failed"}</h1>

        {orderNumber && (
          <p>
            Order number: <strong>{orderNumber}</strong>
          </p>
        )}

        {error && <p>{error}</p>}

        <a className="btn btn-light" href={storeSlug ? `/${storeSlug}` : "/track"}>
          Back to store
        </a>
      </div>
    </main>
  );
}