// These controls show modules; the API remains authoritative for preset role grants.
export const PERMISSION_OPTIONS = [
  { id: "orders", label: "Orders & Fulfillment", description: "View and process customer orders" },
  { id: "inventory", label: "Products & Stock", description: "Manage products, variants, and stock" },
  { id: "customers", label: "Customers & Chat", description: "Access customer contacts and chat conversations" },
  { id: "couriers", label: "Couriers & Delivery", description: "Manage courier partners and shipments" },
  { id: "analytics", label: "Analytics & Reports", description: "View store performance metrics and reports" },
  { id: "reviews", label: "Product Reviews", description: "Moderate customer reviews and feedback" },
];

export const ALL_PERMISSION_IDS = PERMISSION_OPTIONS.map((permission) => permission.id);

// Keep the preview granular so customizing one module cannot widen unrelated read grants.
export const DEFAULT_ROLE_PERMISSIONS = {
  admin: ["*"],
  order_manager: ["orders:*", "customers:*", "couriers:read", "inventory:read", "messages:*"],
  inventory_manager: ["inventory:*", "orders:read", "reviews:manage"],
  support: ["orders:read", "customers:*", "messages:*"],
  viewer: ["orders:read", "inventory:read", "analytics:read"],
  custom: ["orders"],
};

// Switching to Custom retains granular access without carrying the administrator wildcard.
export function permissionsForStaffRole(role, currentPermissions) {
  if (role !== "custom") return DEFAULT_ROLE_PERMISSIONS[role] || [];
  return currentPermissions.includes("*") ? ALL_PERMISSION_IDS : currentPermissions;
}

// Chat grants share the Customers control without altering their stored permissions.
function permissionModule(permission) {
  const prefix = permission.split(":", 1)[0];
  return prefix === "messages" ? "customers" : prefix;
}

// Module IDs are only a display projection, never a replacement for saved granular grants.
export function normalizePermissionsToModuleIds(permissions, role) {
  const grants = Array.isArray(permissions) ? permissions : DEFAULT_ROLE_PERMISSIONS[role] || [];
  if (grants.includes("*")) return ALL_PERMISSION_IDS;
  return [...new Set(grants.map(permissionModule))].filter((module) => ALL_PERMISSION_IDS.includes(module));
}

// Change only the selected module; retain exact grants for every untouched module.
export function toggleStaffModule(permissions, module) {
  const grants = permissions.includes("*") ? ALL_PERMISSION_IDS : permissions;
  return grants.some((permission) => permissionModule(permission) === module)
    ? grants.filter((permission) => permissionModule(permission) !== module)
    : [...grants, module];
}

// Presets never send overrides; legacy aliases must not expand granular grants on a custom save.
export function staffPermissionPayload(role, permissions, hasChanges = true) {
  if (!hasChanges) return {};
  if (role !== "custom") return { role };
  return {
    role,
    permissions: permissions.filter((permission) =>
      !ALL_PERMISSION_IDS.includes(permission)
      || !permissions.some((grant) => grant.startsWith(`${permission}:`)),
    ),
  };
}
