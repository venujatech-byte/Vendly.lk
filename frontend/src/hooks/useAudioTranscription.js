import { useEffect, useRef, useState } from "react";

const MAX_RECORDING_MILLISECONDS = 30_000;

function preferredMimeType() {
  if (!window.MediaRecorder) return "";

  return [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ].find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionForMimeType(mimeType) {
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("mpeg")) return "mp3";
  if (mimeType.includes("wav")) return "wav";
  return "webm";
}

function microphoneError(error) {
  if (!window.isSecureContext) {
    return "Voice input needs HTTPS or localhost. You can still type your message.";
  }
  if (error?.name === "NotAllowedError") {
    return "Microphone access was blocked. Allow microphone permission and try again.";
  }
  if (error?.name === "NotFoundError") {
    return "No microphone was found on this device.";
  }
  return error?.message || "Voice input could not start. Please try again.";
}

/** Record microphone audio and send it to a caller-provided transcription API. */
export function useAudioTranscription({ language, transcribe, onTranscript, onError }) {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const recorderRef = useRef(null);
  const streamRef = useRef(null);
  const chunksRef = useRef([]);
  const timeoutRef = useRef(null);
  const mountedRef = useRef(true);
  const callbacksRef = useRef({ language, transcribe, onTranscript, onError });
  callbacksRef.current = { language, transcribe, onTranscript, onError };

  function releaseMicrophone() {
    window.clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function stopRecording() {
    const recorder = recorderRef.current;
    if (recorder?.state === "recording") recorder.stop();
  }

  async function startRecording() {
    if (isRecording || isTranscribing) return;

    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      callbacksRef.current.onError?.(new Error(
        "Voice input needs a supported browser on HTTPS or localhost.",
      ));
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = preferredMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      streamRef.current = stream;
      recorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data);
      };
      recorder.onerror = (event) => {
        callbacksRef.current.onError?.(new Error(
          event.error?.message || "The microphone recording failed.",
        ));
      };
      recorder.onstop = async () => {
        const recordingType = recorder.mimeType || mimeType || "audio/webm";
        const audio = new Blob(chunksRef.current, { type: recordingType });
        recorderRef.current = null;
        releaseMicrophone();
        if (!mountedRef.current) return;
        setIsRecording(false);
        setIsTranscribing(true);

        try {
          const transcript = await callbacksRef.current.transcribe(
            audio,
            `voice-message.${extensionForMimeType(recordingType)}`,
            callbacksRef.current.language,
          );
          if (mountedRef.current) callbacksRef.current.onTranscript?.(transcript);
        } catch (error) {
          if (mountedRef.current) callbacksRef.current.onError?.(error);
        } finally {
          if (mountedRef.current) setIsTranscribing(false);
        }
      };

      recorder.start(250);
      setIsRecording(true);
      timeoutRef.current = window.setTimeout(stopRecording, MAX_RECORDING_MILLISECONDS);
    } catch (error) {
      releaseMicrophone();
      callbacksRef.current.onError?.(new Error(microphoneError(error)));
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const recorder = recorderRef.current;
      if (recorder?.state === "recording") recorder.stop();
      releaseMicrophone();
    };
  }, []);

  return { isRecording, isTranscribing, startRecording, stopRecording };
}
