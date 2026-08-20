// Temporary category records used until Firestore is connected.
const sampleCategories = [
  {
    id: "category-footwear",
    name: "Footwear",
    description: "Shoes, sandals and other footwear.",
    status: "active",
  },
  {
    id: "category-audio",
    name: "Audio",
    description: "Earbuds, headphones and speakers.",
    status: "active",
  },
  {
    id: "category-wearables",
    name: "Wearables",
    description: "Smart watches and fitness devices.",
    status: "active",
  },
  {
    id: "category-bags",
    name: "Bags",
    description: "Handbags, backpacks and travel bags.",
    status: "active",
  },
  {
    id: "category-appliances",
    name: "Appliances",
    description: "Small home and kitchen appliances.",
    status: "active",
  },
  {
    id: "category-uncategorized",
    name: "Uncategorized",
    description: "Products waiting for a category.",
    status: "needs-attention",
  },
];

export default sampleCategories;