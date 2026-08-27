// Tiny self-check: node frontend/src/services/orderNotes.test.mjs
import assert from "node:assert/strict";

import { customerNoteFromPrivateNote } from "./orderNotes.js";

// An order placed before `customerNote` existed. The note is the only thing on
// the order nobody in the shop can guess, so losing it to a schema change is
// worse than any formatting problem.
assert.equal(
  customerNoteFromPrivateNote(
    "Created through the public Vendly chatbot. Customer delivery note: leave with security",
  ),
  "leave with security",
);

// The deposit sentence is appended after the note on some orders and must not
// be read as part of what the customer wrote.
assert.equal(
  customerNoteFromPrivateNote(
    "Created through the public Vendly chatbot. Customer delivery note: call before 5pm"
      + " Customer said they will bank transfer the full amount.",
  ),
  "call before 5pm",
);

// A seller's own note is not the customer's words and must never be shown as
// them.
assert.equal(
  customerNoteFromPrivateNote("Ring the bell twice, my own reminder."),
  "",
);

assert.equal(customerNoteFromPrivateNote(""), "");
assert.equal(customerNoteFromPrivateNote(null), "");
assert.equal(customerNoteFromPrivateNote(undefined), "");

console.log("orderNotes: all checks passed");
