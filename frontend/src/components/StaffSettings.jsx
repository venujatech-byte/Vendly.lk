import {
  AlertCircle,
  AlertTriangle,
  Check,
  CheckSquare,
  Copy,
  Mail,
  MoreVertical,
  Plus,
  Shield,
  ShieldCheck,
  Sliders,
  Square,
  Trash2,
  UserCheck,
  UserMinus,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  addBusinessMember,
  cancelBusinessInvitation,
  getBusinessMembers,
  removeBusinessMember,
  updateBusinessMember,
} from "../services/memberService";
import CustomSelect from "./CustomSelect";
import "./StaffSettings.css";

export const PERMISSION_OPTIONS = [
  { id: "orders", label: "Orders & Fulfillment", description: "View and process customer orders" },
  { id: "inventory", label: "Products & Stock", description: "Manage products, variants, and stock" },
  { id: "customers", label: "Customers & Chat", description: "Access customer contacts and chat conversations" },
  { id: "couriers", label: "Couriers & Delivery", description: "Manage courier partners and shipments" },
  { id: "analytics", label: "Analytics & Reports", description: "View store performance metrics and reports" },
  { id: "reviews", label: "Product Reviews", description: "Moderate customer reviews and feedback" },
];

const ALL_PERMISSION_IDS = PERMISSION_OPTIONS.map((p) => p.id);

const DEFAULT_ROLE_PERMISSIONS = {
  admin: ALL_PERMISSION_IDS,
  order_manager: ["orders", "customers", "couriers"],
  inventory_manager: ["inventory", "reviews", "orders"],
  support: ["orders", "customers"],
  viewer: ["orders", "inventory", "analytics"],
  custom: ["orders"],
};

export function normalizePermissionsToModuleIds(permissions, role) {
  if (!Array.isArray(permissions)) {
    return DEFAULT_ROLE_PERMISSIONS[role] || [];
  }
  if (permissions.includes("*")) {
    return ALL_PERMISSION_IDS;
  }
  const result = new Set();
  for (const perm of permissions) {
    const raw = String(perm).toLowerCase().trim();
    if (ALL_PERMISSION_IDS.includes(raw)) {
      result.add(raw);
    }
    const prefix = raw.split(":")[0];
    if (ALL_PERMISSION_IDS.includes(prefix)) {
      result.add(prefix);
    }
    if (prefix === "messages") {
      result.add("customers");
    }
  }
  if (result.size === 0 && DEFAULT_ROLE_PERMISSIONS[role]) {
    return DEFAULT_ROLE_PERMISSIONS[role];
  }
  return Array.from(result);
}

const staffRoles = [
  ["admin", "Admin (Full Access)"],
  ["order_manager", "Order Manager"],
  ["inventory_manager", "Inventory Manager"],
  ["support", "Customer Support"],
  ["viewer", "Viewer (Read Only)"],
  ["custom", "Custom Permissions"],
];

const roleDescriptions = {
  admin: "Unrestricted access across all store operations and settings.",
  order_manager: "Manages customer orders, dispatch, and customer relations.",
  inventory_manager: "Controls products, categories, stock levels, and customer reviews.",
  support: "Views order history and manages customer support inquiries.",
  viewer: "Read-only access to sales, catalog, and analytics.",
  custom: "Individually selected modular permissions configured by store owner.",
};

function StaffSettings({ businessId, currentRole }) {
  const [members, setMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [email, setEmail] = useState("");
  const [selectedRole, setSelectedRole] = useState("order_manager");
  const [selectedPermissions, setSelectedPermissions] = useState(
    DEFAULT_ROLE_PERMISSIONS.order_manager,
  );
  const [showCustomPermissions, setShowCustomPermissions] = useState(true);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [copiedToken, setCopiedToken] = useState(null);
  const [lastCreatedInviteToken, setLastCreatedInviteToken] = useState(null);

  // Modal state for editing an existing member's permissions
  const [editingMember, setEditingMember] = useState(null);
  const [editPermissions, setEditPermissions] = useState([]);
  const [editRole, setEditRole] = useState("order_manager");
  const [isUpdatingMember, setIsUpdatingMember] = useState(false);

  // Deletion confirmation state
  const [memberToRemove, setMemberToRemove] = useState(null);
  const [isRemovingMember, setIsRemovingMember] = useState(false);

  const canManageStaff = ["owner", "admin"].includes(currentRole);

  async function loadData() {
    if (!businessId || !canManageStaff) return;
    try {
      const data = await getBusinessMembers(businessId);
      setMembers(data.members || []);
      const formattedInvites = (data.invitations || []).map((inv) => ({
        ...inv,
        token: inv.token || inv.id,
      }));
      setInvitations(formattedInvites);
    } catch (error) {
      setErrorMessage(error.message || "Failed to load staff list.");
    }
  }

  useEffect(() => {
    loadData();
  }, [businessId, canManageStaff]);

  function handleRoleChange(newRole) {
    setSelectedRole(newRole);
    if (DEFAULT_ROLE_PERMISSIONS[newRole]) {
      setSelectedPermissions(DEFAULT_ROLE_PERMISSIONS[newRole]);
    }
    if (newRole === "custom") {
      setShowCustomPermissions(true);
    }
  }

  function togglePermission(permId) {
    setSelectedPermissions((current) => {
      const updated = current.includes(permId)
        ? current.filter((id) => id !== permId)
        : [...current, permId];
      if (selectedRole !== "custom") {
        setSelectedRole("custom");
      }
      return updated;
    });
  }

  function toggleEditPermission(permId) {
    setEditPermissions((current) => {
      const updated = current.includes(permId)
        ? current.filter((id) => id !== permId)
        : [...current, permId];
      return updated;
    });
  }

  async function handleAddStaff(event) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage("");
    setSuccessMessage("");

    const targetEmail = email.trim().toLowerCase();
    if (!targetEmail) {
      setErrorMessage("Please enter an email address.");
      setIsSaving(false);
      return;
    }

    try {
      const payload = {
        email: targetEmail,
        role: selectedRole,
        permissions: selectedPermissions,
      };

      const result = await addBusinessMember(businessId, payload);
      setEmail("");
      setSelectedRole("order_manager");
      setSelectedPermissions(DEFAULT_ROLE_PERMISSIONS.order_manager);
      setShowCustomPermissions(false);

      if (result.invitation || result.inviteToken) {
        const token =
          result.inviteToken ||
          result.invitation?.token ||
          result.invitation?.id ||
          result.invitationId;
        setLastCreatedInviteToken(token);
        const inviteUrl = `${window.location.origin}/join?token=${token}`;
        setSuccessMessage(
          `Invitation created for ${targetEmail}! Share this link: ${inviteUrl}`,
        );
      } else {
        setLastCreatedInviteToken(null);
        setSuccessMessage(`Staff member added successfully!`);
      }

      await loadData();
    } catch (error) {
      if (
        error.code === "preregistered_user_cannot_be_staff" ||
        error.message?.includes("preregistered") ||
        error.status === 409
      ) {
        setErrorMessage(
          "This email is already registered as a Vendly user. As per security rules, pre-registered accounts cannot be added as staff. Only new emails can be invited.",
        );
      } else {
        setErrorMessage(error.message || "Failed to invite staff member.");
      }
    } finally {
      setIsSaving(false);
    }
  }

  async function handleCopyInviteLink(rawToken) {
    const effectiveToken = rawToken || "";
    if (!effectiveToken || effectiveToken === "undefined") {
      setErrorMessage("Could not determine valid invitation link. Please reload the page.");
      return;
    }
    const inviteUrl = `${window.location.origin}/join?token=${effectiveToken}`;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopiedToken(effectiveToken);
      setTimeout(() => setCopiedToken(null), 3000);
    } catch {
      prompt("Copy invite link:", inviteUrl);
    }
  }

  async function handleCancelInvitation(invitationId) {
    setErrorMessage("");
    try {
      await cancelBusinessInvitation(businessId, invitationId);
      setInvitations((current) => current.filter((inv) => inv.id !== invitationId));
      setSuccessMessage("Invitation revoked.");
    } catch (error) {
      setErrorMessage(error.message || "Failed to cancel invitation.");
    }
  }

  function startEditMember(member) {
    setEditingMember(member);
    const existingPerms = normalizePermissionsToModuleIds(member.permissions, member.role);
    setEditPermissions(existingPerms);
    setEditRole(member.role || "custom");
  }

  async function saveMemberPermissions() {
    if (!editingMember) return;
    setIsUpdatingMember(true);
    setErrorMessage("");
    try {
      const updated = await updateBusinessMember(businessId, editingMember.id, {
        role: editRole,
        permissions: editPermissions,
      });
      setMembers((current) =>
        current.map((m) => (m.id === editingMember.id ? { ...m, ...updated } : m)),
      );
      setEditingMember(null);
      setSuccessMessage("Staff permissions updated successfully.");
      await loadData();
    } catch (error) {
      setErrorMessage(error.message || "Failed to update permissions.");
    } finally {
      setIsUpdatingMember(false);
    }
  }

  async function toggleMemberStatus(member) {
    setErrorMessage("");
    const newStatus = member.status === "active" ? "inactive" : "active";
    try {
      const updated = await updateBusinessMember(businessId, member.id, {
        status: newStatus,
      });
      setMembers((current) =>
        current.map((m) => (m.id === member.id ? { ...m, ...updated } : m)),
      );
    } catch (error) {
      setErrorMessage(error.message || "Failed to update member status.");
    }
  }

  async function confirmRemoveMember() {
    if (!memberToRemove) return;
    setIsRemovingMember(true);
    setErrorMessage("");
    try {
      await removeBusinessMember(businessId, memberToRemove.id);
      setMembers((current) => current.filter((m) => m.id !== memberToRemove.id));
      setMemberToRemove(null);
      setSuccessMessage("Staff member removed from business.");
    } catch (error) {
      setErrorMessage(error.message || "Failed to remove staff member.");
    } finally {
      setIsRemovingMember(false);
    }
  }

  return (
    <section className="staff-settings">
      <header className="staff-settings__header">
        <div>
          <h2>Staff Management & Permissions</h2>
          <p>
            Invite team members and configure granular, customizable access permissions for each
            staff account.
          </p>
        </div>
      </header>

      {!canManageStaff ? (
        <div className="staff-settings__notice">
          <AlertCircle size={18} />
          <span>Only the store owner or an administrator can manage staff accounts and permissions.</span>
        </div>
      ) : (
        <>
          {errorMessage && (
            <div className="staff-settings__alert staff-settings__alert--error" role="alert">
              <AlertCircle size={18} />
              <span>{errorMessage}</span>
            </div>
          )}

          {successMessage && (
            <div className="staff-settings__alert staff-settings__alert--success" role="status">
              <Check size={18} />
              <span style={{ flex: 1 }}>{successMessage}</span>
              {lastCreatedInviteToken && (
                <button
                  type="button"
                  className="staff-settings__btn-secondary"
                  onClick={() => handleCopyInviteLink(lastCreatedInviteToken)}
                  style={{ marginLeft: "auto" }}
                >
                  {copiedToken === lastCreatedInviteToken ? (
                    <>
                      <Check size={14} /> Copied!
                    </>
                  ) : (
                    <>
                      <Copy size={14} /> Copy Link
                    </>
                  )}
                </button>
              )}
            </div>
          )}

          {/* Add Staff Section */}
          <div className="staff-settings__card staff-settings__card--invite">
            <div className="staff-settings__card-header">
              <UserPlus size={20} className="staff-settings__header-icon" />
              <div>
                <h3>Invite New Staff Member</h3>
                <p>
                  Send an onboarding invite to an unregistered email. Customize their permissions below.
                </p>
              </div>
            </div>

            <form className="staff-settings__invite-form" onSubmit={handleAddStaff}>
              <div className="staff-settings__invite-fields">
                <div className="staff-settings__input-group">
                  <label htmlFor="staff-email">Staff Email Address</label>
                  <input
                    id="staff-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="colleague@example.com"
                    required
                  />
                  <small>Pre-registered Vendly users cannot be added; only new emails can be invited.</small>
                </div>

                <div className="staff-settings__input-group">
                  <label htmlFor="staff-role">Role Template</label>
                  <CustomSelect
                    id="staff-role"
                    value={selectedRole}
                    onChange={(e) => handleRoleChange(e.target.value)}
                  >
                    {staffRoles.map(([val, label]) => (
                      <option key={val} value={val}>
                        {label}
                      </option>
                    ))}
                  </CustomSelect>
                  <small>{roleDescriptions[selectedRole]}</small>
                </div>
              </div>

              {/* Modular Permissions Customization Panel */}
              <div className="staff-settings__custom-section">
                <div className="staff-settings__custom-header">
                  <div className="staff-settings__custom-title-row">
                    <strong>Modular Access Controls</strong>
                    <span className="staff-settings__badge">
                      {selectedPermissions.length} of {PERMISSION_OPTIONS.length} selected
                    </span>
                  </div>
                  <div className="staff-settings__quick-links">
                    <button
                      type="button"
                      className="staff-settings__text-btn"
                      onClick={() => {
                        setSelectedPermissions(ALL_PERMISSION_IDS);
                        setSelectedRole("custom");
                      }}
                    >
                      Select All
                    </button>
                    <span className="staff-settings__divider">•</span>
                    <button
                      type="button"
                      className="staff-settings__text-btn"
                      onClick={() => {
                        setSelectedPermissions([]);
                        setSelectedRole("custom");
                      }}
                    >
                      Clear
                    </button>
                  </div>
                </div>

                <div className="staff-settings__permissions-grid">
                  {PERMISSION_OPTIONS.map((perm) => {
                    const isChecked = selectedPermissions.includes(perm.id);
                    return (
                      <label
                        key={perm.id}
                        className={`staff-settings__perm-card ${
                          isChecked ? "staff-settings__perm-card--checked" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => togglePermission(perm.id)}
                        />
                        <div className="staff-settings__perm-content">
                          <strong>{perm.label}</strong>
                          <p>{perm.description}</p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div className="staff-settings__form-actions">
                <button type="submit" className="staff-settings__btn-primary" disabled={isSaving}>
                  <UserPlus size={16} />
                  {isSaving ? "Creating Invite..." : "Send Staff Invite"}
                </button>
              </div>
            </form>
          </div>

          {/* Pending Invitations Section */}
          {invitations.length > 0 && (
            <div className="staff-settings__card">
              <div className="staff-settings__card-header">
                <Mail size={20} className="staff-settings__header-icon" />
                <div>
                  <h3>Pending Staff Invitations ({invitations.length})</h3>
                  <p>
                    Invited staff will automatically join this store as soon as they register or sign
                    in.
                  </p>
                </div>
              </div>

              <div className="staff-settings__invites-list">
                {invitations.map((inv) => {
                  const token = inv.token || inv.id;
                  return (
                    <div key={inv.id} className="staff-settings__invite-item">
                      <div className="staff-settings__invite-info">
                        <strong>{inv.email}</strong>
                        <div className="staff-settings__tags">
                          <span className="staff-settings__tag staff-settings__tag--role">
                            {inv.role}
                          </span>
                          <span className="staff-settings__tag staff-settings__tag--perms">
                            {Array.isArray(inv.permissions) ? inv.permissions.join(", ") : "custom"}
                          </span>
                        </div>
                      </div>
                      <div className="staff-settings__invite-actions">
                        <button
                          type="button"
                          className="staff-settings__btn-secondary"
                          onClick={() => handleCopyInviteLink(token)}
                          title="Copy direct invite link"
                        >
                          {copiedToken === token ? (
                            <>
                              <Check size={14} /> Copied!
                            </>
                          ) : (
                            <>
                              <Copy size={14} /> Copy Link
                            </>
                          )}
                        </button>
                        <button
                          type="button"
                          className="staff-settings__btn-danger-outline"
                          onClick={() => handleCancelInvitation(inv.id)}
                          title="Revoke invitation"
                        >
                          <X size={14} /> Revoke
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Active Members Section */}
          <div className="staff-settings__card">
            <div className="staff-settings__card-header">
              <Users size={20} className="staff-settings__header-icon" />
              <div>
                <h3>Active Store Team ({members.length})</h3>
                <p>Team members with authorized access to your store dashboard.</p>
              </div>
            </div>

            <div className="staff-settings__members-list">
              {members.map((member) => {
                const isOwner = member.role === "owner";

                return (
                  <article
                    key={member.id}
                    className={`staff-settings__member-row ${
                      member.status === "inactive" ? "staff-settings__member-row--disabled" : ""
                    }`}
                  >
                    <div className="staff-settings__member-primary">
                      <div className="staff-settings__avatar">
                        {member.displayName ? member.displayName[0].toUpperCase() : "U"}
                      </div>
                      <div className="staff-settings__member-details">
                        <div className="staff-settings__member-name-row">
                          <strong>{member.displayName || "Store Staff"}</strong>
                          {isOwner && (
                            <span className="staff-settings__tag staff-settings__tag--owner">
                              <ShieldCheck size={13} /> Owner
                            </span>
                          )}
                          {member.status === "inactive" && (
                            <span className="staff-settings__tag staff-settings__tag--disabled">
                              Disabled
                            </span>
                          )}
                        </div>
                        <span className="staff-settings__member-email">{member.email}</span>
                        {!isOwner && (
                          <div className="staff-settings__member-perms-summary">
                            <span className="staff-settings__role-pill">{member.role}</span>
                            <span className="staff-settings__perms-count">
                              Permissions:{" "}
                              {member.role === "admin" || (Array.isArray(member.permissions) && member.permissions.includes("*"))
                                ? "All (Admin)"
                                : normalizePermissionsToModuleIds(member.permissions, member.role).length > 0
                                ? normalizePermissionsToModuleIds(member.permissions, member.role)
                                    .map((p) => PERMISSION_OPTIONS.find((o) => o.id === p)?.label.split(" ")[0] || p)
                                    .join(", ")
                                : "None"}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {!isOwner && (
                      <div className="staff-settings__member-actions">
                        <button
                          type="button"
                          className="staff-settings__btn-secondary"
                          onClick={() => startEditMember(member)}
                          title="Customize permissions"
                        >
                          <Sliders size={14} />
                          <span>Permissions</span>
                        </button>

                        <button
                          type="button"
                          className="staff-settings__btn-secondary"
                          onClick={() => toggleMemberStatus(member)}
                        >
                          {member.status === "active" ? "Disable" : "Enable"}
                        </button>

                        <button
                          type="button"
                          className="staff-settings__btn-danger-outline"
                          onClick={() => setMemberToRemove(member)}
                          title="Remove staff member"
                        >
                          <Trash2 size={14} />
                          <span>Remove</span>
                        </button>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </div>
        </>
      )}

      {/* Edit Member Permissions Modal */}
      {editingMember && (
        <div className="staff-settings__modal-backdrop" onClick={() => setEditingMember(null)}>
          <div
            className="staff-settings__modal-content"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="staff-settings__modal-header">
              <div>
                <h3>Customize Access: {editingMember.displayName || editingMember.email}</h3>
                <p>Select role preset or toggle modular permissions specifically for this staff member.</p>
              </div>
              <button
                type="button"
                className="staff-settings__modal-close"
                onClick={() => setEditingMember(null)}
              >
                <X size={18} />
              </button>
            </div>

            <div className="staff-settings__modal-body">
              <div className="staff-settings__input-group">
                <label>Role Preset</label>
                <CustomSelect
                  value={editRole}
                  onChange={(e) => {
                    const newR = e.target.value;
                    setEditRole(newR);
                    if (DEFAULT_ROLE_PERMISSIONS[newR]) {
                      setEditPermissions(DEFAULT_ROLE_PERMISSIONS[newR]);
                    }
                  }}
                >
                  {staffRoles.map(([val, label]) => (
                    <option key={val} value={val}>
                      {label}
                    </option>
                  ))}
                </CustomSelect>
              </div>

              <div className="staff-settings__modal-perms">
                <div className="staff-settings__custom-header">
                  <div className="staff-settings__custom-title-row">
                    <label>Modular Permissions</label>
                    <span className="staff-settings__badge">
                      {editPermissions.length} of {PERMISSION_OPTIONS.length} active
                    </span>
                  </div>
                  <div className="staff-settings__quick-links">
                    <button
                      type="button"
                      className="staff-settings__text-btn"
                      onClick={() => setEditPermissions(ALL_PERMISSION_IDS)}
                    >
                      Select All
                    </button>
                    <span className="staff-settings__divider">•</span>
                    <button
                      type="button"
                      className="staff-settings__text-btn"
                      onClick={() => setEditPermissions([])}
                    >
                      Clear
                    </button>
                  </div>
                </div>
                <div className="staff-settings__permissions-grid">
                  {PERMISSION_OPTIONS.map((perm) => {
                    const isChecked = editPermissions.includes(perm.id);
                    return (
                      <label
                        key={perm.id}
                        className={`staff-settings__perm-card ${
                          isChecked ? "staff-settings__perm-card--checked" : ""
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => toggleEditPermission(perm.id)}
                        />
                        <div className="staff-settings__perm-content">
                          <strong>{perm.label}</strong>
                          <p>{perm.description}</p>
                        </div>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>

            <div className="staff-settings__modal-footer">
              <button
                type="button"
                className="staff-settings__btn-secondary"
                onClick={() => setEditingMember(null)}
                disabled={isUpdatingMember}
              >
                Cancel
              </button>
              <button
                type="button"
                className="staff-settings__btn-primary"
                onClick={saveMemberPermissions}
                disabled={isUpdatingMember}
              >
                {isUpdatingMember ? "Saving Changes..." : "Save Permissions"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Remove Member Confirmation Modal */}
      {memberToRemove && (
        <div className="staff-settings__modal-backdrop" onClick={() => setMemberToRemove(null)}>
          <div
            className="staff-settings__modal-content staff-settings__modal-content--sm"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            <div className="staff-settings__modal-header">
              <div className="staff-settings__danger-title">
                <AlertTriangle size={20} className="staff-settings__danger-icon" />
                <h3>Remove Staff Member</h3>
              </div>
            </div>

            <div className="staff-settings__modal-body">
              <p>
                Are you sure you want to remove{" "}
                <strong>{memberToRemove.displayName || memberToRemove.email}</strong> from this
                store?
              </p>
              <p className="staff-settings__modal-hint">
                They will immediately lose access to this business and its dashboards.
              </p>
            </div>

            <div className="staff-settings__modal-footer">
              <button
                type="button"
                className="staff-settings__btn-secondary"
                onClick={() => setMemberToRemove(null)}
                disabled={isRemovingMember}
              >
                Cancel
              </button>
              <button
                type="button"
                className="staff-settings__btn-danger"
                onClick={confirmRemoveMember}
                disabled={isRemovingMember}
              >
                {isRemovingMember ? "Removing..." : "Confirm Removal"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

export default StaffSettings;
