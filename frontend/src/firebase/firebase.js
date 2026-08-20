// Firebase application setup.
import { initializeApp } from "firebase/app";

// Firebase Authentication tools.
import {
  getAuth,
  GoogleAuthProvider,
} from "firebase/auth";

// Read Firebase settings from .env.local.
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId:
    import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

// Initialize the Firebase application.
const firebaseApp = initializeApp(firebaseConfig);

// Initialize Firebase Authentication.
const auth = getAuth(firebaseApp);

// Configure the Google login provider.
const googleProvider = new GoogleAuthProvider();

googleProvider.setCustomParameters({
  prompt: "select_account",
});

// Export these objects so authentication components can use them.
export {
  firebaseApp,
  auth,
  googleProvider,
};
