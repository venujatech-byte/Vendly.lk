import React, {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { Check, ChevronDown } from "lucide-react";
import "./CustomSelect.css";

/**
 * Helper to extract option objects from React children (<option> elements or fragments).
 */
function extractOptionsFromChildren(children) {
  const result = [];
  React.Children.forEach(children, (child) => {
    if (!child) return;
    if (child.type === "option") {
      result.push({
        value: child.props.value !== undefined ? child.props.value : child.props.children,
        label: child.props.children,
        disabled: Boolean(child.props.disabled),
      });
    } else if (child.props && child.props.children) {
      // Traverse nested children such as Fragments or optgroups
      result.push(...extractOptionsFromChildren(child.props.children));
    }
  });
  return result;
}

export default function CustomSelect({
  id,
  name,
  value,
  defaultValue = "",
  onChange,
  options,
  children,
  placeholder = "Select...",
  disabled = false,
  className = "",
  style = {},
  required = false,
  autoFocus = false,
  "aria-label": ariaLabel,
  ...restProps
}) {
  const generatedId = useId();
  const selectId = id || generatedId;

  const [isOpen, setIsOpen] = useState(false);
  const [internalValue, setInternalValue] = useState(defaultValue);
  const [placement, setPlacement] = useState("bottom");
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  const containerRef = useRef(null);
  const menuRef = useRef(null);
  const triggerRef = useRef(null);

  const isControlled = value !== undefined;
  const currentValue = isControlled ? value : internalValue;

  // Normalize options array from options prop or React children
  const parsedOptions = useMemo(() => {
    if (options && Array.isArray(options) && options.length > 0) {
      return options.map((opt) =>
        typeof opt === "object" && opt !== null
          ? {
              value: opt.value !== undefined ? opt.value : "",
              label: opt.label !== undefined ? opt.label : String(opt.value),
              disabled: Boolean(opt.disabled),
              icon: opt.icon,
            }
          : { value: String(opt), label: String(opt) }
      );
    }
    if (children) {
      return extractOptionsFromChildren(children);
    }
    return [];
  }, [options, children]);

  // Find currently selected option
  const selectedOption = useMemo(() => {
    return parsedOptions.find((opt) => String(opt.value) === String(currentValue));
  }, [parsedOptions, currentValue]);

  // Determine display label
  const displayLabel = useMemo(() => {
    if (selectedOption) {
      return selectedOption.label;
    }
    if (currentValue !== "" && currentValue !== null && currentValue !== undefined) {
      return String(currentValue);
    }
    return placeholder;
  }, [selectedOption, currentValue, placeholder]);

  // Check placement on open
  useEffect(() => {
    if (isOpen && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect();
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;
      if (spaceBelow < 220 && spaceAbove > spaceBelow) {
        setPlacement("top");
      } else {
        setPlacement("bottom");
      }

      // Initialize highlighted index to selected item
      const initialIdx = parsedOptions.findIndex(
        (opt) => String(opt.value) === String(currentValue)
      );
      setHighlightedIndex(initialIdx >= 0 ? initialIdx : 0);
    }
  }, [isOpen, parsedOptions, currentValue]);

  // Click outside to close
  useEffect(() => {
    if (!isOpen) return;

    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("touchstart", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("touchstart", handleClickOutside);
    };
  }, [isOpen]);

  // Scroll highlighted item into view
  useEffect(() => {
    if (isOpen && menuRef.current && highlightedIndex >= 0) {
      const items = menuRef.current.querySelectorAll(".custom-select__option");
      const target = items[highlightedIndex];
      if (target) {
        target.scrollIntoView({ block: "nearest" });
      }
    }
  }, [isOpen, highlightedIndex]);

  const handleSelect = useCallback(
    (option) => {
      if (!option || option.disabled) return;

      if (!isControlled) {
        setInternalValue(option.value);
      }

      setIsOpen(false);
      triggerRef.current?.focus();

      if (onChange) {
        const syntheticEvent = {
          target: {
            id: selectId,
            name: name || selectId,
            value: option.value,
            type: "select-one",
          },
          currentTarget: {
            id: selectId,
            name: name || selectId,
            value: option.value,
          },
          preventDefault: () => {},
          stopPropagation: () => {},
        };
        onChange(syntheticEvent);
      }
    },
    [isControlled, onChange, selectId, name]
  );

  // Keyboard navigation
  const handleKeyDown = (event) => {
    if (disabled) return;

    if (!isOpen) {
      if (["Enter", " ", "ArrowDown", "ArrowUp"].includes(event.key)) {
        event.preventDefault();
        setIsOpen(true);
      }
      return;
    }

    switch (event.key) {
      case "Escape":
        event.preventDefault();
        setIsOpen(false);
        triggerRef.current?.focus();
        break;

      case "Tab":
        setIsOpen(false);
        break;

      case "ArrowDown": {
        event.preventDefault();
        let next = highlightedIndex + 1;
        while (next < parsedOptions.length && parsedOptions[next]?.disabled) {
          next++;
        }
        if (next < parsedOptions.length) {
          setHighlightedIndex(next);
        }
        break;
      }

      case "ArrowUp": {
        event.preventDefault();
        let prev = highlightedIndex - 1;
        while (prev >= 0 && parsedOptions[prev]?.disabled) {
          prev--;
        }
        if (prev >= 0) {
          setHighlightedIndex(prev);
        }
        break;
      }

      case "Enter":
      case " ": {
        event.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < parsedOptions.length) {
          handleSelect(parsedOptions[highlightedIndex]);
        }
        break;
      }

      default:
        break;
    }
  };

  const toggleOpen = () => {
    if (disabled) return;
    setIsOpen((prev) => !prev);
  };

  return (
    <div
      ref={containerRef}
      className={`custom-select ${isOpen ? "is-open" : ""} ${disabled ? "is-disabled" : ""} ${className}`}
      style={style}
      onKeyDown={handleKeyDown}
      {...restProps}
    >
      {/* Hidden native select for form serialization, accessibility, and automation */}
      <select
        aria-hidden="true"
        tabIndex={-1}
        id={selectId}
        name={name}
        value={currentValue ?? ""}
        onChange={() => {}}
        required={required}
        disabled={disabled}
        className="custom-select__native"
      >
        {placeholder && <option value="">{placeholder}</option>}
        {parsedOptions.map((opt, idx) => (
          <option key={idx} value={opt.value} disabled={opt.disabled}>
            {typeof opt.label === "string" ? opt.label : String(opt.value)}
          </option>
        ))}
      </select>

      {/* Visible styled trigger button */}
      <button
        ref={triggerRef}
        type="button"
        className="custom-select__trigger"
        onClick={toggleOpen}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-label={ariaLabel}
        autoFocus={autoFocus}
      >
        <span className="custom-select__value">
          {displayLabel}
        </span>
        <ChevronDown
          size={14}
          className={`custom-select__chevron ${isOpen ? "is-rotated" : ""}`}
          aria-hidden="true"
        />
      </button>

      {/* Styled dropdown menu popup */}
      {isOpen && (
        <div
          ref={menuRef}
          role="listbox"
          className={`custom-select__menu custom-select__menu--${placement}`}
        >
          {parsedOptions.length === 0 ? (
            <div className="custom-select__empty">No options</div>
          ) : (
            parsedOptions.map((opt, index) => {
              const isSelected = String(opt.value) === String(currentValue);
              const isHighlighted = index === highlightedIndex;

              return (
                <div
                  key={index}
                  role="option"
                  aria-selected={isSelected}
                  aria-disabled={opt.disabled}
                  className={`custom-select__option ${isSelected ? "is-selected" : ""} ${isHighlighted ? "is-highlighted" : ""} ${opt.disabled ? "is-disabled" : ""}`}
                  onClick={() => handleSelect(opt)}
                  onMouseEnter={() => !opt.disabled && setHighlightedIndex(index)}
                >
                  <span className="custom-select__option-label">
                    {opt.label}
                  </span>
                  {isSelected && (
                    <Check
                      size={14}
                      strokeWidth={2.5}
                      className="custom-select__check"
                      aria-hidden="true"
                    />
                  )}
                </div>
              );
            })
          )}
        </div>
      )}
    </div>
  );
}
