// The chatbot originally wrote the customer's delivery note into the seller's
// `privateNote`, behind this exact phrase and sometimes followed by a sentence
// about a bank transfer. Orders placed before `customerNote` existed still
// carry it that way, so it is recovered rather than lost to the seller.
const LEGACY_NOTE_MARKER = "Customer delivery note: ";
const LEGACY_NOTE_SUFFIX = " Customer said they will bank transfer";

export function customerNoteFromPrivateNote(privateNote) {
  const text = String(privateNote || "");
  const start = text.indexOf(LEGACY_NOTE_MARKER);

  if (start === -1) return "";

  const note = text.slice(start + LEGACY_NOTE_MARKER.length);
  const suffix = note.indexOf(LEGACY_NOTE_SUFFIX);

  return (suffix === -1 ? note : note.slice(0, suffix)).trim();
}
