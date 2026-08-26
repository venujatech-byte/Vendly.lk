import { useMemo, useState } from "react";

function compareValues(leftValue, rightValue) {
  if (leftValue == null && rightValue == null) return 0;
  if (leftValue == null) return 1;
  if (rightValue == null) return -1;

  if (typeof leftValue === "number" && typeof rightValue === "number") {
    return leftValue - rightValue;
  }

  if (leftValue instanceof Date && rightValue instanceof Date) {
    return leftValue.getTime() - rightValue.getTime();
  }

  return String(leftValue).localeCompare(String(rightValue), undefined, {
    numeric: true,
    sensitivity: "base",
  });
}

// Sort the complete filtered data set before it is handed to pagination.
export default function useTableSort(items = [], accessors = {}) {
  const [sort, setSort] = useState({ key: null, direction: "ascending" });

  function requestSort(key) {
    setSort((current) => ({
      key,
      direction:
        current.key === key && current.direction === "ascending"
          ? "descending"
          : "ascending",
    }));
  }

  const sortedItems = useMemo(() => {
    if (!sort.key || !accessors[sort.key]) return items;

    const accessor = accessors[sort.key];
    const multiplier = sort.direction === "ascending" ? 1 : -1;

    return items
      .map((item, originalIndex) => ({ item, originalIndex }))
      .sort((left, right) => {
        const result = compareValues(accessor(left.item), accessor(right.item));
        return result === 0
          ? left.originalIndex - right.originalIndex
          : result * multiplier;
      })
      .map(({ item }) => item);
  }, [items, accessors, sort]);

  return { sortedItems, sort, requestSort };
}
