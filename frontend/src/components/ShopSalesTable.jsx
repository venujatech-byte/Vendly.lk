import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, Package, Printer, ShieldCheck, Trash2 } from "lucide-react";
import ActionMenu from "./ActionMenu";
import TablePagination from "./TablePagination";
import useTablePagination from "../hooks/useTablePagination";
import "./ShopSales.css";

function hasActiveWarranty(sale) {
  return (sale.items ?? []).some((item) => item.warrantyExpiresAt && new Date(item.warrantyExpiresAt) >= new Date());
}

export default function ShopSalesTable({ sales, onPrint, onWarranty, onRemove }) {
  const [expanded, setExpanded] = useState(null);
  const pagination = useTablePagination(sales);
  return <section className="orders-table-section shop-sales-table">
    <div className="orders-table__scroll"><table className="orders-table"><thead><tr>
      <th></th><th>Sale number</th><th>Items</th><th>Total</th><th>Date</th><th>Actions</th>
    </tr></thead><tbody>
      {pagination.pageItems.map((sale) => <Fragment key={sale.id}>
        <tr><td><button className="orders-table__expand-button" type="button" onClick={() => setExpanded(expanded === sale.id ? null : sale.id)}>{expanded === sale.id ? <ChevronDown size={18}/> : <ChevronRight size={18}/>}</button></td>
          <td><strong>#{sale.saleNumber}</strong>{sale.customerName && <span className="orders-table__secondary">{sale.customerName}</span>}</td>
          <td><div className="orders-table__items">{sale.items.slice(0, 3).map((item) => <span className="orders-table__product-preview" key={item.id}>{item.imageUrl ? <img src={item.imageUrl} alt=""/> : <Package size={18}/>}</span>)}{sale.itemCount > 3 && <span>+{sale.itemCount - 3}</span>}</div></td>
          <td className="orders-table__total">{sale.total}</td><td><span>{sale.date}</span><span className="orders-table__secondary">{sale.time}</span></td>
          <td><ActionMenu items={[{ label: "Print receipt", icon: <Printer size={16}/>, onClick: () => onPrint(sale) }, ...(hasActiveWarranty(sale) ? [{ label: "Warranty claim", icon: <ShieldCheck size={16}/>, onClick: () => onWarranty(sale) }] : []), { label: "Delete sale", icon: <Trash2 size={16}/>, danger: true, onClick: () => onRemove(sale) }]}/></td>
        </tr>
        {expanded === sale.id && <tr className="orders-table__details-row"><td colSpan={6}><div className="shop-sale-details">
          <section><h3>Items sold</h3>{sale.items.map((item) => <div className="shop-sale-details__item" key={item.id}><span>{item.name}{item.size ? ` · ${item.size}` : ""} × {item.quantity}</span><strong>{item.price}</strong></div>)}</section>
          <section><h3>Sale information</h3><p>Payment: <strong>{sale.paymentMethod}</strong></p><p>Customer: <strong>{sale.customerName || "Walk-in customer"}</strong></p><p>Phone: <strong>{sale.phoneNumber || "Not recorded"}</strong></p>{sale.note && <p>Note: <strong>{sale.note}</strong></p>}</section>
          <section className="shop-sale-details__actions"><button type="button" onClick={() => onPrint(sale)}><Printer size={16}/>Print receipt</button>{hasActiveWarranty(sale) && <button type="button" onClick={() => onWarranty(sale)}><ShieldCheck size={16}/>Warranty claim</button>}</section>
        </div></td></tr>}
      </Fragment>)}
      {!sales.length && <tr><td colSpan={6}>No physical-shop sales found.</td></tr>}
    </tbody></table></div>
    <TablePagination pagination={pagination} label="shop sales" />
  </section>;
}
