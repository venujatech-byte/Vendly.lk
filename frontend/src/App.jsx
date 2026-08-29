// React state and effect hooks manage the sidebar and colour theme.
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

// Shared layout components and the individual dashboard pages.
import "./App.css";
import BusinessAssistant from "./components/BusinessAssistant.jsx";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
import ProfileModal from "./components/ProfileModal.jsx";
import SettingsModal from "./components/SettingsModal.jsx";
import { useAuth } from "./context/authContextValue.js";
const AnalyticsPage = lazy(() => import("./pages/AnalyticsPage.jsx"));
const CouriersPage = lazy(() => import("./pages/CouriersPage.jsx"));
const CustomersPage = lazy(() => import("./pages/CustomersPage.jsx"));
const InventoryPage = lazy(() => import("./pages/InventoryPage.jsx"));
const OrdersPage = lazy(() => import("./pages/OrdersPage.jsx"));
const OverviewPage = lazy(() => import("./pages/OverviewPage.jsx"));
const BusinessSetupPage = lazy(() => import("./pages/BusinessSetupPage.jsx"));
const CustomerAuthGate = lazy(() => import("./pages/CustomerAuthGate.jsx"));

// Choose a starting theme from local storage or the user's device preference.
function getInitialTheme() {
  const savedTheme = localStorage.getItem("vendly-theme");

  if (savedTheme === "light" || savedTheme === "dark") {
    return savedTheme;
  }

  const deviceUsesDarkMode = window.matchMedia(
    "(prefers-color-scheme: dark)",
  ).matches;

  if (deviceUsesDarkMode === true) {
    return "dark";
  }

  return "light";
}

function App() {  
  const { user } = useAuth();
  // Application-wide UI state shared by the sidebar and header.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState(getInitialTheme);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [settingsSection, setSettingsSection] = useState("general");
  const [isSettingsModalOpen, setIsSettingsModalOpen] = useState(false);

  function openSettings(section = "general") {
    setSettingsSection(section);
    setIsSettingsModalOpen(true);
  }

  // Apply the selected theme to the HTML element and remember the choice.
  useEffect(() => {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("vendly-theme", theme);
}, [theme]);

  // PayHere redirects back without a trusted payment result. Reopen Billing so
  // the dashboard can display the status recorded by the signed backend callback.
  useEffect(() => {
    const currentUrl = new URL(window.location.href);
    if (!currentUrl.searchParams.has("billing")) return;

    setSettingsSection("billing");
    setIsSettingsModalOpen(true);
    currentUrl.searchParams.delete("billing");
    window.history.replaceState({}, "", `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`);
  }, []);

  // Assistant settings commands open the same trusted settings modal as the
  // header and profile controls, preserving its permission checks.
  useEffect(() => {
    function handleAssistantSettings(event) {
      setSettingsSection(event.detail?.section || "general");
      setIsSettingsModalOpen(true);
    }

    window.addEventListener("vendly:open-settings", handleAssistantSettings);
    return () => window.removeEventListener("vendly:open-settings", handleAssistantSettings);
  }, []);

  // A Business Assistant theme request uses the same state as the header toggle.
  useEffect(() => {
    function handleAssistantTheme(event) {
      const requestedTheme = event.detail?.theme;
      if (requestedTheme === "light" || requestedTheme === "dark") {
        setTheme(requestedTheme);
      }
    }

    window.addEventListener("vendly:set-theme", handleAssistantTheme);
    return () => window.removeEventListener("vendly:set-theme", handleAssistantTheme);
  }, []);

  // Expand or collapse the left sidebar.
  function toggleSidebar() {
    setIsSidebarCollapsed((currentValue) => !currentValue);
  }

  // Change between the light and dark themes.
  function toggleTheme() {
  setTheme((currentTheme) => {
    if (currentTheme === "light") {
      return "dark";
    }

    return "light";
  });
}

  return (
  <Suspense
  fallback={
    <main className="app-loading" aria-label="Loading Vendly">
      <div className="app-loading__content">
        <div className="app-loading__logo">
          <span>V</span>
        </div>

        <h1>Vendly</h1>
        <p>Preparing your workspace...</p>

        <div className="app-loading__progress">
          <span />
        </div>

        <div className="app-loading__dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </div>
      </div>
    </main>
  }
>



  
  <Routes>
    {/* Login remains publicly accessible. */}
    <Route
      path="/login"
      element={<LoginPage />}
    />

    <Route
      path="/s/:storeCode"
      element={<CustomerAuthGate linkType="store" />}
    />

    <Route
      path="/p/:productCode"
      element={<CustomerAuthGate linkType="product" />}
    />

    {/* Google users enter their business name after their first login. */}
    <Route
      path="/setup-business"
      element={
        <ProtectedRoute requireSellerProfile={false}>
          <BusinessSetupPage />
        </ProtectedRoute>
      }
    />

    {/* Every dashboard route requires authentication. */}
    <Route
      path="/*"
      element={
        <ProtectedRoute>
          <div className="app">
            <Sidebar
              isCollapsed={isSidebarCollapsed}
              onToggleSidebar={toggleSidebar}
              onOpenProfile={() => setIsProfileModalOpen(true)}
              onOpenSettings={openSettings}
            />

            <div className="app__content">
              <Routes>
                <Route
                  path="/"
                  element={
                    <>
                      <Header
                        title="Overview"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <OverviewPage />
                    </>
                  }
                />

                <Route
                  path="/orders"
                  element={
                    <ProtectedRoute permission="orders:read">
                      <Header
                        title="Orders"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <OrdersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/inventory"
                  element={
                    <ProtectedRoute permission="inventory:read">
                      <Header
                        title="Inventory"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <InventoryPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/couriers"
                  element={
                    <ProtectedRoute permission="couriers:read">
                      <Header
                        title="Couriers"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <CouriersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/customers"
                  element={
                    <ProtectedRoute permission="customers:read">
                      <Header
                        title="Customers"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <CustomersPage />
                    </ProtectedRoute>
                  }
                />

                <Route
                  path="/analytics"
                  element={
                    <ProtectedRoute permission="analytics:read">
                      <Header
                        title="Analytics"
                        theme={theme}
                        onToggleTheme={toggleTheme}
                        onOpenProfile={() => setIsProfileModalOpen(true)}
                        onOpenSettings={openSettings}
                      />

                      <AnalyticsPage />
                    </ProtectedRoute>
                  }
                />

                {/* Unknown dashboard links return to Overview. */}
                <Route
                  path="*"
                  element={<Navigate to="/" replace />}
                />
              </Routes>
            </div>
            <BusinessAssistant
              isOpen={isAssistantOpen}
              onToggle={() => setIsAssistantOpen((current) => !current)}
              onClose={() => setIsAssistantOpen(false)}
            />
            <ProfileModal
              isOpen={isProfileModalOpen}
              onClose={() => setIsProfileModalOpen(false)}
              user={user}
            />
            <SettingsModal
              isOpen={isSettingsModalOpen}
              initialSection={settingsSection}
              onClose={() => setIsSettingsModalOpen(false)}
              onOpenProfile={() => {
                setIsSettingsModalOpen(false);
                setIsProfileModalOpen(true);
              }}
              theme={theme}
              onToggleTheme={toggleTheme}
            />
          </div>
        </ProtectedRoute>
      }
    />
  </Routes>
  </Suspense>
);
}

export default App;
