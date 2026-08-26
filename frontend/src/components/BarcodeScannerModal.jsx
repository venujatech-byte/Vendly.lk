import { useEffect, useRef, useState } from "react";
import { Camera, ScanBarcode, X } from "lucide-react";

import "./BarcodeScannerModal.css";

const BARCODE_FORMATS = [
  "ean_13",
  "ean_8",
  "code_128",
  "code_39",
  "qr_code",
];

function BarcodeScannerModal({
  isOpen,
  onClose,
  onDetected,
  title = "Scan barcode",
  description = "Place the barcode inside the camera frame.",
  manualLabel = "Or enter the barcode",
  inputPlaceholder = "Enter EAN, Code 128, Code 39 or QR value",
  submitLabel = "Use barcode",
}) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const hasDetectedRef = useRef(false);
  const [manualValue, setManualValue] = useState("");
  const [scannerError, setScannerError] = useState("");
  const [isCameraReady, setIsCameraReady] = useState(false);

  useEffect(() => {
    if (!isOpen) return undefined;

    let isActive = true;
    hasDetectedRef.current = false;
    setManualValue("");
    setScannerError("");
    setIsCameraReady(false);

    function stopCamera() {
      if (timerRef.current) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }

      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;

      if (videoRef.current) videoRef.current.srcObject = null;
    }

    async function startCamera() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setScannerError(
          "Camera access is unavailable. Open Vendly through HTTPS or localhost, or enter the barcode below.",
        );
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: "environment" },
          },
          audio: false,
        });

        if (!isActive) {
          stream.getTracks().forEach((track) => track.stop());
          return;
        }

        streamRef.current = stream;
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setIsCameraReady(true);

        // Opening a camera and detecting a barcode are separate browser
        // capabilities. Keep the preview working even if the native detector
        // is unavailable.
        if (!("BarcodeDetector" in window)) {
          setScannerError(
            "The camera is open, but automatic barcode detection is not supported by this browser. Try Chrome or Edge, or enter the barcode below.",
          );
          return;
        }

        const detector = new window.BarcodeDetector({ formats: BARCODE_FORMATS });

        async function detectBarcode() {
          if (!isActive || hasDetectedRef.current || !videoRef.current) return;

          try {
            const results = await detector.detect(videoRef.current);
            const value = results[0]?.rawValue?.trim();

            if (value) {
              hasDetectedRef.current = true;
              stopCamera();
              onDetected(value);
              return;
            }
          } catch (error) {
            console.error("Barcode frame could not be scanned:", error);
          }

          timerRef.current = window.setTimeout(detectBarcode, 350);
        }

        detectBarcode();
      } catch (error) {
        console.error("Camera could not be started:", error);
        setScannerError(
          error?.name === "NotAllowedError"
            ? "Camera permission was denied. Allow camera access or enter the barcode below."
            : "The camera could not be opened. Enter the barcode below instead.",
        );
      }
    }

    startCamera();

    return () => {
      isActive = false;
      stopCamera();
    };
  }, [isOpen, onDetected]);

  if (!isOpen) return null;

  function submitManualBarcode(event) {
    event.preventDefault();
    const value = manualValue.trim();
    if (value) onDetected(value);
  }

  return (
    <div className="barcode-scanner" role="presentation" onMouseDown={onClose}>
      <section
        className="barcode-scanner__dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="barcode-scanner-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="barcode-scanner__header">
          <div>
            <span className="barcode-scanner__icon"><ScanBarcode size={21} /></span>
            <div>
              <h2 id="barcode-scanner-title">{title}</h2>
              <p>{description}</p>
            </div>
          </div>
          <button type="button" onClick={onClose} aria-label="Close barcode scanner">
            <X size={20} />
          </button>
        </header>

        <div className="barcode-scanner__viewport">
          <video ref={videoRef} autoPlay muted playsInline aria-label="Barcode camera preview" />
          <div className="barcode-scanner__frame" aria-hidden="true" />
          {!isCameraReady && !scannerError && (
            <p><Camera size={20} /> Starting camera…</p>
          )}
        </div>

        {scannerError && <p className="barcode-scanner__error" role="alert">{scannerError}</p>}

        <form className="barcode-scanner__manual" onSubmit={submitManualBarcode}>
          <label htmlFor="manual-barcode">{manualLabel}</label>
          <div>
            <input
              id="manual-barcode"
              value={manualValue}
              onChange={(event) => setManualValue(event.target.value)}
              placeholder={inputPlaceholder}
              autoComplete="off"
            />
            <button type="submit" disabled={!manualValue.trim()}>{submitLabel}</button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default BarcodeScannerModal;
