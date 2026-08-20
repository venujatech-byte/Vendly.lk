import { UserPlus } from "lucide-react";
import { useEffect, useState } from "react";

import {
  addBusinessMember,
  getBusinessMembers,
  updateBusinessMember,
} from "../services/memberService";
import "./StaffSettings.css";


const staffRoles = [
  ["admin", "Admin"],
  ["order_manager", "Order manager"],
  ["inventory_manager", "Inventory manager"],
  ["support", "Support"],
  ["viewer", "Viewer"],
];

const roleDescriptions = {
  admin: "Full business access, including staff management.",
  order_manager: "Manage orders and customers; view stock and couriers.",
  inventory_manager: "Manage products, stock and reviews; view orders.",
  support: "View orders and manage customer support details.",
  viewer: "Read-only access to orders, inventory and analytics.",
};


function StaffSettings({ businessId, currentRole }) {
  const [members, setMembers] = useState([]);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("order_manager");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const canManageStaff = ["owner", "admin"].includes(currentRole);

  useEffect(() => {
    let requestIsCurrent = true;

    if (!businessId || !canManageStaff) return undefined;

    getBusinessMembers(businessId)
      .then((records) => {
        if (requestIsCurrent) setMembers(records);
      })
      .catch((error) => {
        if (requestIsCurrent) setErrorMessage(error.message);
      });

    return () => {
      requestIsCurrent = false;
    };
  }, [businessId, canManageStaff]);

  async function addMember(event) {
    event.preventDefault();
    setIsSaving(true);
    setErrorMessage("");

    try {
      const member = await addBusinessMember(businessId, { email, role });
      setMembers((current) => [...current, member]);
      setEmail("");
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function changeMember(member, changes) {
    setErrorMessage("");

    try {
      const updated = await updateBusinessMember(businessId, member.id, changes);
      setMembers((current) =>
        current.map((item) => (item.id === member.id ? updated : item)),
      );
    } catch (error) {
      setErrorMessage(error.message);
    }
  }

  return (
    <section className="staff-settings">
      <header>
        <div><h2>Staff & permissions</h2><p>Control who can access this business.</p></div>
      </header>

      {!canManageStaff ? (
        <p className="staff-settings__notice">Only the owner or an admin can manage staff accounts.</p>
      ) : (
        <>
          <form onSubmit={addMember}>
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Existing Vendly account email"
              required
            />
            <select value={role} onChange={(event) => setRole(event.target.value)}>
              {staffRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <button type="submit" disabled={isSaving}>
              <UserPlus size={16} /> {isSaving ? "Adding..." : "Add staff"}
            </button>
          </form>
          <p className="staff-settings__role-description">{roleDescriptions[role]}</p>

          {errorMessage && <p className="staff-settings__notice staff-settings__notice--error" role="alert">{errorMessage}</p>}

          <div className="staff-settings__members">
            {members.map((member) => (
              <article key={member.id}>
                <div><strong>{member.displayName}</strong><span>{member.email}</span></div>
                {member.role === "owner" ? (
                  <strong className="staff-settings__owner">Owner</strong>
                ) : (
                  <>
                    <select
                      value={member.role}
                      onChange={(event) => changeMember(member, { role: event.target.value })}
                    >
                      {staffRoles.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                    </select>
                    <small className="staff-settings__member-permissions">
                      {roleDescriptions[member.role]}
                    </small>
                    <button
                      type="button"
                      onClick={() => changeMember(member, {
                        status: member.status === "active" ? "inactive" : "active",
                      })}
                    >
                      {member.status === "active" ? "Disable" : "Enable"}
                    </button>
                  </>
                )}
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

export default StaffSettings;
