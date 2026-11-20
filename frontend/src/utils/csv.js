export function escapeCsvCell(value) {
  let text = String(value ?? "");
  // Protect text a spreadsheet could interpret as a formula, including after leading whitespace.
  if (typeof value === "string" && (/^[\t\r\n\0]/.test(text) || /^[=+\-@＝＋－＠]/u.test(text.trimStart()))) {
    text = `'${text}`;
  }
  return `"${text.replaceAll('"', '""')}"`;
}
