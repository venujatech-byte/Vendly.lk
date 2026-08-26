import "./TablePagination.css";

function pageNumbers(page, totalPages) {
  const first = Math.max(1, Math.min(page - 2, totalPages - 4));
  const last = Math.min(totalPages, first + 4);
  return Array.from({ length: last - first + 1 }, (_, index) => first + index);
}

export default function TablePagination({ pagination, label, variant = "orders" }) {
  const isCustomerVariant = variant === "customers";
  const footerClass = isCustomerVariant ? "customer-table-footer" : "orders-table__footer";
  const controlsClass = isCustomerVariant ? "customer-table-pagination" : "orders-table__pagination";
  const activeClass = isCustomerVariant ? "is-active" : "orders-table__page--active";

  return (
    <footer className={`${footerClass} table-pagination-footer`}>
      <span>Showing {pagination.start} to {pagination.end} of {pagination.total} {label}</span>
      <div className={controlsClass} aria-label={`${label} pagination`}>
        <button type="button" disabled={pagination.page === 1} onClick={() => pagination.setPage(pagination.page - 1)}>Previous</button>
        {pageNumbers(pagination.page, pagination.totalPages).map((pageNumber) => (
          <button
            key={pageNumber}
            type="button"
            className={pageNumber === pagination.page ? activeClass : undefined}
            aria-current={pageNumber === pagination.page ? "page" : undefined}
            onClick={() => pagination.setPage(pageNumber)}
          >
            {pageNumber}
          </button>
        ))}
        <button type="button" disabled={pagination.page === pagination.totalPages} onClick={() => pagination.setPage(pagination.page + 1)}>Next</button>
      </div>
    </footer>
  );
}
