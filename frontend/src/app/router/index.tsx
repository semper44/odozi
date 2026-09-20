// src/app/router/index.tsx

import { createBrowserRouter, redirect } from "react-router-dom";

import Home from "@/pages/Home";
import {GitHubLoginOrRegister} from "@/pages/registrationorlogin";

const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

/**
 * The dashboard endpoint is already the backend's session validator.  Running
 * it before mounting the dashboard prevents protected UI from flashing for an
 * anonymous or expired browser session.
 */
const requireAuthenticatedSession = async () => {
  const response = await fetch(`${backendUrl}/dashboard/`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });
  console.log("response", response)
  if (response.status === 401 || response.status === 403) {
    throw redirect("/login");
  }

  // making sure to redirect only for a auth error
  if (!response.ok) {
    throw new Response("Unable to verify the current session.", {
      status: response.status,
    });
  }

  return null;
};

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
    loader: requireAuthenticatedSession,
  },
  {
    path: "/login",
    element: <GitHubLoginOrRegister />,
  },
 
]);
