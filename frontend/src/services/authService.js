/// Firebase Authentication functions.
import {
  createUserWithEmailAndPassword,
  deleteUser,
  EmailAuthProvider,
  getIdToken,
  reauthenticateWithCredential,
  reauthenticateWithPopup,
  reload,
  sendEmailVerification,
  sendPasswordResetEmail,
  signInAnonymously,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  updatePassword,
  updateProfile,
  verifyBeforeUpdateEmail,
} from "firebase/auth";

// Firebase objects configured in firebase.js.
import {
  auth,
  googleProvider,
} from "../firebase/firebase";
import { apiRequest } from "./apiClient";

// Register a seller using an email address and password.
export async function registerWithEmail(
  name,
  email,
  password,
) {
  const userCredential =
    await createUserWithEmailAndPassword(
      auth,
      email,
      password,
    );

  // Save the seller's name in their Firebase profile.
  await updateProfile(userCredential.user, {
    displayName: name,
  });

  // Send an email-verification message.
  await sendEmailVerification(userCredential.user);

  return userCredential.user;
}

// Login using email and password.
export async function loginWithEmail(email, password) {
  const userCredential =
    await signInWithEmailAndPassword(
      auth,
      email,
      password,
    );

  const loggedInUser = userCredential.user;

  // Retrieve the latest email-verification status from Firebase.
  await reload(loggedInUser);

  // Email/password accounts must verify their address before continuing.
  if (!loggedInUser.emailVerified) {
    await signOut(auth);

    const verificationError = new Error(
      "Email address has not been verified.",
    );

    verificationError.code = "auth/email-not-verified";

    throw verificationError;
  }

  return loggedInUser;
}

// Login or register using a Google account.
export async function loginWithGoogle() {
  const userCredential = await signInWithPopup(
    auth,
    googleProvider,
  );

  return userCredential.user;
  
}

// Logout the currently authenticated seller.
export async function logoutUser() {
  await signOut(auth);
}

// Generate a token that can be sent to the Flask backend.
export async function getCurrentUserToken(forceRefresh = false) {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    return null;
  }

  return getIdToken(currentUser, forceRefresh);
}

export async function loginAsGuest() {
  try {
    const userCredential = await signInAnonymously(auth);
    return userCredential.user;
  } catch (error) {
    if (error.code === "auth/operation-not-allowed") {
      const providerError = new Error(
        "Guest login is disabled. Enable Anonymous sign-in in Firebase Console > Authentication > Sign-in method.",
      );
      providerError.code = error.code;
      throw providerError;
    }

    throw error;
  }
}

// Return true when the current account can sign in with an email and password.
export function currentUserHasPasswordProvider() {
  return Boolean(
    auth.currentUser?.providerData.some(
      (provider) => provider.providerId === "password",
    ),
  );
}

// Firebase requires a recent login before changing sensitive account details.
async function reauthenticateCurrentUser(currentPassword = "") {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    throw new Error("Please sign in again before changing your profile.");
  }

  if (currentUserHasPasswordProvider()) {
    if (!currentPassword) {
      const passwordError = new Error("Enter your current password to continue.");
      passwordError.code = "auth/current-password-required";
      throw passwordError;
    }

    const credential = EmailAuthProvider.credential(
      currentUser.email,
      currentPassword,
    );
    await reauthenticateWithCredential(currentUser, credential);
    return;
  }

  const usesGoogle = currentUser.providerData.some(
    (provider) => provider.providerId === "google.com",
  );

  if (usesGoogle) {
    await reauthenticateWithPopup(currentUser, googleProvider);
    return;
  }

  const providerError = new Error(
    "This sign-in provider cannot be re-authenticated from this screen.",
  );
  providerError.code = "auth/provider-not-supported";
  throw providerError;
}

// Send verification to the new address. Firebase changes the address only
// after the user opens that verification link.
export async function requestAccountEmailChange(newEmail, currentPassword = "") {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    throw new Error("Please sign in again before changing your email.");
  }

  await reauthenticateCurrentUser(currentPassword);
  await verifyBeforeUpdateEmail(currentUser, newEmail);
}

// Password accounts must prove their current password before setting a new one.
export async function changeAccountPassword(currentPassword, newPassword) {
  const currentUser = auth.currentUser;

  if (!currentUser || !currentUserHasPasswordProvider()) {
    const providerError = new Error(
      "This account uses Google sign-in and does not have a Vendly password.",
    );
    providerError.code = "auth/password-provider-missing";
    throw providerError;
  }

  await reauthenticateCurrentUser(currentPassword);
  await updatePassword(currentUser, newPassword);
}

export async function sendCurrentUserPasswordReset() {
  const currentUser = auth.currentUser;

  if (!currentUser?.email) {
    throw new Error("No email address is available for this account.");
  }

  await sendPasswordResetEmail(auth, currentUser.email);
}

// Send a password reset email to any user by email address (for login / forgot password screen).
export async function sendPasswordReset(email = "") {
  const cleanEmail = email.trim();

  if (!cleanEmail) {
    const error = new Error("Please enter your email address.");
    error.code = "auth/invalid-email";
    throw error;
  }

  await sendPasswordResetEmail(auth, cleanEmail);
}

// Centralized translation of Firebase Authentication error codes to user-friendly messages.
export function getAuthErrorMessage(error) {
  if (!error) return "An unexpected error occurred. Please try again.";

  // Handle both Error object with code property or string containing (auth/...)
  const errorCode =
    error.code ||
    (typeof error.message === "string" && error.message.match(/auth\/[a-z0-9-]+/)?.[0]) ||
    "";

  switch (errorCode) {
    case "auth/email-already-in-use":
      return "An account already exists with this email.";
    case "auth/invalid-email":
      return "Please enter a valid email address.";
    case "auth/invalid-credential":
    case "auth/wrong-password":
      return "The email or password is incorrect.";
    case "auth/user-not-found":
      return "No account found with this email.";
    case "auth/weak-password":
      return "Please use a stronger password (at least 6 characters).";
    case "auth/too-many-requests":
      return "Too many failed attempts. Please wait a moment or reset your password.";
    case "auth/network-request-failed":
      return "Network connection failed. Please check your internet connection.";
    case "auth/popup-closed-by-user":
      return "Sign-in was cancelled.";
    case "auth/popup-blocked":
      return "Pop-up was blocked by your browser. Please allow pop-ups for this site.";
    case "auth/email-not-verified":
      return "Please verify your email address before logging in.";
    case "auth/user-disabled":
      return "This account has been disabled. Please contact support.";
    case "auth/operation-not-allowed":
      return "This sign-in method is currently not enabled.";
    default:
      return (
        error.message?.replace(/^Firebase:\s*(Error\s*)?(\(auth\/[^)]+\)\.?\s*)?/i, "") ||
        "Authentication failed. Please try again."
      );
  }
}

// Permanently delete the user's account after verifying their credentials.
export async function deleteCurrentUserAccount(currentPassword = "") {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    throw new Error("Please sign in again before deleting your account.");
  }

  // Re-authenticate first to verify identity and avoid auth/requires-recent-login
  await reauthenticateCurrentUser(currentPassword);

  // Clean up backend records (user document, business memberships, seller profile)
  try {
    await apiRequest("/me", { method: "DELETE" });
  } catch (backendError) {
    console.warn("Backend account deletion warning:", backendError);
  }

  // Delete from client Firebase Auth
  try {
    await deleteUser(currentUser);
  } catch (error) {
    if (error?.code !== "auth/user-not-found") {
      throw error;
    }
  }

  try {
    await signOut(auth);
  } catch {
    // Ignore signout errors if already cleared
  }
}
