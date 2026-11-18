import {
  useEffect,
  useRef,
  useState,
} from "react";

import { onAuthStateChanged } from "firebase/auth";

import { auth } from "../firebase/firebase";
import { getCurrentAccount } from "../services/accountService";
import { createBusiness } from "../services/businessService";
import { invalidateReadCache } from "../services/readCache";
import {
  clearPendingSellerProfile,
  getSellerProfile,
} from "../services/sellerService";
import { AuthContext } from "./authContextValue";

function isUserEmailVerified(firebaseUser) {
  if (!firebaseUser) return false;
  if (firebaseUser.isAnonymous) return true;
  const isPasswordUser = firebaseUser.providerData?.some(
    (p) => p.providerId === "password"
  );
  if (isPasswordUser) {
    return Boolean(firebaseUser.emailVerified);
  }
  return true;
}

function AuthProvider({ children }) {
  // Invalidate outstanding account loads whenever the Firebase session changes.
  const authVersion = useRef(0);
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

  async function loadAccount(currentUser, version) {
    const isCurrentSession = () => authVersion.current === version && auth.currentUser?.uid === currentUser.uid;
    let legacyProfile = await getSellerProfile(currentUser);
    if (!isCurrentSession()) return;

    try {
      let currentAccount = await getCurrentAccount();
      if (!isCurrentSession()) return;

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

        if (!isCurrentSession()) return;
        currentAccount = await getCurrentAccount();
        if (!isCurrentSession()) return;
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
      if (!isCurrentSession()) return;
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
        const version = ++authVersion.current;
        // Clear the previous session's cached and pending business reads before exposing this identity.
        invalidateReadCache("");
        setIsAuthLoading(true);
        setAuthenticationError(null);
        setAccount(null);
        setSellerProfile(null);
        setAccountError(null);

        // Do not treat unverified email/password accounts as logged in.
        // This prevents login gates from unmounting or prematurely redirecting.
        if (currentUser && !isUserEmailVerified(currentUser)) {
          setUser(null);
          setIsAuthLoading(false);
          return;
        }

        setUser(currentUser);

        try {
          if (currentUser) {
            await loadAccount(currentUser, version);
          }
        } catch (error) {
          if (authVersion.current !== version) return;
          console.error("Seller profile could not be loaded:", error);
          setSellerProfile(null);
        } finally {
          if (authVersion.current === version) setIsAuthLoading(false);
        }
      },
      (error) => {
        authVersion.current += 1;
        // An authentication failure must also discard any previously authenticated read cache.
        invalidateReadCache("");
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
    return () => {
      authVersion.current += 1;
      unsubscribe();
    };
  }, []);

  // Refresh profile data after the seller finishes business setup.
  async function refreshSellerProfile() {
    const version = authVersion.current;
    // A refreshed membership must not reuse reads made under its previous access rights.
    invalidateReadCache("");
    setIsAuthLoading(true);

    if (!auth.currentUser || !isUserEmailVerified(auth.currentUser)) {
      setSellerProfile(null);
      setAccount(null);
      setIsAuthLoading(false);
      return;
    }

    try {
      await loadAccount(auth.currentUser, version);
    } finally {
      if (authVersion.current === version) setIsAuthLoading(false);
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
