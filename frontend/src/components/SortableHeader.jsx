import { ArrowDown, ArrowUp } from "lucide-react";
import "./SortableHeader.css";

export default function SortableHeader({ columnKey, label, sorting, className }) {
  const isActive = sorting.sort.key === columnKey;
  const direction = isActive ? sorting.sort.direction : "none";

  return (
    <th className={className} aria-sort={direction}>
      <button
        className={`sortable-header${isActive ? " sortable-header--active" : ""}`}
        type="button"
        onClick={() => sorting.requestSort(columnKey)}
      >
        <span>{label}</span>
        {isActive && (
          sorting.sort.direction === "ascending"
            ? <ArrowUp size={12} aria-hidden="true" />
            : <ArrowDown size={12} aria-hidden="true" />
        )}
      </button>
    </th>
  );
}
