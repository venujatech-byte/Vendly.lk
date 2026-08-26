// Fixed chat-panel labels in the three storefront languages.
//
// These are a static table on purpose. The bot's replies are translated by the
// model because they are generated text; this chrome is a closed set of short
// strings that never changes, so a table is cheaper, instant, and correct even
// when the AI provider is down.
//
// Keep the keys in sync with STOREFRONT_TEXT.en — that is the fallback for any
// language missing an entry.
const STOREFRONT_TEXT = {
  en: {
    showProducts: "Show products",
    wantToOrder: "I want to order",
    reviews: "Reviews",
    typeMessage: "Type a message…",
    orderThisProduct: "Order this product",
    compareSimilar: "Compare similar products",
    youMayAlsoLike: "You may also like",
    verifiedReviews: "Verified customer reviews",
    listening: "Listening…",
    speakYourMessage: "Speak your message",
    releaseToFinish: "Release to finish",
    productsAndQuantity: "Products & quantity",
  },
  si: {
    showProducts: "නිෂ්පාදන පෙන්වන්න",
    wantToOrder: "මට ඕඩර් කරන්න ඕන",
    reviews: "සමාලෝචන",
    typeMessage: "පණිවිඩයක් ටයිප් කරන්න…",
    orderThisProduct: "මෙම නිෂ්පාදනය ඕඩර් කරන්න",
    compareSimilar: "සමාන නිෂ්පාදන සසඳන්න",
    youMayAlsoLike: "ඔබ මෙයටත් කැමති විය හැක",
    verifiedReviews: "සත්‍යාපිත පාරිභෝගික සමාලෝචන",
    listening: "අහගෙන ඉන්නවා…",
    speakYourMessage: "ඔබේ පණිවිඩය කියන්න",
    releaseToFinish: "අවසන් කිරීමට අත ඉවත් කරන්න",
    productsAndQuantity: "නිෂ්පාදන සහ ප්‍රමාණය",
  },
  ta: {
    showProducts: "பொருட்களைக் காட்டு",
    wantToOrder: "நான் ஆர்டர் செய்ய விரும்புகிறேன்",
    reviews: "மதிப்புரைகள்",
    typeMessage: "செய்தியை உள்ளிடவும்…",
    orderThisProduct: "இந்தப் பொருளை ஆர்டர் செய்",
    compareSimilar: "ஒத்த பொருட்களை ஒப்பிடு",
    youMayAlsoLike: "இதுவும் உங்களுக்குப் பிடிக்கலாம்",
    verifiedReviews: "சரிபார்க்கப்பட்ட வாடிக்கையாளர் மதிப்புரைகள்",
    listening: "கேட்டுக்கொண்டிருக்கிறேன்…",
    speakYourMessage: "உங்கள் செய்தியைச் சொல்லுங்கள்",
    releaseToFinish: "முடிக்க விடுவிக்கவும்",
    productsAndQuantity: "பொருட்கள் & அளவு",
  },
};

export function storefrontText(language) {
  return { ...STOREFRONT_TEXT.en, ...(STOREFRONT_TEXT[language] || {}) };
}

export default STOREFRONT_TEXT;
