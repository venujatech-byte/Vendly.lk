import { apiRequest } from "./apiClient";


export async function getBusinessMembers(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/members`);
  return response.members;
}


export async function addBusinessMember(businessId, memberData) {
  const response = await apiRequest(`/businesses/${businessId}/members`, {
    method: "POST",
    body: memberData,
  });
  return response.member;
}


export async function updateBusinessMember(businessId, memberUid, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/members/${memberUid}`,
    { method: "PATCH", body: changes },
  );
  return response.member;
}
