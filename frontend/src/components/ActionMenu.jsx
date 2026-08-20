import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreVertical } from "lucide-react";

import "./ActionMenu.css";

function ActionMenu({ label = "More actions", items = [] }) {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, right: 0 });
  const buttonReference = useRef(null);
  const menuReference = useRef(null);

  function openMenu() {
    const rectangle = buttonReference.current?.getBoundingClientRect();
    if (rectangle) {
      setPosition({
        top: Math.min(rectangle.bottom + 6, window.innerHeight - 120),
        right: Math.max(8, window.innerWidth - rectangle.right),
      });
    }
    setIsOpen((open) => !open);
  }

  useEffect(() => {
    if (!isOpen) return undefined;

    function closeOnOutsideClick(event) {
      if (
        !buttonReference.current?.contains(event.target) &&
        !menuReference.current?.contains(event.target)
      ) setIsOpen(false);
    }

    function closeMenu() {
      setIsOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutsideClick);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideClick);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
    };
  }, [isOpen]);

  return (
    <div className="action-menu">
      <button ref={buttonReference} className="orders-table__more-button" type="button" aria-label={label} aria-expanded={isOpen} onClick={openMenu}>
        <MoreVertical size={19} aria-hidden="true" />
      </button>
      {isOpen && createPortal(
        <div ref={menuReference} className="action-menu__list" style={position} role="menu">
          {items.map((item) => (
            <button key={item.label} type="button" className={item.danger ? "action-menu__item action-menu__item--danger" : "action-menu__item"} onClick={() => { setIsOpen(false); item.onClick?.(); }} role="menuitem" disabled={item.disabled}>
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}

export default ActionMenu;
