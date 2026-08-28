import {
  Bot,
  Check,
  Mic,
  MicOff,
  Send,
  Sparkles,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { useAuth } from "../context/authContextValue";
import {
  sendBusinessAssistantMessage,
  transcribeBusinessAssistantAudio,
} from "../services/businessAssistantService";
import { downloadOrderExport, printWaybill } from "../services/operationService";
import { downloadInventoryCsv, getProducts } from "../services/productService";
import { downloadCustomersCsv, getCustomers } from "../services/customerService";
import { getShopSales } from "../services/shopSaleService";
import { downloadReceiptPdf } from "../services/receiptService";
import "./BusinessAssistant.css";

const starterMessage = {
  id: "assistant-welcome",
  role: "assistant",
  text: "Hello! I can summarize your business, search and filter records, open dashboard tools and settings, export data, and safely prepare status or stock updates.",
  suggestions: ["Today's summary", "Filter packed orders", "Open customer messages", "Add a new order"],
};

const AUDIO_MIME_TYPES = [
  "audio/webm;codecs=opus",
  "audio/ogg;codecs=opus",
  "audio/mp4",
  "audio/webm",
];

const VOICE_AGENT = String(import.meta.env.VITE_VOICE_AGENT || "ai")
  .trim()
  .toLowerCase();
const USE_BROWSER_VOICE_AGENT = VOICE_AGENT === "browser";

function preferredAudioMimeType() {
  if (!window.MediaRecorder?.isTypeSupported) return "";
  return AUDIO_MIME_TYPES.find((type) => window.MediaRecorder.isTypeSupported(type)) || "";
}

function audioFileExtension(mimeType) {
  if (mimeType.includes("wav")) return "wav";
  if (mimeType.includes("ogg")) return "ogg";
  if (mimeType.includes("mp4")) return "m4a";
  return "webm";
}

function mixAudioBufferToMono(audioBuffer) {
  const monoSamples = new Float32Array(audioBuffer.length);

  for (let channelIndex = 0; channelIndex < audioBuffer.numberOfChannels; channelIndex += 1) {
    const channelSamples = audioBuffer.getChannelData(channelIndex);
    for (let sampleIndex = 0; sampleIndex < channelSamples.length; sampleIndex += 1) {
      monoSamples[sampleIndex] += channelSamples[sampleIndex] / audioBuffer.numberOfChannels;
    }
  }

  return monoSamples;
}

function resampleAudio(samples, inputSampleRate, outputSampleRate = 16000) {
  if (inputSampleRate === outputSampleRate) return samples;

  const sampleRateRatio = inputSampleRate / outputSampleRate;
  const outputLength = Math.max(1, Math.round(samples.length / sampleRateRatio));
  const output = new Float32Array(outputLength);

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const inputStart = Math.round(outputIndex * sampleRateRatio);
    const inputEnd = Math.min(
      samples.length,
      Math.max(inputStart + 1, Math.round((outputIndex + 1) * sampleRateRatio)),
    );
    let total = 0;

    for (let inputIndex = inputStart; inputIndex < inputEnd; inputIndex += 1) {
      total += samples[inputIndex];
    }
    output[outputIndex] = total / (inputEnd - inputStart);
  }

  return output;
}

function normalizeVoiceSamples(samples) {
  let peak = 0;
  let squareTotal = 0;

  for (const sample of samples) {
    const absoluteSample = Math.abs(sample);
    if (absoluteSample > peak) peak = absoluteSample;
    squareTotal += sample * sample;
  }

  const rms = Math.sqrt(squareTotal / Math.max(1, samples.length));
  if (rms < 0.001) {
    throw new Error("The recording is too quiet. Move closer to the microphone and try again.");
  }

  const gain = peak > 0 ? Math.min(6, 0.92 / peak) : 1;
  if (gain <= 1.05) return samples;

  const normalized = new Float32Array(samples.length);
  for (let index = 0; index < samples.length; index += 1) {
    normalized[index] = Math.max(-1, Math.min(1, samples[index] * gain));
  }
  return normalized;
}

function encodePcmWav(samples, sampleRate) {
  const bytesPerSample = 2;
  const wavBuffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(wavBuffer);

  const writeText = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (const sample of samples) {
    const clampedSample = Math.max(-1, Math.min(1, sample));
    view.setInt16(
      offset,
      clampedSample < 0 ? clampedSample * 0x8000 : clampedSample * 0x7fff,
      true,
    );
    offset += bytesPerSample;
  }

  return wavBuffer;
}

async function prepareWhisperAudio(recordedBlob) {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  if (!AudioContext) return null;

  const audioContext = new AudioContext();
  try {
    const audioBuffer = await audioContext.decodeAudioData(await recordedBlob.arrayBuffer());
    const monoSamples = mixAudioBufferToMono(audioBuffer);
    const whisperSampleRate = Math.min(16000, audioBuffer.sampleRate);
    const resampledSamples = resampleAudio(
      monoSamples,
      audioBuffer.sampleRate,
      whisperSampleRate,
    );
    const normalizedSamples = normalizeVoiceSamples(resampledSamples);
    const wavBuffer = encodePcmWav(normalizedSamples, whisperSampleRate);

    return new Blob([wavBuffer], { type: "audio/wav" });
  } finally {
    audioContext.close().catch(() => {});
  }
}

function messageId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function friendlyError(error) {
  return error?.message || "The business assistant could not complete that request.";
}

function isResetFilterCommand(message) {
  const normalizedMessage = String(message || "").trim().toLowerCase();

  return (
    /\b(reset|clear|remove)\b.*\b(filters?|search)\b/.test(normalizedMessage)
    || /\b(filters?|search)\b.*\b(reset|clear|remove)\b/.test(normalizedMessage)
    || /\bshow\s+(all|everything)(\s+records?)?\b/.test(normalizedMessage)
  );
}

function downloadShopSalesCsv(sales) {
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const headings = ["Sale number", "Customer", "Phone", "Items", "Subtotal", "Discount", "Total", "Date"];
  const rows = sales.filter((sale) => sale.status !== "voided").map((sale) => [
    sale.saleNumber,
    sale.customerName || "Walk-in customer",
    sale.phoneNumber || "",
    (sale.items || []).map((item) => `${item.name} x ${item.quantity}`).join("; "),
    (sale.subtotalMinor || 0) / 100,
    (sale.discountTotalMinor || 0) / 100,
    (sale.totalAmountMinor || 0) / 100,
    String(sale.createdAt || "").slice(0, 10),
  ]);
  const csv = [headings, ...rows].map((row) => row.map(escape).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = `vendly-shop-sales-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function BusinessAssistant({ isOpen, onToggle, onClose }) {
  const navigate = useNavigate();
  const { business } = useAuth();
  const [messages, setMessages] = useState([starterMessage]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [speechEnabled, setSpeechEnabled] = useState(false);
  const [voiceLanguage, setVoiceLanguage] = useState("en-LK");
  const messageListRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const browserRecognitionRef = useRef(null);
  const browserTranscriptRef = useRef("");
  const browserRecognitionErrorRef = useRef(false);
  const livePreviewRecognitionRef = useRef(null);
  const livePreviewTranscriptRef = useRef("");
  const isAiRecordingRef = useRef(false);
  const audioChunksRef = useRef([]);
  const recordingStartedAtRef = useRef(0);
  const isStartingVoiceRef = useRef(false);
  const isMountedRef = useRef(true);
  const voiceHoldTimerRef = useRef(null);
  const skipNextAssistantClickRef = useRef(false);
  const voiceStopRequestedRef = useRef(false);
  const [isHoldingVoiceButton, setIsHoldingVoiceButton] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState("");

  useEffect(() => {
    if (!isOpen || !messageListRef.current) return;
    messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
  }, [isOpen, messages, isSending]);

  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      window.clearTimeout(voiceHoldTimerRef.current);
      const recorder = mediaRecorderRef.current;
      if (recorder && recorder.state !== "inactive") recorder.stop();
      browserRecognitionRef.current?.abort();
      livePreviewRecognitionRef.current?.abort();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      window.speechSynthesis?.cancel();
    };
  }, []);

  function speak(text) {
    if (!speechEnabled || !window.speechSynthesis || !text) return;

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = voiceLanguage;
    utterance.rate = 1;
    window.speechSynthesis.speak(utterance);
  }

  function appendAssistantResponse(response) {
    const assistantMessage = {
      id: messageId("assistant"),
      role: "assistant",
      text: response?.message || "I could not prepare a response.",
      cards: response?.cards || [],
      suggestions: response?.suggestions || [],
      pendingAction: response?.pendingAction || null,
    };

    setMessages((current) => [...current, assistantMessage]);
    speak(assistantMessage.text);
  }

  async function executeResponseAction(response) {
    const action = response?.clientAction;

    if (action?.type === "export_orders") {
      await downloadOrderExport(business.id, {
        dateFrom: action.dateFrom || "",
        dateTo: action.dateTo || "",
        status: action.status || "",
      });
      return;
    }

    if (action?.type === "export_sales") {
      const sales = await getShopSales(business.id, {
        dateFrom: action.dateFrom || "",
        dateTo: action.dateTo || "",
      });
      downloadShopSalesCsv(sales);
      return;
    }

    if (action?.type === "print_waybills") {
      action.orders?.forEach((order) => printWaybill(order));
      return;
    }

    if (action?.type === "print_receipts") {
      action.sales?.forEach((sale) => downloadReceiptPdf(business, {
        ...sale,
        orderNumber: sale.saleNumber,
        deliveryFeeMinor: 0,
        taxTotalMinor: 0,
        deliveryAddress: {},
        paymentMethod: "paid",
      }));
      return;
    }

    if (action?.type === "set_theme") {
      window.dispatchEvent(new CustomEvent("vendly:set-theme", { detail: { theme: action.theme } }));
      return;
    }

    if (action?.type === "export_inventory") {
      const products = await getProducts(business.id);
      downloadInventoryCsv(products);
      return;
    }

    if (action?.type === "export_customers") {
      const customers = await getCustomers(business.id);
      downloadCustomersCsv(customers);
      return;
    }

    if (action?.type === "open_settings") {
      window.dispatchEvent(new CustomEvent("vendly:open-settings", {
        detail: { section: action.section || "general" },
      }));
      return;
    }

    if (action?.type === "reset_filters") {
      window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      return;
    }

    if (response?.navigateTo) {
      // Assistant filtering is intentionally replace-not-additive. Reset the
      // previous page's filter state before opening the requested filtered view.
      if (/[?&](search|status|dateFrom|dateTo|stockStatus|sortBy)=/.test(response.navigateTo)) {
        window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      }
      navigate(response.navigateTo);
    }
  }

  async function sendMessage(text) {
    const cleanMessage = text.trim();
    if (!cleanMessage || isSending) return;

    setMessages((current) => [
      ...current,
      { id: messageId("user"), role: "user", text: cleanMessage },
    ]);
    setDraft("");
    setIsSending(true);

    // Resetting filters is a local dashboard command. Handle it before the API
    // call so an AI provider can never reinterpret it as the previous filter.
    if (isResetFilterCommand(cleanMessage)) {
      window.dispatchEvent(new CustomEvent("vendly:reset-filters"));
      appendAssistantResponse({
        message: "Filters cleared. Showing all records again.",
      });
      setIsSending(false);
      return;
    }

    try {
      if (!business?.id) {
        throw new Error("Your business account is still loading. Please try again.");
      }

      const response = await sendBusinessAssistantMessage(business.id, {
        message: cleanMessage,
      });
      appendAssistantResponse(response);
      await executeResponseAction(response);
    } catch (error) {
      appendAssistantResponse({ message: friendlyError(error) });
    } finally {
      setIsSending(false);
    }
  }

  async function confirmAction(action, sourceMessageId) {
    if (isSending) return;
    setIsSending(true);
    setMessages((current) => current.map((message) => (
      message.id === sourceMessageId
        ? { ...message, pendingAction: null, actionState: "confirmed" }
        : message
    )));

    try {
      const response = await sendBusinessAssistantMessage(business.id, {
        confirmedAction: action,
      });
      appendAssistantResponse(response);
      await executeResponseAction(response);
    } catch (error) {
      appendAssistantResponse({ message: friendlyError(error) });
    } finally {
      setIsSending(false);
    }
  }

  function cancelAction(sourceMessageId) {
    setMessages((current) => current.map((message) => (
      message.id === sourceMessageId
        ? { ...message, pendingAction: null, actionState: "cancelled" }
        : message
    )));
  }

  function stopMediaStream() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;
  }

  function startBrowserVoiceInput() {
    window.speechSynthesis?.cancel();

    if (isListening || isTranscribing || isStartingVoiceRef.current) return;

    if (!business?.id) {
      appendAssistantResponse({
        message: "Your business account is still loading. Please try voice input again in a moment.",
      });
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      appendAssistantResponse({
        message: "Browser speech recognition is not supported here. Use Chrome or Edge, or set VITE_VOICE_AGENT=ai.",
      });
      return;
    }

    if (!window.isSecureContext) {
      appendAssistantResponse({
        message: "Microphone access needs HTTPS or localhost. Open the deployed HTTPS site, or use localhost on this computer.",
      });
      return;
    }

    voiceStopRequestedRef.current = false;
    browserTranscriptRef.current = "";
    browserRecognitionErrorRef.current = false;
    isStartingVoiceRef.current = true;
    setVoiceTranscript("Preparing browser speech recognition…");

    const recognition = new SpeechRecognition();
    browserRecognitionRef.current = recognition;
    recognition.lang = voiceLanguage;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      isStartingVoiceRef.current = false;
      setIsListening(true);
      setVoiceTranscript("Listening in browser…");
    };

    recognition.onresult = (event) => {
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0]?.transcript || "";
        if (event.results[index].isFinal) {
          browserTranscriptRef.current += `${transcript} `;
        } else {
          interimTranscript += transcript;
        }
      }

      const visibleTranscript = `${browserTranscriptRef.current}${interimTranscript}`.trim();
      setVoiceTranscript(visibleTranscript || "Listening in browser…");
    };

    recognition.onerror = (event) => {
      if (event.error === "aborted" && voiceStopRequestedRef.current) return;

      browserRecognitionErrorRef.current = true;
      const errorMessages = {
        "not-allowed": "Microphone permission was denied. Allow microphone access in your browser settings and try again.",
        "audio-capture": "No working microphone was found on this device.",
        network: "The browser speech service could not connect. Check your internet connection or use the AI voice provider.",
        "no-speech": "No speech was detected. Press the microphone and try again.",
      };
      appendAssistantResponse({
        message: errorMessages[event.error] || "Browser speech recognition failed. Please try again or use the AI voice provider.",
      });
    };

    recognition.onend = async () => {
      isStartingVoiceRef.current = false;
      setIsListening(false);
      browserRecognitionRef.current = null;

      const transcribedText = browserTranscriptRef.current.trim();
      browserTranscriptRef.current = "";

      if (!isMountedRef.current || browserRecognitionErrorRef.current) {
        setVoiceTranscript("");
        return;
      }

      if (!transcribedText) {
        setVoiceTranscript("");
        if (voiceStopRequestedRef.current) {
          appendAssistantResponse({
            message: "No speech was detected. Hold the microphone and speak your full request.",
          });
        }
        return;
      }

      setDraft(transcribedText);
      setVoiceTranscript(transcribedText);
      await sendMessage(transcribedText);
      if (isMountedRef.current) setVoiceTranscript("");
    };

    try {
      recognition.start();
    } catch {
      isStartingVoiceRef.current = false;
      browserRecognitionRef.current = null;
      setVoiceTranscript("");
      appendAssistantResponse({
        message: "Browser speech recognition could not start. Wait a moment and try again.",
      });
    }
  }

  function stopLiveTranscriptionPreview() {
    const recognition = livePreviewRecognitionRef.current;
    livePreviewRecognitionRef.current = null;
    isAiRecordingRef.current = false;

    if (!recognition) return;
    recognition.onend = null;
    recognition.onresult = null;
    recognition.onerror = null;

    try {
      recognition.stop();
    } catch {
      try {
        recognition.abort();
      } catch {
        // The browser may already have stopped the preview recognizer.
      }
    }
  }

  function startLiveTranscriptionPreview() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition || !window.isSecureContext) return;

    stopLiveTranscriptionPreview();
    isAiRecordingRef.current = true;
    livePreviewTranscriptRef.current = "";

    const recognition = new SpeechRecognition();
    livePreviewRecognitionRef.current = recognition;
    recognition.lang = voiceLanguage;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let interimTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0]?.transcript || "";
        if (event.results[index].isFinal) {
          livePreviewTranscriptRef.current += `${transcript} `;
        } else {
          interimTranscript += transcript;
        }
      }

      const visibleTranscript = `${livePreviewTranscriptRef.current}${interimTranscript}`.trim();
      if (visibleTranscript && isMountedRef.current) setVoiceTranscript(visibleTranscript);
    };

    // Live browser recognition can end after a pause. Restart only the visual
    // preview while MediaRecorder is still capturing the authoritative audio.
    recognition.onend = () => {
      if (!isAiRecordingRef.current || livePreviewRecognitionRef.current !== recognition) return;
      try {
        recognition.start();
      } catch {
        // Whisper still receives the complete recording if preview restart fails.
      }
    };

    recognition.onerror = () => {
      // Live preview is optional. Keep recording for the final Whisper result.
    };

    try {
      recognition.start();
    } catch {
      livePreviewRecognitionRef.current = null;
    }
  }

  async function startVoiceInput() {
    // Stop the current TTS reply before opening the microphone. This prevents
    // the assistant from transcribing its own voice and keeps voice controls
    // predictable for both the composer mic and floating-button long press.
    window.speechSynthesis?.cancel();

    if (USE_BROWSER_VOICE_AGENT) {
      startBrowserVoiceInput();
      return;
    }

    if (isListening || isTranscribing || isStartingVoiceRef.current) return;

    if (!business?.id) {
      appendAssistantResponse({
        message: "Your business account is still loading. Please try voice input again in a moment.",
      });
      return;
    }

    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      appendAssistantResponse({
        message: "Microphone access needs HTTPS or localhost. Open the deployed HTTPS site, or use localhost on this computer.",
      });
      return;
    }

    if (!window.MediaRecorder) {
      appendAssistantResponse({
        message: "Audio recording is not supported by this browser. Please use a current version of Chrome, Edge or Safari.",
      });
      return;
    }

    isStartingVoiceRef.current = true;
    stopMediaStream();
    voiceStopRequestedRef.current = false;
    setVoiceTranscript("Preparing microphone…");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: { ideal: 1 },
          sampleRate: { ideal: 48000 },
          sampleSize: { ideal: 16 },
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      if (voiceStopRequestedRef.current || !isMountedRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        isStartingVoiceRef.current = false;
        setVoiceTranscript("");
        return;
      }

      mediaStreamRef.current = stream;
      audioChunksRef.current = [];
      const selectedMimeType = preferredAudioMimeType();
      const recorderOptions = {
        audioBitsPerSecond: 128000,
        ...(selectedMimeType ? { mimeType: selectedMimeType } : {}),
      };
      let recorder;

      try {
        recorder = new window.MediaRecorder(stream, recorderOptions);
      } catch {
        recorder = new window.MediaRecorder(stream);
      }

      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) audioChunksRef.current.push(event.data);
      };

      recorder.onerror = () => {
        isStartingVoiceRef.current = false;
        stopLiveTranscriptionPreview();
        setIsListening(false);
        stopMediaStream();
        if (!voiceStopRequestedRef.current) {
          appendAssistantResponse({
            message: "The microphone recording failed. Please try again or type your request.",
          });
        }
      };

      recorder.onstart = () => {
        isStartingVoiceRef.current = false;
        recordingStartedAtRef.current = performance.now();
        setVoiceTranscript("Listening…");
        setIsListening(true);
        startLiveTranscriptionPreview();
      };

      recorder.onstop = async () => {
        isStartingVoiceRef.current = false;
        stopLiveTranscriptionPreview();
        setIsListening(false);
        stopMediaStream();

        const durationMilliseconds = performance.now() - recordingStartedAtRef.current;
        const mimeType = recorder.mimeType || selectedMimeType || "audio/webm";
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        audioChunksRef.current = [];

        if (!isMountedRef.current) return;

        if (durationMilliseconds < 600 || audioBlob.size < 512) {
          setVoiceTranscript("");
          appendAssistantResponse({
            message: "That recording was too short. Hold the microphone and speak your full request.",
          });
          return;
        }

        setIsTranscribing(true);
        setVoiceTranscript("Preparing clear audio…");

        try {
          let whisperAudioBlob = audioBlob;
          let whisperMimeType = mimeType;

          try {
            const preparedWav = await prepareWhisperAudio(audioBlob);
            if (preparedWav) {
              whisperAudioBlob = preparedWav;
              whisperMimeType = "audio/wav";
            }
          } catch (audioError) {
            if (audioError?.message?.includes("too quiet")) throw audioError;
            // If this browser cannot decode its own recording, Groq can still
            // receive the original supported MediaRecorder file.
          }

          setVoiceTranscript("Transcribing with Groq…");
          const extension = audioFileExtension(whisperMimeType);
          const transcription = await transcribeBusinessAssistantAudio(
            business.id,
            whisperAudioBlob,
            {
              filename: `business-assistant-${Date.now()}.${extension}`,
              // Let multilingual Whisper detect English, Sinhala, Tamil and
              // mixed-language commands instead of incorrectly forcing the
              // language used for text-to-speech playback.
              language: "",
            },
          );
          const transcribedText = transcription?.text?.trim();
          if (!transcribedText) throw new Error("No speech was detected in the recording.");

          if (isMountedRef.current) {
            setDraft(transcribedText);
            setVoiceTranscript(transcribedText);
            await sendMessage(transcribedText);
          }
        } catch (error) {
          if (isMountedRef.current) {
            appendAssistantResponse({ message: friendlyError(error) });
          }
        } finally {
          if (isMountedRef.current) {
            setIsTranscribing(false);
            setVoiceTranscript("");
          }
        }
      };

      recorder.start(250);
    } catch (error) {
      isStartingVoiceRef.current = false;
      stopLiveTranscriptionPreview();
      stopMediaStream();
      setIsListening(false);
      setVoiceTranscript("");

      const errorMessage = error?.name === "NotAllowedError"
        ? "Microphone permission was denied. Allow microphone access in your browser settings and try again."
        : error?.name === "NotFoundError"
          ? "No microphone was found on this device."
          : "The microphone could not be opened. Please check your browser permissions and try again.";
      appendAssistantResponse({ message: errorMessage });
    }
  }

  function stopVoiceInput() {
    window.speechSynthesis?.cancel();
    voiceStopRequestedRef.current = true;

    if (USE_BROWSER_VOICE_AGENT) {
      const recognition = browserRecognitionRef.current;
      if (recognition) {
        try {
          recognition.stop();
        } catch {
          recognition.abort();
        }
      } else if (!isStartingVoiceRef.current) {
        setIsListening(false);
      }
      return;
    }

    const recorder = mediaRecorderRef.current;

    if (recorder && recorder.state !== "inactive") {
      try {
        recorder.requestData();
      } catch {
        // Some browsers do not allow requestData immediately after start.
      }
      recorder.stop();
      return;
    }

    if (!isStartingVoiceRef.current) {
      stopMediaStream();
      setIsListening(false);
    }
  }

  function startHeldVoiceCommand(event) {
    if (event.button !== undefined && event.button !== 0) return;

    skipNextAssistantClickRef.current = false;
    window.clearTimeout(voiceHoldTimerRef.current);
    voiceHoldTimerRef.current = window.setTimeout(() => {
      skipNextAssistantClickRef.current = true;
      window.speechSynthesis?.cancel();
      setIsHoldingVoiceButton(true);
      startVoiceInput();
    }, 280);
  }

  function finishHeldVoiceCommand() {
    window.clearTimeout(voiceHoldTimerRef.current);
    if (!skipNextAssistantClickRef.current) return;

    setIsHoldingVoiceButton(false);
    stopVoiceInput();
  }

  function cancelHeldVoiceCommand() {
    finishHeldVoiceCommand();
    // Pointer cancellation/leave does not dispatch the normal click that
    // pointer-up does, so do not suppress the seller's next ordinary click.
    skipNextAssistantClickRef.current = false;
  }

  function handleAssistantButtonClick() {
    if (skipNextAssistantClickRef.current) {
      skipNextAssistantClickRef.current = false;
      return;
    }
    onToggle();
  }

  return (
    <>
      <button
        className={`floating-assistant-button ${isListening || isHoldingVoiceButton || isTranscribing ? "is-listening" : ""}`}
        type="button"
        onClick={handleAssistantButtonClick}
        onPointerDown={startHeldVoiceCommand}
        onPointerUp={finishHeldVoiceCommand}
        onPointerLeave={cancelHeldVoiceCommand}
        onPointerCancel={cancelHeldVoiceCommand}
        aria-label={isTranscribing ? "Transcribing voice command" : isListening || isHoldingVoiceButton ? "Listening for a voice command" : isOpen ? "Close business assistant" : "Open business assistant"}
        aria-expanded={isOpen}
        title="Click to open. Press and hold to speak."
      >
        {isListening || isHoldingVoiceButton || isTranscribing ? <Mic aria-hidden="true" /> : isOpen ? <X aria-hidden="true" /> : <Sparkles aria-hidden="true" />}
      </button>

      {(isListening || isHoldingVoiceButton || isTranscribing) && (
        <div className="business-assistant__voice-overlay" aria-live="polite">
          <div className="business-assistant__voice-orb"><Mic aria-hidden="true" /></div>
          <p className="business-assistant__voice-label">
            {isTranscribing ? "Transcribing…" : "Listening…"}
          </p>
          <p className="business-assistant__voice-transcript">
            {voiceTranscript || "Speak your dashboard command"}
          </p>
          <p className="business-assistant__voice-hint">
            {isTranscribing
              ? "Converting your recording to text with Groq"
              : USE_BROWSER_VOICE_AGENT
                ? "Using browser speech recognition · release to finish"
                : "Live preview · Groq Whisper verifies the final text"}
          </p>
        </div>
      )}

      {isOpen && (
        <section
          className="business-assistant"
          role="dialog"
          aria-label="Business Assistant"
        >
          <header className="business-assistant__header">
            <span className="business-assistant__identity">
              <span className="business-assistant__logo"><Bot aria-hidden="true" /></span>
              <span>
                <strong>Business Assistant</strong>
                <small>Permission-aware AI</small>
              </span>
            </span>

            <span className="business-assistant__header-actions">
              <button
                type="button"
                className="business-assistant__language"
                onClick={() => setVoiceLanguage((current) => current === "en-LK" ? "si-LK" : "en-LK")}
                title="Change voice language"
              >
                {voiceLanguage === "en-LK" ? "EN" : "සිං"}
              </button>
              <button
                type="button"
                className="business-assistant__icon-button"
                onClick={() => setSpeechEnabled((current) => !current)}
                aria-label={speechEnabled ? "Turn spoken replies off" : "Turn spoken replies on"}
                aria-pressed={speechEnabled}
              >
                {speechEnabled ? <Volume2 aria-hidden="true" /> : <VolumeX aria-hidden="true" />}
              </button>
              <button
                type="button"
                className="business-assistant__icon-button"
                onClick={onClose}
                aria-label="Close assistant"
              >
                <X aria-hidden="true" />
              </button>
            </span>
          </header>

          <div
            className="business-assistant__messages"
            ref={messageListRef}
            aria-live="polite"
          >
            {messages.map((message) => (
              <article
                className={`business-assistant__message business-assistant__message--${message.role}`}
                key={message.id}
              >
                <p>{message.text}</p>

                {message.cards?.length > 0 && (
                  <div className="business-assistant__cards">
                    {message.cards.map((card, index) => (
                      <button
                        className="business-assistant__card"
                        type="button"
                        key={`${message.id}-${card.id || index}`}
                        onClick={() => card.navigateTo && navigate(card.navigateTo)}
                        disabled={!card.navigateTo}
                      >
                        <span>
                          <strong>{card.title}</strong>
                          {card.subtitle && <small>{card.subtitle}</small>}
                        </span>
                        <span className="business-assistant__card-value">{card.value}</span>
                      </button>
                    ))}
                  </div>
                )}

                {message.pendingAction && (
                  <div className="business-assistant__confirmation">
                    <strong>Confirmation required</strong>
                    <span>{message.pendingAction.label}</span>
                    <div>
                      <button
                        type="button"
                        className="business-assistant__confirm"
                        onClick={() => confirmAction(message.pendingAction, message.id)}
                        disabled={isSending}
                      >
                        <Check aria-hidden="true" /> Confirm
                      </button>
                      <button
                        type="button"
                        onClick={() => cancelAction(message.id)}
                        disabled={isSending}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                )}

                {message.actionState && (
                  <small className="business-assistant__action-state">
                    Action {message.actionState}.
                  </small>
                )}

                {message.suggestions?.length > 0 && (
                  <div className="business-assistant__suggestions">
                    {message.suggestions.map((suggestion) => (
                      <button
                        type="button"
                        key={`${message.id}-${suggestion}`}
                        onClick={() => sendMessage(suggestion)}
                        disabled={isSending}
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </article>
            ))}

            {isSending && (
              <div className="business-assistant__thinking" aria-label="Assistant is thinking">
                <span /> <span /> <span />
              </div>
            )}
          </div>

          <form
            className="business-assistant__composer"
            onSubmit={(event) => {
              event.preventDefault();
              sendMessage(draft);
            }}
          >
            <button
              type="button"
              className={`business-assistant__voice ${isListening || isTranscribing ? "is-listening" : ""}`}
              onClick={isListening ? stopVoiceInput : startVoiceInput}
              aria-label={isTranscribing ? "Transcribing voice command" : isListening ? "Stop listening" : "Use voice input"}
              disabled={isTranscribing || isSending}
            >
              {isListening ? <MicOff aria-hidden="true" /> : <Mic aria-hidden="true" />}
            </button>
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask about your business..."
              aria-label="Assistant request"
              disabled={isSending || isTranscribing}
              autoComplete="off"
            />
            <button
              type="submit"
              className="business-assistant__send"
              aria-label="Send request"
              disabled={isSending || isTranscribing || !draft.trim()}
            >
              <Send aria-hidden="true" />
            </button>
          </form>
        </section>
      )}
    </>
  );
}

export default BusinessAssistant;
