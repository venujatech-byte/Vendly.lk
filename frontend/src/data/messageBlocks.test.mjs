// node frontend/src/data/messageBlocks.test.mjs
import assert from "node:assert/strict";

import { splitMessageBlocks } from "./messageBlocks.js";

const reply = [
  "Here's a quick compare of the power banks:",
  "",
  "| Spec | ASPOR A337 | Xiaomi 20k |",
  "|------|------------|------------|",
  "| Battery Capacity | 30,000 mAh | 20,000 mAh |",
  "| Warranty | 6 months | 1 month |",
  "",
  "Choose the one that fits your need best.",
].join("\n");

const blocks = splitMessageBlocks(reply);
assert.deepEqual(blocks.map((b) => b.type), ["text", "table", "text"]);

const [, table] = blocks;
assert.deepEqual(table.head, ["Spec", "ASPOR A337", "Xiaomi 20k"]);
assert.equal(table.rows.length, 2, "the |---| separator must not become a row");
assert.deepEqual(table.rows[0], ["Battery Capacity", "30,000 mAh", "20,000 mAh"]);

// Plain replies must stay plain — no table, one text block.
const plain = splitMessageBlocks("The ASPOR A337 costs LKR 8,000.00.");
assert.deepEqual(plain.map((b) => b.type), ["text"]);

// A stray pipe in prose is not a table.
assert.deepEqual(
  splitMessageBlocks("Battery | charging info follows").map((b) => b.type),
  ["text"],
);

assert.deepEqual(splitMessageBlocks("").length, 0);

console.log("messageBlocks: all checks passed");
