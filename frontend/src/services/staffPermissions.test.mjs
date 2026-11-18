import assert from "node:assert/strict";
import { test } from "node:test";

import {
  ALL_PERMISSION_IDS,
  DEFAULT_ROLE_PERMISSIONS,
  normalizePermissionsToModuleIds,
  permissionsForStaffRole,
  staffPermissionPayload,
  toggleStaffModule,
} from "./staffPermissions.js";

// The form cannot submit module overrides while retaining a preset role label.
test("preset submissions defer to server grants", () => {
  for (const role of Object.keys(DEFAULT_ROLE_PERMISSIONS).filter((role) => role !== "custom")) {
    assert.deepEqual(staffPermissionPayload(role, ALL_PERMISSION_IDS), { role });
  }
  assert.deepEqual(DEFAULT_ROLE_PERMISSIONS.viewer, ["orders:read", "inventory:read", "analytics:read"]);
});

// Displaying read grants must not make them writable when another module changes.
test("module overrides preserve untouched granular grants", () => {
  const original = DEFAULT_ROLE_PERMISSIONS.viewer;
  const customized = toggleStaffModule(original, "couriers");
  assert.deepEqual(staffPermissionPayload("custom", customized).permissions, [...original, "couriers"]);
  assert.deepEqual(toggleStaffModule(original, "orders"), ["inventory:read", "analytics:read"]);
  assert.deepEqual(DEFAULT_ROLE_PERMISSIONS.viewer, ["orders:read", "inventory:read", "analytics:read"]);
});


// Selecting Custom alone cannot turn a viewer's read grants into full module permissions.
test("role changes retain granular access or load the chosen preset", () => {
  const viewer = DEFAULT_ROLE_PERMISSIONS.viewer;
  assert.deepEqual(permissionsForStaffRole("custom", viewer), viewer);
  assert.deepEqual(permissionsForStaffRole("viewer", ["*"]), viewer);
  assert.deepEqual(permissionsForStaffRole("custom", ["*"]), ALL_PERMISSION_IDS);
});

// Unchanged legacy records keep their exact grants until an owner intentionally edits them.
test("unchanged save submits no membership changes", () => {
  for (const role of ["viewer", "custom"]) {
    assert.deepEqual(staffPermissionPayload(role, ["orders", "orders:read"], false), {});
    assert.deepEqual(staffPermissionPayload(role, ["*"], false), {});
  }
});

// Ignore legacy widening aliases on a custom save, matching backend authorization semantics.
test("legacy aliases cannot expand an unrelated module edit", () => {
  const permissions = toggleStaffModule(["orders", "orders:read", "inventory:read"], "couriers");
  assert.deepEqual(staffPermissionPayload("custom", permissions).permissions, ["orders:read", "inventory:read", "couriers"]);
  assert.deepEqual(staffPermissionPayload("custom", ["orders"]).permissions, ["orders"]);
});

// Removing Customers also removes its chat grants; unrelated staff grants stay unchanged.
test("module removal drops all related grants", () => {
  assert.deepEqual(toggleStaffModule(["customers:*", "messages:read", "staff:manage"], "customers"), ["staff:manage"]);
  assert.deepEqual(toggleStaffModule(["*"], "orders"), ALL_PERMISSION_IDS.filter((id) => id !== "orders"));
});

// Empty and cleared selections must stay empty instead of falling back to a role default.
test("checkbox projection does not change saved permissions", () => {
  assert.deepEqual(normalizePermissionsToModuleIds(["orders", "orders:read", "messages:read"], "custom"), ["orders", "customers"]);
  assert.deepEqual(normalizePermissionsToModuleIds([], "viewer"), []);
  assert.deepEqual(normalizePermissionsToModuleIds(["staff:manage"], "viewer"), []);
  assert.deepEqual(staffPermissionPayload("custom", []).permissions, []);
  assert.deepEqual(normalizePermissionsToModuleIds(["*"], "admin"), ALL_PERMISSION_IDS);
});
