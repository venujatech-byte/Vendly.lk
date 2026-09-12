import { apiRequest } from "./apiClient";

export async function getBusinessMembers(businessId) {
  const response = await apiRequest(`/businesses/${businessId}/members`);
  return {
    members: response.members || [],
    invitations: response.invitations || [],
  };
}

export async function addBusinessMember(businessId, memberData) {
  const response = await apiRequest(`/businesses/${businessId}/members`, {
    method: "POST",
    body: memberData,
  });
  return response;
}

export async function updateBusinessMember(businessId, memberUid, changes) {
  const response = await apiRequest(
    `/businesses/${businessId}/members/${memberUid}`,
    { method: "PATCH", body: changes },
  );
  return response.member;
}

export async function removeBusinessMember(businessId, memberUid) {
  const response = await apiRequest(
    `/businesses/${businessId}/members/${memberUid}`,
    { method: "DELETE" },
  );
  return response;
}

export async function cancelBusinessInvitation(businessId, invitationId) {
  const response = await apiRequest(
    `/businesses/${businessId}/invitations/${invitationId}`,
    { method: "DELETE" },
  );
  return response;
}

export async function getPublicInvitation(token) {
  const response = await apiRequest(`/invitations/${token}`, {
    requiresAuthentication: false,
  });
  return response.invitation;
}
