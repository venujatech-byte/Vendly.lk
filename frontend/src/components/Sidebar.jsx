// Sidebar styles, Vendly logo, and React Router navigation component.
import "./Sidebar.css";
import vendlyLogo from "../assets/vendly-logo.png";
import { NavLink } from "react-router-dom";
import { useAuth } from "../context/authContextValue";
import { useEffect, useRef, useState } from "react";
import { logoutUser } from "../services/authService";

// Icons paired with sidebar links and footer actions.
import {
  LayoutDashboard,
  ClipboardList,
  Truck,
  Users,
  ChartNoAxesCombined,
  Box,
  ChevronsRight,
  ChevronRight,
  Store,
  ChevronsLeft,
  CreditCard,
  LogOut,
  Settings,
  Sparkles,
  UserRound,
  UsersRound,
} from "lucide-react";

// Central list of sidebar pages; map() below turns each item into a link.
const navigationItems = [
  { label: "Overview", path: "/", icon: LayoutDashboard },
  { label: "Orders", path: "/orders", icon: ClipboardList, permission: "orders:read" },
  { label: "Inventory", path: "/inventory", icon: Box, permission: "inventory:read" },
  { label: "Couriers", path: "/couriers", icon: Truck, permission: "couriers:read" },
  { label: "Customers", path: "/customers", icon: Users, permission: "customers:read" },
  { label: "Analytics", path: "/analytics", icon: ChartNoAxesCombined, permission: "analytics:read" },
];

function hasPermission(membership, requiredPermission) {
  if (!requiredPermission || membership?.role === "owner") return true;
  const permissions = membership?.permissions ?? [];
  const resource = requiredPermission.split(":", 1)[0];
  return permissions.includes("*") || permissions.includes(requiredPermission) || permissions.includes(`${resource}:*`);
}

function readableRole(role = "viewer") {
  return role.split("_").map((word) => word[0].toUpperCase() + word.slice(1)).join(" ");
}

function Sidebar({ isCollapsed, onToggleSidebar, onOpenProfile, onOpenSettings }) {
  const { sellerProfile, membership } = useAuth();
  const businessName = sellerProfile?.businessName ?? "Your Business";
  const [isProfileMenuOpen, setIsProfileMenuOpen] = useState(false);
  const profileMenuReference = useRef(null);

  useEffect(() => {
    function closeProfileMenu(event) {
      if (!profileMenuReference.current?.contains(event.target)) {
        setIsProfileMenuOpen(false);
      }
    }
    document.addEventListener("pointerdown", closeProfileMenu);
    return () => document.removeEventListener("pointerdown", closeProfileMenu);
  }, []);

  function openSettings(section) {
    setIsProfileMenuOpen(false);
    onOpenSettings(section);
  }

  return (
    <aside id="sidebar-navigation" className={`sidebar ${isCollapsed ? "sidebar--collapsed" : ""}`} >
{/* Logo and button that expands or collapses the sidebar. */}
<div className="sidebar__top">
  <div className="sidebar__logo">
    <img
      className="sidebar__logo-image"
      src={vendlyLogo}
      alt="Vendly.lk"
    />
  </div>

  <button
    className="sidebar__toggle"
    type="button"
    onClick={onToggleSidebar}
    aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
    aria-expanded={!isCollapsed}
    title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
  >
    {isCollapsed ? <ChevronsRight size={20} /> : < ChevronsLeft className="Panel_icon" size={20} />}
  </button>
</div>
      {/* Main navigation links. NavLink reports which route is active. */}
      <nav className="sidebar__navigation">
        {navigationItems.filter((item) => hasPermission(membership, item.permission)).map((item) => {
          // Store the selected icon component in a capitalized variable for JSX.
          const Icon = item.icon;

          return (
 <NavLink
  className={({ isActive }) =>
    `sidebar__link ${isActive ? "sidebar__link--active" : ""}`
  }
  end={item.path === "/"}
  key={item.path}
  to={item.path}
  title={isCollapsed ? item.label : undefined}
>
  <Icon size={22} />
  <span className="sidebar__label">{item.label}</span>
</NavLink>
          );
        })}
      </nav>

     {/* Keep the business switcher anchored at the bottom of the sidebar. */}
     <div className="sidebar__footer" ref={profileMenuReference}>
  {isProfileMenuOpen && (
    <div className="sidebar__profile-menu" role="menu">
      <button type="button" onClick={() => { setIsProfileMenuOpen(false); onOpenProfile(); }} role="menuitem"><UserRound size={16} />My Profile</button>
      <button type="button" onClick={() => openSettings("staff")} role="menuitem"><UsersRound size={16} />Staff & permissions</button>
      <button type="button" onClick={() => openSettings("plan")} role="menuitem"><Sparkles size={16} />Current plan</button>
      <button type="button" onClick={() => openSettings("billing")} role="menuitem"><CreditCard size={16} />Billing</button>
      <button type="button" onClick={() => openSettings("general")} role="menuitem"><Settings size={16} />All settings</button>
      <button className="sidebar__profile-menu-danger" type="button" onClick={logoutUser} role="menuitem"><LogOut size={16} />Log out</button>
    </div>
  )}
  <button
    className="sidebar__business"
    type="button"
    onClick={() => setIsProfileMenuOpen((current) => !current)}
    title={isCollapsed ? businessName : undefined}
    aria-haspopup="menu"
    aria-expanded={isProfileMenuOpen}
  >
    <span className="sidebar__business-icon">
      <Store size={18} aria-hidden="true" />
    </span>

    <span className="sidebar__business-details sidebar__label">
      <strong>{businessName}</strong>
      <small>{readableRole(membership?.role)}</small>
    </span>

    <ChevronRight
      className={`sidebar__business-arrow ${isProfileMenuOpen ? "is-open" : ""}`}
      size={16}
      aria-hidden="true"
    />
  </button>
</div>
    </aside>
  );
}

export default Sidebar;
