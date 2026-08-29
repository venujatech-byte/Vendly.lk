// The 25 administrative districts of Sri Lanka, in the same order and spelling
// as DISTRICT_NAMES in backend/app/services/courier_service.py. The backend
// resolves Sinhala, Tamil and misspelled names to these; the dashboard and the
// storefront only ever send this exact spelling.
export const SRI_LANKA_DISTRICTS = [
  "Ampara",
  "Anuradhapura",
  "Badulla",
  "Batticaloa",
  "Colombo",
  "Galle",
  "Gampaha",
  "Hambantota",
  "Jaffna",
  "Kalutara",
  "Kandy",
  "Kegalle",
  "Kilinochchi",
  "Kurunegala",
  "Mannar",
  "Matale",
  "Matara",
  "Monaragala",
  "Mullaitivu",
  "Nuwara Eliya",
  "Polonnaruwa",
  "Puttalam",
  "Ratnapura",
  "Trincomalee",
  "Vavuniya",
];

// Matches slugify() in backend/app/services/text.py, which is how the stored
// districtFirstKgPricesMinor map is keyed.
export function districtSlug(district) {
  return String(district)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export default SRI_LANKA_DISTRICTS;
