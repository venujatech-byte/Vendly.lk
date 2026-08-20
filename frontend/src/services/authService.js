// Firebase Authentication functions.
import {
  createUserWithEmailAndPassword,
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
export async function getCurrentUserToken() {
  const currentUser = auth.currentUser;

  if (!currentUser) {
    return null;
  }

  return getIdToken(currentUser);
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
