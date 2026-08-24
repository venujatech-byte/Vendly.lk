import { Package } from "lucide-react";
import "./ShopSales.css";
export default function WarrantyClaimsTable({ claims }) {
  return <section className="orders-table-section warranty-table"><div className="orders-table__scroll"><table className="orders-table"><thead><tr><th>Claim</th><th>Original sale</th><th>Item</th><th>Customer</th><th>Reason</th><th>Status</th><th>Date</th></tr></thead><tbody>
    {claims.map((claim) => <tr key={claim.id}><td><strong>#{claim.claimNumber}</strong></td><td>{claim.sourceNumber}</td><td><div className="warranty-table__item">{claim.item?.mediaUrl ? <img src={claim.item.mediaUrl} alt=""/> : <Package size={20}/>}<span>{claim.item?.name}</span></div></td><td>{claim.customerName}<span className="orders-table__secondary">{claim.phoneNumber}</span></td><td>{claim.reason}<span className="orders-table__secondary">{claim.details}</span></td><td><span className="warranty-table__status">{claim.status}</span></td><td>{claim.createdAt ? new Date(claim.createdAt).toLocaleDateString("en-LK") : "—"}</td></tr>)}
    {!claims.length && <tr><td colSpan={7}>No warranty claims recorded.</td></tr>}
  </tbody></table></div></section>;
}
