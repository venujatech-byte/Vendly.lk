import { Package } from "lucide-react";
import TablePagination from "./TablePagination";
import SortableHeader from "./SortableHeader";
import useTablePagination from "../hooks/useTablePagination";
import useTableSort from "../hooks/useTableSort";
import "./ShopSales.css";

const claimTypeLabels = {
  "supplier-warranty": "Supplier warranty",
  "shop-warranty": "Shop warranty",
  "shop-repair": "Shop repair",
};

const money = (minor = 0) =>
  `LKR ${(minor / 100).toLocaleString("en-LK", { minimumFractionDigits: 2 })}`;

const warrantySortAccessors = {
  claim: (claim) => claim.claimNumber,
  sale: (claim) => claim.sourceNumber,
  item: (claim) => claim.item?.name,
  handling: (claim) => claimTypeLabels[claim.claimType] ?? claim.claimType,
  impact: (claim) => claim.revenueImpactMinor ?? 0,
  customer: (claim) => claim.customerName,
  reason: (claim) => claim.reason,
  status: (claim) => claim.status,
  date: (claim) => new Date(claim.createdAt ?? 0),
};

export default function WarrantyClaimsTable({ claims = [] }) {
  const sorting = useTableSort(claims, warrantySortAccessors);
  const pagination = useTablePagination(sorting.sortedItems);

  return (
    <section className="orders-table-section warranty-table">
      <div className="orders-table__scroll">
        <table className="orders-table">
          <thead>
            <tr><SortableHeader columnKey="claim" label="Claim" sorting={sorting} /><SortableHeader columnKey="sale" label="Original sale" sorting={sorting} /><SortableHeader columnKey="item" label="Item" sorting={sorting} /><SortableHeader columnKey="handling" label="Handling" sorting={sorting} /><SortableHeader columnKey="impact" label="Revenue impact" sorting={sorting} /><SortableHeader columnKey="customer" label="Customer" sorting={sorting} /><SortableHeader columnKey="reason" label="Reason" sorting={sorting} /><SortableHeader columnKey="status" label="Status" sorting={sorting} /><SortableHeader columnKey="date" label="Date" sorting={sorting} /></tr>
          </thead>
          <tbody>
            {pagination.pageItems.map((claim) => (
              <tr key={claim.id}>
                <td><strong>#{claim.claimNumber}</strong></td>
                <td>{claim.sourceNumber}</td>
                <td><div className="warranty-table__item">{claim.item?.mediaUrl ? <img src={claim.item.mediaUrl} alt="" /> : <Package size={20} />}<span>{claim.item?.name}<small>Qty: {claim.claimQuantity ?? 1}</small></span></div></td>
                <td>{claimTypeLabels[claim.claimType] ?? "Supplier warranty"}</td>
                <td>{claim.revenueImpactMinor ? money(claim.revenueImpactMinor) : "No deduction"}</td>
                <td>{claim.customerName}<span className="orders-table__secondary">{claim.phoneNumber}</span></td>
                <td>{claim.reason}<span className="orders-table__secondary">{claim.details}</span></td>
                <td><span className="warranty-table__status">{claim.status}</span></td>
                <td>{claim.createdAt ? new Date(claim.createdAt).toLocaleDateString("en-LK") : "—"}</td>
              </tr>
            ))}
            {!claims.length && <tr><td colSpan={9}>No warranty claims recorded.</td></tr>}
          </tbody>
        </table>
      </div>
      <TablePagination pagination={pagination} label="warranty claims" />
    </section>
  );
}
