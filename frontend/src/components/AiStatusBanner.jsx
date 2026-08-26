import { useEffect, useState } from "react";
import { AlertTriangle, X } from "lucide-react";

import { useAuth } from "../context/authContextValue";
import { getAiStatus } from "../services/businessService";

import "./AiStatusBanner.css";

// A retired model or a revoked key makes every chatbot reply drop back to
// simplified English, in English only, with nothing shown to anyone. It reached
// the server log and stopped there. This is the seller-visible half.
const FAILURE_COPY = {
  configuration: {
    title: "The chatbot's AI is not responding",
    detail:
      "Customer replies have dropped back to simplified English and are no longer answering in Sinhala or Tamil. This does not fix itself — the AI model or API key needs attention.",
  },
  rate_limit: {
    title: "The chatbot's AI is rate limited",
    detail:
      "Some replies are falling back to simplified English while the limit resets. If this keeps appearing, the provider plan needs a higher quota.",
  },
  unavailable: {
    title: "The chatbot's AI could not be reached",
    detail:
      "The last request to the AI provider failed. Replies are falling back to simplified English until it recovers.",
  },
};

// Slow on purpose. This is a background health check, not a live metric, and a
// failure that matters persists for minutes.
const POLL_INTERVAL_MS = 5 * 60 * 1000;

function AiStatusBanner() {
  const { business, membership } = useAuth();
  const [failure, setFailure] = useState(null);
  const [dismissedAt, setDismissedAt] = useState("");
  const canSeeStatus = ["owner", "admin"].includes(membership?.role);

  useEffect(() => {
    if (!business?.id || !canSeeStatus) return undefined;

    let requestIsCurrent = true;

    function check() {
      getAiStatus(business.id)
        .then((result) => {
          if (requestIsCurrent) setFailure(result?.aiStatus?.failure || null);
        })
        // A failing health check must never itself surface an error.
        .catch(() => {});
    }

    check();
    const timer = window.setInterval(check, POLL_INTERVAL_MS);

    return () => {
      requestIsCurrent = false;
      window.clearInterval(timer);
    };
  }, [business?.id, canSeeStatus]);

  // Dismissal is per-occurrence: a newer failure shows again rather than
  // staying hidden because an older one was dismissed.
  if (!failure || failure.at === dismissedAt) return null;

  const copy = FAILURE_COPY[failure.kind] || FAILURE_COPY.unavailable;

  return (
    <div className="ai-status-banner" role="status">
      <AlertTriangle size={18} aria-hidden="true" />
      <div className="ai-status-banner__text">
        <strong>{copy.title}</strong>
        <p>{copy.detail}</p>
        <small>
          {failure.provider} · {failure.model} · last failed{" "}
          {new Date(failure.at).toLocaleString()}
        </small>
      </div>
      <button
        type="button"
        onClick={() => setDismissedAt(failure.at)}
        aria-label="Dismiss this warning"
      >
        <X size={16} />
      </button>
    </div>
  );
}

export default AiStatusBanner;
