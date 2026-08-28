// Tiny self-check: node frontend/src/data/storefrontText.test.mjs
import assert from "node:assert/strict";

import STOREFRONT_TEXT, { storefrontText } from "./storefrontText.js";

const englishKeys = Object.keys(STOREFRONT_TEXT.en).sort();

// Numerals read the same in all three languages, so "differs from English" is
// not a meaningful check for them. Neither are the terms Sri Lankan customers
// say in English while speaking Sinhala or Tamil - translating "Brand" or
// "Warranty" would read as stilted, not as localised.
const SHARED_ACROSS_LANGUAGES = new Set([
  "suggestQty2",
  "suggestQty3",
  "specBrand",
  "specCategory",
  "specWarranty",
  "specSize",
  "filters",
  "sortFeatured",
  "deliveryFee",
  "loginGuest",
  "payCod",
]);

for (const language of ["si", "ta"]) {
  assert.deepEqual(
    Object.keys(STOREFRONT_TEXT[language]).sort(),
    englishKeys,
    `${language} is missing or has extra keys versus en`,
  );
  for (const key of englishKeys) {
    if (SHARED_ACROSS_LANGUAGES.has(key)) continue;
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
