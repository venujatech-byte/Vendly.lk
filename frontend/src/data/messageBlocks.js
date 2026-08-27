// Extracted so the parser can be checked without a DOM. StorefrontPage
// imports it; keep it here rather than duplicating the logic.
export function splitMessageBlocks(text) {
  const lines = String(text || "").split("\n");
  const blocks = [];
  let paragraph = [];
  let table = null;

  const flushParagraph = () => {
    if (paragraph.length) blocks.push({ type: "text", text: paragraph.join("\n") });
    paragraph = [];
  };
  const flushTable = () => {
    if (table && table.rows.length) blocks.push({ type: "table", ...table });
    table = null;
  };
  // A separator row is the |---|---| line under the header.
  const isSeparator = (cells) =>
    cells.length > 0 && cells.every((cell) => /^:?-{2,}:?$/.test(cell.trim()));
  const cellsOf = (line) =>
    line.trim().replace(/^\|/, "").replace(/\|$/, "").split("|").map((cell) => cell.trim());

  lines.forEach((line) => {
    if (line.trim().startsWith("|") && line.includes("|", 1)) {
      const cells = cellsOf(line);
      if (isSeparator(cells)) return;
      if (!table) {
        flushParagraph();
        table = { head: cells, rows: [] };
      } else {
        table.rows.push(cells);
      }
      return;
    }
    flushTable();
    if (line.trim()) paragraph.push(line);
    else flushParagraph();
  });

  flushTable();
  flushParagraph();
  return blocks;
}
