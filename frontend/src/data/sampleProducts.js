// Temporary product records used to build the inventory UI before Firestore.
const sampleProducts = [
  // Simple product without size variants.
  {
    id: "product-001",
    name: "Haylou Smart Watch LS02",
    productType: "Smart Watch",
    sku: "HW-LS02-BLK",
    barcode: "6971664930824",
    category: "Wearables",

    costPrice: 3300,
    sellingPrice: 4900,
    weightKg: 0.05,

    stock: 36,
    lowStockThreshold: 5,
    approvedReviews: 128,

    description:
      "Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.Haylou LS02 is a sporty smart watch with 12 sport modes, heart rate monitoring, sleep tracking, and 30-day battery life. Water resistant up to 5ATM.",

    images: [
      "/products/haylou-ls02-front.png",
      "/products/haylou-ls02-side.png",
      "/products/haylou-ls02-box.png",
      "/products/haylou-ls02-back.png",
      "/products/haylou-ls02-strap.png",
    ],
  },

  // Another simple product record.
  {
    id: "product-002",
    name: "Redmi Buds 4 Lite",
    productType: "Earbuds",
    sku: "RB-4L-BLK",
    barcode: "6941812712569",
    category: "Audio",

    costPrice: 2700,
    sellingPrice: 3950,
    weightKg: 0.04,

    stock: 18,
    lowStockThreshold: 20,
    approvedReviews: 84,

    description:
      "Lightweight wireless earbuds supplied with a compact charging case.",

    images: [
      "/products/redmi-buds-front.png",
      "/products/redmi-buds-case.png",
    ],
  },

  // Product with no remaining stock.
  {
    id: "product-003",
    name: "Zara Mini Tote Bag - Beige",
    productType: "Handbag",
    sku: "ZARA-MINI-BGE",
    barcode: "2000003145123",
    category: "Bags",

    costPrice: 2400,
    sellingPrice: 3700,
    weightKg: 0.35,

    stock: 0,
    lowStockThreshold: 5,
    approvedReviews: 45,

    description:
      "A compact beige tote bag suitable for everyday use.",

    images: [
      "/products/zara-mini-bag-front.png",
      "/products/zara-mini-bag-side.png",
    ],
  },

  // Simple footwear product with one SKU.
  {
    id: "product-004",
    name: "Running Shoes - Black",
    productType: "Men's Shoes",
    sku: "RS-BLK-42",
    barcode: "8901234567890",
    category: "Footwear",

    costPrice: 6000,
    sellingPrice: 8250,
    weightKg: 0.8,

    stock: 42,
    lowStockThreshold: 10,
    approvedReviews: 62,

    description:
      "Black running shoes designed for everyday exercise and casual wear.",

    images: [
      "/products/running-shoes-left.png",
      "/products/running-shoes-right.png",
    ],
  },

  // Simple appliance product with one SKU.
  {
    id: "product-005",
    name: "Portable Blender 380ml",
    productType: "Home Appliance",
    sku: "PB-380-PNK",
    barcode: "8906123456781",
    category: "Appliances",

    costPrice: 3900,
    sellingPrice: 5680,
    weightKg: 0.6,

    stock: 27,
    lowStockThreshold: 10,
    approvedReviews: 31,

    description:
      "A compact 380ml portable blender suitable for preparing drinks while travelling.",

    images: [
      "/products/portable-blender-front.png",
      "/products/portable-blender-open.png",
    ],
  },

  // Pink shoe product; each size has its own SKU, barcode, and stock.
  {
    id: "product-006-pink",
    name: "Daisy Running Shoes - Pink",
    colour: "Pink",
    colourHex: "#ec7f9f",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "pink-36", size: "36", sku: "DFS-PNK-36", barcode: "890123456001", stock: 5 },
      { id: "pink-37", size: "37", sku: "DFS-PNK-37", barcode: "890123456002", stock: 1 },
      { id: "pink-38", size: "38", sku: "DFS-PNK-38", barcode: "890123456003", stock: 2 },
      { id: "pink-39", size: "39", sku: "DFS-PNK-39", barcode: "890123456004", stock: 3 },
      { id: "pink-40", size: "40", sku: "DFS-PNK-40", barcode: "890123456005", stock: 4 },
    ],
    approvedReviews: 42,
    description:
      "Lightweight pink running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/pink.png"],
  },

  // Purple is stored as a separate product with size variants.
  {
    id: "product-007-purple",
    name: "Daisy Running Shoes - Purple",
    colour: "Purple",
    colourHex: "#8a62c2",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 6,
    hasSizes: true,
    sizes: [
      { id: "purple-36", size: "36", sku: "DFS-PUR-36", barcode: "890123456101", stock: 2 },
      { id: "purple-37", size: "37", sku: "DFS-PUR-37", barcode: "890123456102", stock: 1 },
      { id: "purple-38", size: "38", sku: "DFS-PUR-38", barcode: "890123456103", stock: 1 },
      { id: "purple-39", size: "39", sku: "DFS-PUR-39", barcode: "890123456104", stock: 1 },
      { id: "purple-40", size: "40", sku: "DFS-PUR-40", barcode: "890123456105", stock: 1 },
    ],
    approvedReviews: 18,
    description:
      "Lightweight purple running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/purple.png"],
  },

  // Burgundy is stored as a separate product with size variants.
  {
    id: "product-008-burgundy",
    name: "Daisy Running Shoes - Burgundy",
    colour: "Burgundy",
    colourHex: "#8b1e3f",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "burgundy-36", size: "36", sku: "DFS-BUR-36", barcode: "890123456201", stock: 1 },
      { id: "burgundy-37", size: "37", sku: "DFS-BUR-37", barcode: "890123456202", stock: 1 },
      { id: "burgundy-38", size: "38", sku: "DFS-BUR-38", barcode: "890123456203", stock: 2 },
      { id: "burgundy-39", size: "39", sku: "DFS-BUR-39", barcode: "890123456204", stock: 2 },
      { id: "burgundy-40", size: "40", sku: "DFS-BUR-40", barcode: "890123456205", stock: 1 },
    ],
    approvedReviews: 23,
    description:
      "Lightweight burgundy running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/burgundy.png"],
  },

  // Black is stored as a separate product with size variants.
  {
    id: "product-009-black",
    name: "Daisy Running Shoes - Black",
    colour: "Black",
    colourHex: "#161616",
    brand: "Daisy Fashion",
    productType: "Women's Shoes",
    category: "Footwear",
    costPrice: 1200,
    sellingPrice: 1899,
    weightKg: 0.45,
    lowStockThreshold: 5,
    hasSizes: true,
    sizes: [
      { id: "black-36", size: "36", sku: "DFS-BLK-36", barcode: "890123456301", stock: 0 },
      { id: "black-37", size: "37", sku: "DFS-BLK-37", barcode: "890123456302", stock: 0 },
      { id: "black-38", size: "38", sku: "DFS-BLK-38", barcode: "890123456303", stock: 0 },
      { id: "black-39", size: "39", sku: "DFS-BLK-39", barcode: "890123456304", stock: 0 },
      { id: "black-40", size: "40", sku: "DFS-BLK-40", barcode: "890123456305", stock: 0 },
    ],
    approvedReviews: 11,
    description:
      "Lightweight black running shoes designed for comfortable daily wear.",
    images: ["/products/daisy-shoes/black.png"],
  },
];

// Export the records so inventory components can display and calculate them.
export default sampleProducts;
