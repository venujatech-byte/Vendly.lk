// React and router tools used to start the Vendly application.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/inter";
import './index.css'
import App from './App.jsx'
import { AuthProvider } from "./context/AuthContext.jsx";

// Mount the React application inside the <div id="root"> from index.html.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
  <AuthProvider>
    <App />
  </AuthProvider>
</BrowserRouter>
  </StrictMode>,
);
