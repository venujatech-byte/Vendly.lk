function pendingProfileKey(email) {
  return `vendly-pending-profile:${String(email ?? "").trim().toLowerCase()}`;
}


// Read onboarding details kept locally until an email address is verified.
export async function getSellerProfile(user) {
  if (!user?.email) return null;

  const storedValue = localStorage.getItem(pendingProfileKey(user.email));

  if (!storedValue) return null;

  try {
    return JSON.parse(storedValue);
  } catch {
    localStorage.removeItem(pendingProfileKey(user.email));
    return null;
  }
}


// Unverified accounts cannot use Flask yet, so remember only the non-sensitive
// onboarding names in this browser until the first verified login.
export async function saveSellerProfile(user, profileData) {
  localStorage.setItem(
    pendingProfileKey(user.email),
    JSON.stringify({
      ownerName: profileData.ownerName.trim(),
      businessName: profileData.businessName.trim(),
      email: user.email ?? "",
    }),
  );
}


export function clearPendingSellerProfile(user) {
  if (user?.email) localStorage.removeItem(pendingProfileKey(user.email));
}
