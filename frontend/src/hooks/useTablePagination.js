import { useEffect, useMemo, useState } from "react";

export const TABLE_PAGE_SIZE = 10;

// Keep dashboard tables small and predictable while preserving their filters.
export default function useTablePagination(items = [], pageSize = TABLE_PAGE_SIZE) {
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));
  const itemKey = items
    .map((item, index) => item?.id ?? item?.orderNumber ?? item?.saleNumber ?? index)
    .join("|");

  useEffect(() => {
    setPage(1);
  }, [itemKey]);

  useEffect(() => {
    setPage((currentPage) => Math.min(currentPage, totalPages));
  }, [totalPages]);

  const startIndex = (page - 1) * pageSize;
  const pageItems = useMemo(
    () => items.slice(startIndex, startIndex + pageSize),
    [items, startIndex, pageSize],
  );

  return {
    page,
    setPage,
    totalPages,
    pageItems,
    start: items.length === 0 ? 0 : startIndex + 1,
    end: Math.min(startIndex + pageSize, items.length),
    total: items.length,
  };
}
