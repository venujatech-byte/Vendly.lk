import { useEffect, useState } from "react";

import { createCategory, updateCategory } from "../services/categoryService";
import ModalShell from "./ModalShell";

import "./InventoryForm.css";

function AddCategoryModal({ isOpen, businessId, category = null, onClose, onCreated, onUpdated }) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    sortOrder: "0",
  });
  const [errorMessage, setErrorMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setFormData(category ? { name: category.name ?? "", description: category.description ?? "", sortOrder: String(category.sortOrder ?? 0) } : { name: "", description: "", sortOrder: "0" });
      setErrorMessage("");
    }
  }, [isOpen, category]);

  function updateField(event) {
    const { name, value } = event.target;
    setFormData((current) => ({ ...current, [name]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setErrorMessage("");
    setIsSaving(true);

    try {
      const response = category ? await updateCategory(businessId, category.id, {
        ...formData,
        sortOrder: Number(formData.sortOrder),
      }) : await createCategory(businessId, {
        ...formData,
        sortOrder: Number(formData.sortOrder),
      });
      if (category) onUpdated?.(response.category);
      else onCreated?.(response.category);
      onClose();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <ModalShell
      isOpen={isOpen}
      title={category ? "Edit Category" : "Add Category"}
      description="Create a category used to organise your catalogue."
      onClose={onClose}
    >
      <form className="inventory-form" onSubmit={handleSubmit}>
        <label>
          Category name
          <input
            name="name"
            value={formData.name}
            onChange={updateField}
            placeholder="Example: Footwear"
            maxLength={120}
            autoFocus
            required
          />
        </label>

        <label>
          Description
          <textarea
            name="description"
            value={formData.description}
            onChange={updateField}
            placeholder="What kind of products belong here?"
            maxLength={500}
            rows={4}
          />
        </label>

        <label>
          Display order
          <input
            name="sortOrder"
            type="number"
            value={formData.sortOrder}
            onChange={updateField}
            min="0"
            step="1"
          />
        </label>

        {errorMessage && <p className="inventory-form__error">{errorMessage}</p>}

        <footer className="inventory-form__footer">
          <button type="button" onClick={onClose}>Cancel</button>
          <button className="inventory-form__primary" type="submit" disabled={isSaving}>
            {isSaving ? "Saving..." : category ? "Save changes" : "Add Category"}
          </button>
        </footer>
      </form>
    </ModalShell>
  );
}

export default AddCategoryModal;
