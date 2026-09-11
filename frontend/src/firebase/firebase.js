//firestore emulator
import {
  getFirestore,
  connectFirestoreEmulator,
} from "firebase/firestore";
import {
  getStorage,
  connectStorageEmulator,
} from "firebase/storage";
import { getDatabase } from "firebase/database";

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
  databaseURL: import.meta.env.VITE_FIREBASE_DATABASE_URL,
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

// Services
const db = getFirestore(firebaseApp);
const storage = getStorage(firebaseApp);
const rtdb = getDatabase(
  firebaseApp,
  import.meta.env.VITE_FIREBASE_DATABASE_URL || undefined,
);

if (import.meta.env.DEV) {
  connectFirestoreEmulator(db, "127.0.0.1", 8080);
  connectStorageEmulator(storage, "127.0.0.1", 9199);
}

// Export these objects
export {
  firebaseApp,
  auth,
  db,
  storage,
  rtdb,
  googleProvider,
};
