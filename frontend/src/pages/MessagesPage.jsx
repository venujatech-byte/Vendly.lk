import { useSearchParams } from "react-router-dom";
import { useAuth } from "../context/authContextValue";
import CustomerMessages from "../components/CustomerMessages";
import "./MessagesPage.css";

export default function MessagesPage() {
  const { business } = useAuth();
  const [searchParams] = useSearchParams();
  const requestedSessionId = searchParams.get("session") || "";

  return (
    <main className="messages-page">
      <CustomerMessages
        businessId={business?.id}
        initialSessionId={requestedSessionId}
      />
    </main>
  );
}
