import { apiRequest } from "./apiClient";


export async function getBusinessBilling(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/billing`);
  return response.billing;
}


export async function createPayHereCheckout(businessId, checkoutData) {
  const response = await apiRequest(`/businesses/${businessId}/billing/checkout`, {
    method: "POST",
    body: checkoutData,
  });
  return response.checkout;
}


export function redirectToPayHere(checkout) {
  const form = document.createElement("form");
  form.method = "POST";
  form.action = checkout.actionUrl;
  form.hidden = true;

  Object.entries(checkout.fields).forEach(([name, value]) => {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value ?? "";
    form.appendChild(input);
  });

  document.body.appendChild(form);
  form.submit();
}
