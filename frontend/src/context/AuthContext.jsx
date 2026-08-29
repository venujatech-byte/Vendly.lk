import {
  useEffect,
  useState,
} from "react";

import { onAuthStateChanged } from "firebase/auth";

import { auth } from "../firebase/firebase";
import { getCurrentAccount } from "../services/accountService";
import { createBusiness } from "../services/businessService";
import {
  clearPendingSellerProfile,
  getSellerProfile,
} from "../services/sellerService";
import { AuthContext } from "./authContextValue";

function AuthProvider({ children }) {
  // Firebase user currently logged into Vendly.
  const [user, setUser] = useState(null);

  // Vendly-specific details stored separately from the Firebase user.
  const [sellerProfile, setSellerProfile] = useState(null);

  // Account data returned by Flask: user profile, business and membership.
  const [account, setAccount] = useState(null);

  // A backend error does not destroy the Firebase login session.
  const [accountError, setAccountError] = useState(null);

  // Firebase listener failures are separate from backend account failures.
  const [authenticationError, setAuthenticationError] = useState(null);

  // Prevent pages from loading before Firebase checks the session.
  const [isAuthLoading, setIsAuthLoading] = useState(true);

  async function loadAccount(currentUser) {
    let legacyProfile = await getSellerProfile(currentUser);

    try {
      let currentAccount = await getCurrentAccount();

      if (
        !legacyProfile &&
        currentAccount.profile?.businessName &&
        !currentAccount.business
      ) {
        legacyProfile = {
          ownerName: currentAccount.profile.ownerName,
          businessName: currentAccount.profile.businessName,
        };
      }

      // Upgrade profiles created by the earlier direct-Firestore onboarding.
      if (!currentAccount.business && legacyProfile) {
        await createBusiness({
          ownerName:
            legacyProfile.ownerName ??
            currentUser.displayName ??
            "Business owner",
          businessName: legacyProfile.businessName,
        });

        currentAccount = await getCurrentAccount();
      }

      setAccount(currentAccount);
      setAccountError(null);

      if (currentAccount.business) {
        clearPendingSellerProfile(currentUser);
        setSellerProfile({
          ...legacyProfile,
          ownerName:
            currentAccount.profile?.displayName ??
            legacyProfile?.ownerName ??
            currentUser.displayName ??
            "",
          businessName: currentAccount.business.name,
        });
        return;
      }
    } catch (error) {
      console.error("Vendly account could not be loaded:", error);
      setAccount(null);
      setAccountError(error);
    }

    // Compatibility fallback while an older account is being migrated.
    setSellerProfile(legacyProfile);
  }

  useEffect(() => {
    // Firebase calls this whenever the login session changes.
    const unsubscribe = onAuthStateChanged(
      auth,
      async (currentUser) => {
        setIsAuthLoading(true);
        setAuthenticationError(null);
        setUser(currentUser);

        try {
          if (currentUser) {
            await loadAccount(currentUser);
          } else {
            setSellerProfile(null);
            setAccount(null);
            setAccountError(null);
          }
        } catch (error) {
          console.error("Seller profile could not be loaded:", error);
          setSellerProfile(null);
        } finally {
          setIsAuthLoading(false);
        }
      },
      (error) => {
        console.error("Firebase authentication could not be initialized:", error);
        setUser(null);
        setSellerProfile(null);
        setAccount(null);
        setAccountError(null);
        setAuthenticationError(error);
        setIsAuthLoading(false);
      },
    );

    // Stop the Firebase listener when this component is removed.
    return unsubscribe;
  }, []);

  // Refresh profile data after the seller finishes business setup.
  async function refreshSellerProfile() {
    setIsAuthLoading(true);

    if (!auth.currentUser) {
      setSellerProfile(null);
      setAccount(null);
      setIsAuthLoading(false);
      return;
    }

    try {
      await loadAccount(auth.currentUser);
    } finally {
      setIsAuthLoading(false);
    }
  }

  const authValue = {
    user,
    sellerProfile,
    account,
    business: account?.business ?? null,
    membership: account?.membership ?? null,
    accountError,
    authenticationError,
    refreshSellerProfile,
    isAuthLoading,
    isAuthenticated: Boolean(user),
  };

  return (
    <AuthContext.Provider value={authValue}>
      {children}
    </AuthContext.Provider>
  );
}

export { AuthProvider };
