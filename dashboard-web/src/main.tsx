import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.tsx";
import {
  AcceptInvitationPage,
} from "./pages/AcceptInvitationPage";

import "./index.css";
import "./mobile-shell.css";
import "./dashboard-polish.css";
import "./admin-workspace.css";
import "./invitation-onboarding.css";


declare global {
  interface Window {
    __STOREPLUG_INVITATION_TOKEN__?:
      string;
  }
}


const apiBaseUrl =
  import.meta.env.VITE_API_URL ||
  "http://localhost:8000/api/v1";


const normalizedPath =
  window.location.pathname.replace(
    /\/+$/,
    "",
  );


const isInvitationRoute =
  normalizedPath === "/accept-invite";


const invitationToken =
  window.__STOREPLUG_INVITATION_TOKEN__ ??
  null;


delete window.__STOREPLUG_INVITATION_TOKEN__;


const application = isInvitationRoute ? (
  <AcceptInvitationPage
    invitationToken={invitationToken}
    apiBaseUrl={apiBaseUrl}
  />
) : (
  <App />
);


createRoot(
  document.getElementById("root")!,
).render(
  <StrictMode>
    {application}
  </StrictMode>,
);
