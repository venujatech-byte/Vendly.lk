// Tiny self-check: node frontend/src/data/storefrontText.test.mjs
import assert from "node:assert/strict";

import STOREFRONT_TEXT, { storefrontText } from "./storefrontText.js";

const englishKeys = Object.keys(STOREFRONT_TEXT.en).sort();

for (const language of ["si", "ta"]) {
  assert.deepEqual(
    Object.keys(STOREFRONT_TEXT[language]).sort(),
    englishKeys,
    `${language} is missing or has extra keys versus en`,
  );
  for (const key of englishKeys) {
    assert.notEqual(
      STOREFRONT_TEXT[language][key],
      STOREFRONT_TEXT.en[key],
      `${language}.${key} was left as the English string`,
    );
  }
}

// An unknown or missing language must fall back rather than render blanks.
assert.equal(storefrontText("fr").showProducts, STOREFRONT_TEXT.en.showProducts);
assert.equal(storefrontText(undefined).typeMessage, STOREFRONT_TEXT.en.typeMessage);
assert.equal(storefrontText("si").showProducts, STOREFRONT_TEXT.si.showProducts);

console.log("storefrontText: all checks passed");
