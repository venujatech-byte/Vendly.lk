import { useRef } from "react";
import { resumePublicChatSession } from "../services/publicService";

export function useChatSessionRecovery(session, user, storageKey, onRenewed) {
  const contextRef = useRef(null);
  // Discard recovery state when navigation, account, or the selected conversation changes.
  if (
    contextRef.current?.storageKey !== storageKey ||
    contextRef.current?.sessionId !== session?.sessionId ||
    contextRef.current?.uid !== user?.uid ||
    contextRef.current?.anonymous !== user?.isAnonymous
  ) {
    contextRef.current = {
      storageKey, sessionId: session?.sessionId, uid: user?.uid,
      anonymous: user?.isAnonymous, recovery: null,
    };
  }
  Object.assign(contextRef.current, { session, onRenewed });

  return async function runChatRequest(activeSession, request) {
    const context = contextRef.current;
    try {
      return await request(activeSession);
    } catch (error) {
      // Only explicit expiry is safe to retry; other failures may follow a successful write.
      if (
        error.code !== "chat_session_expired" || !context.uid || context.anonymous ||
        contextRef.current !== context || context.sessionId !== activeSession.sessionId
      ) throw error;

      // Concurrent history/claim/message requests must share one token rotation.
      let recovery = context.recovery;
      if (recovery?.token !== activeSession.sessionToken) {
        if (context.session?.sessionToken !== activeSession.sessionToken) throw error;
        recovery = {
          token: activeSession.sessionToken,
          promise: resumePublicChatSession(activeSession.sessionId),
        };
        context.recovery = recovery;
      }
      let renewed;
      try {
        renewed = await recovery.promise;
      } catch (renewalError) {
        if (context.recovery === recovery) context.recovery = null;
        throw renewalError;
      }
      // A late renewal must never replace another account's or conversation's session.
      if (
        contextRef.current !== context ||
        ![activeSession.sessionToken, renewed.sessionToken].includes(context.session?.sessionToken)
      ) throw error;
      if (context.session.sessionToken !== renewed.sessionToken) {
        context.session = renewed;
        context.onRenewed(renewed);
      }
      return request(renewed);
    }
  };
}
