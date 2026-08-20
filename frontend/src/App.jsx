// React state and effect hooks manage the sidebar and colour theme.
import ProtectedRoute from "./components/ProtectedRoute.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import { lazy, Suspense, useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

// Shared layout components and the individual dashboard pages.
import "./App.css";
import Header from "./components/Header.jsx";
import Sidebar from "./components/Sidebar.jsx";
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
  // Application-wide UI state shared by the sidebar and header.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [theme, setTheme] = useState(getInitialTheme);

  // Apply the selected theme to the HTML element and remember the choice.
  useEffect(() => {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("vendly-theme", theme);
}, [theme]);

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
  <Suspense fallback={<main className="app-loading">Loading Vendly...</main>}>
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
          </div>
        </ProtectedRoute>
      }
    />
  </Routes>
  </Suspense>
);
}

export default App;
