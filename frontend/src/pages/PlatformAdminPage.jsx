import { Activity, Building2, Download, Gauge, MessageSquare, Package, RefreshCw, Search, ShoppingCart, UserRound, Wifi, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import StatCard from "../components/StatCard";
import { getPlatformSellerDashboard, getPlatformServerHealth, getPlatformSellerDetail } from "../services/platformAdminService";
import "./PlatformAdminPage.css";

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not available";
  return date.toLocaleDateString("en-LK", { year: "numeric", month: "short", day: "numeric" });
}

function formatBytes(value) {
  if (value === null || value === undefined) return "No data";
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function PlatformAdminPage() {
  const [dashboard, setDashboard] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [serverHealth, setServerHealth] = useState(null);
  const [selectedSeller, setSelectedSeller] = useState(null);
  const [isLoadingSeller, setIsLoadingSeller] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  function loadDashboard() {
    setIsRefreshing(true);
    return getPlatformSellerDashboard()
      .then((data) => setDashboard(data))
      .catch((requestError) => setError(requestError))
      .finally(() => setIsRefreshing(false));
  }

  useEffect(() => {
    let current = true;
    loadDashboard().finally(() => current && setIsLoading(false));
    return () => { current = false; };
  }, []);

  function refreshServerHealth() {
    getPlatformServerHealth().then(setServerHealth).catch((requestError) => setServerHealth({ status: "unavailable", message: requestError.message }));
  }

  async function openSeller(seller) {
    setIsLoadingSeller(true);
    try {
      setSelectedSeller(await getPlatformSellerDetail(seller.id));
    } catch (requestError) {
      setError(requestError);
    } finally {
      setIsLoadingSeller(false);
    }
  }

  useEffect(() => {
    getPlatformServerHealth().then(setServerHealth).catch((requestError) => setServerHealth({ status: "unavailable", message: requestError.message }));
  }, []);

  async function loadMore() {
    if (!dashboard?.nextCursor) return;
    setIsLoadingMore(true);
    try {
      const nextPage = await getPlatformSellerDashboard(dashboard.nextCursor);
      setDashboard((current) => ({
        ...nextPage,
        sellers: [...(current?.sellers ?? []), ...(nextPage.sellers ?? [])],
      }));
    } catch (requestError) {
      setError(requestError);
    } finally {
      setIsLoadingMore(false);
    }
  }

  const summary = dashboard?.summary ?? {};
  const visibleSellers = useMemo(() => (dashboard?.sellers ?? []).filter((seller) => {
    const searchable = `${seller.businessName} ${seller.owner.name} ${seller.owner.email}`.toLowerCase();
    return (statusFilter === "all" || seller.status === statusFilter)
      && searchable.includes(search.trim().toLowerCase());
  }), [dashboard?.sellers, search, statusFilter]);

  function exportVisibleSellers() {
    const rows = [
      ["Business", "Owner", "Email", "Status", "Joined", "Last activity", "Orders", "Products", "Customers"],
      ...visibleSellers.map((seller) => [
        seller.businessName, seller.owner.name, seller.owner.email, seller.status,
        formatDate(seller.createdAt), formatDate(seller.lastActivityAt),
        seller.stats.orders, seller.stats.products, seller.stats.customers,
      ]),
    ];
    const csv = rows.map((row) => row.map((value) => `"${String(value ?? "").replaceAll('"', '""')}"`).join(",")).join("\n");
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "vendly-sellers.csv";
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <main className="platform-admin-page">
      <section className="platform-admin-page__hero">
        <div><span>Vendly internal</span><h1>Seller dashboard</h1><p>Registered businesses and their current platform activity.</p></div>
      </section>

      <section className="platform-admin-page__server-card" aria-label="AWS server health">
        <header><div><h2><Activity size={18} /> AWS server health</h2><p>{serverHealth?.region ? `${serverHealth.region} · ${serverHealth.instanceId}` : "Live EC2 and CloudWatch status"}</p></div><span className={`platform-admin-page__server-status platform-admin-page__server-status--${serverHealth?.status ?? "loading"}`}>{serverHealth?.status ?? "loading"}</span></header>
        {!serverHealth?.configured ? <p className="platform-admin-page__server-note">{serverHealth?.message ?? "Loading AWS monitoring…"}</p> : null}
        {serverHealth?.configured && serverHealth?.metrics ? <div className="platform-admin-page__server-metrics"><div><Gauge /><span>CPU usage</span><strong>{serverHealth.metrics.cpuPercent == null ? "No data" : `${serverHealth.metrics.cpuPercent}%`}</strong></div><div><Gauge /><span>Memory usage</span><strong>{serverHealth.metrics.memoryPercent == null ? "No data" : `${serverHealth.metrics.memoryPercent}%`}</strong><small>CWAgent</small></div><div><Gauge /><span>Disk usage</span><strong>{serverHealth.metrics.diskPercent == null ? "No data" : `${serverHealth.metrics.diskPercent}%`}</strong><small>CWAgent root disk</small></div><div><Activity /><span>Instance</span><strong>{serverHealth.state ?? "Unknown"}</strong><small>{serverHealth.instanceType ?? "EC2"}</small></div><div><Wifi /><span>Network in/out</span><strong>{formatBytes(serverHealth.metrics.networkInBytes)} / {formatBytes(serverHealth.metrics.networkOutBytes)}</strong><small>Latest 5-minute average</small></div><div><Activity /><span>AWS checks</span><strong>{serverHealth.checks?.system ?? "unknown"} / {serverHealth.checks?.instance ?? "unknown"}</strong><small>System / instance</small></div></div> : null}
        {serverHealth?.note ? <p className="platform-admin-page__server-note">{serverHealth.note}</p> : null}
      </section>

      {error ? (
        <section className="platform-admin-page__message" role="alert">
          {error.status === 403 ? "This Firebase account is not authorised as a Vendly team admin." : "The seller dashboard could not be loaded."}
        </section>
      ) : (
        <>
          <section className="platform-admin-page__stats" aria-label="Platform totals">
            <StatCard label="Registered sellers" value={summary.registeredSellers ?? 0} icon={Building2} tone="blue" />
            <StatCard label="Total chats" value={summary.totalChats ?? summary.chats ?? 0} icon={MessageSquare} tone="green" />
            <StatCard label="Orders" value={summary.orders ?? 0} icon={ShoppingCart} tone="purple" />
            <StatCard label="Products" value={summary.products ?? 0} icon={Package} tone="orange" />
            <StatCard label="Customers" value={summary.customers ?? 0} icon={UserRound} tone="indigo" />
          </section>

          <section className="platform-admin-page__table-card">
            <header>
              <div><h2>Registered sellers</h2><p>{isLoading ? "Loading sellers…" : `${visibleSellers.length} of ${(dashboard?.sellers ?? []).length} loaded sellers shown`}</p></div>
              <button className="platform-admin-page__export" type="button" onClick={loadDashboard} disabled={isRefreshing}><RefreshCw size={15} /> {isRefreshing ? "Refreshing" : "Refresh"}</button><button className="platform-admin-page__export" type="button" onClick={exportVisibleSellers} disabled={!visibleSellers.length}><Download size={15} /> Export CSV</button>
            </header>
            <div className="platform-admin-page__controls">
              <label><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search business, owner, or email" /></label>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter seller status">
                <option value="all">All statuses</option><option value="active">Active</option><option value="inactive">Inactive</option><option value="suspended">Suspended</option>
              </select>
            </div>
            <div className="platform-admin-page__table-scroll">
              <table>
                <thead><tr><th>Business</th><th>Owner</th><th>Joined</th><th>Last activity</th><th>Orders</th><th>Products</th><th>Customers</th><th>Status</th><th>Action</th></tr></thead>
                <tbody>
                  {!isLoading && visibleSellers.length === 0 ? <tr><td colSpan="9">No sellers match this search.</td></tr> : null}
                  {visibleSellers.map((seller) => (
                    <tr key={seller.id}>
                      <td><strong>{seller.businessName}</strong></td>
                      <td><span>{seller.owner.name}</span><small>{seller.owner.email || "No email recorded"}</small></td>
                      <td>{formatDate(seller.createdAt)}</td><td>{formatDate(seller.lastActivityAt)}</td>
                      <td>{seller.stats.orders}</td><td>{seller.stats.products}</td><td>{seller.stats.customers}</td>
                      <td><span className={`platform-admin-page__status platform-admin-page__status--${seller.status}`}>{seller.status}</span></td><td><button className="platform-admin-page__view" type="button" onClick={() => openSeller(seller)}>View</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {dashboard?.hasMore ? <button className="platform-admin-page__more" type="button" onClick={loadMore} disabled={isLoadingMore}>{isLoadingMore ? "Loading…" : "Load more sellers"}</button> : null}
          </section>
        </>
      )}
      {isLoadingSeller ? <p className="platform-admin-page__server-note">Loading seller details…</p> : null}
      {selectedSeller ? <section className="platform-admin-page__seller-detail" aria-label="Seller details"><header><div><h2>{selectedSeller.businessName}</h2><p>{selectedSeller.owner.name} · {selectedSeller.owner.email}</p></div><button type="button" onClick={() => setSelectedSeller(null)} aria-label="Close seller details"><X size={18} /></button></header><div className="platform-admin-page__detail-stats"><strong>{selectedSeller.stats.orders}<small>Orders</small></strong><strong>{selectedSeller.stats.products}<small>Products</small></strong><strong>{selectedSeller.stats.customers}<small>Customers</small></strong></div><h3>Recent orders</h3>{selectedSeller.recentOrders?.length ? <ul>{selectedSeller.recentOrders.map((order) => <li key={order.id}><span>#{order.orderNumber}<small>{formatDate(order.createdAt)}</small></span><span>{order.status}</span></li>)}</ul> : <p className="platform-admin-page__server-note">No orders recorded yet.</p>}</section> : null}
    </main>
  );
}

export default PlatformAdminPage;
