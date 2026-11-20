import { useEffect, useEffectEvent, useState } from "react";

export default function PrivateChatAttachment({ className, alt, loadLink }) {
  const [url, setUrl] = useState("");
  const [failed, setFailed] = useState(false);
  const loadPreview = useEffectEvent(async (signal) => {
    try {
      const link = await loadLink(signal);
      if (!signal.aborted) setUrl(link.url);
    } catch {
      if (!signal.aborted) setFailed(true);
    }
  });

  // Keep signed URLs in memory for this mounted attachment only.
  useEffect(() => {
    const controller = new AbortController();
    loadPreview(controller.signal);
    return () => controller.abort();
  }, []);

  async function openAttachment(event) {
    // Recheck access and refresh the URL even when the thumbnail is still displayed.
    event.preventDefault();
    const tab = window.open("about:blank", "_blank");
    if (!tab) return;
    tab.opener = null;
    try {
      const link = await loadLink();
      tab.location.replace(link.url);
      if (failed) {
        setUrl(link.url);
        setFailed(false);
      }
    } catch {
      tab.close();
      setFailed(true);
    }
  }

  if (failed) {
    return <button type="button" onClick={openAttachment}>{alt}</button>;
  }
  if (!url) return null;

  return (
    <a className={className} href={url} target="_blank" rel="noreferrer" onClick={openAttachment}>
      <img src={url} alt={alt} onError={() => setFailed(true)} referrerPolicy="no-referrer" />
    </a>
  );
}
