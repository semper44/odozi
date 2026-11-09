// src/app/router/index.tsx

import { createBrowserRouter, redirect, useRouteError, isRouteErrorResponse } from "react-router-dom";

import Home from "@/pages/Home";
import {GitHubLoginOrRegister} from "@/pages/registrationorlogin";
const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

function RouteErrorBoundary() {
  const error = useRouteError();
  console.error("Route error:", error);

  let errorMessage = "An unexpected error occurred.";
  let statusText = "Application Error";

  if (isRouteErrorResponse(error)) {
    errorMessage = (typeof error.data === "string" ? error.data : error.statusText) || "An error occurred";
    statusText = `${error.status} ${error.statusText || ""}`;
  } else if (error instanceof Error) {
    errorMessage = error.message;
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
      <div className="max-w-md w-full bg-gray-800 rounded-xl p-6 shadow-xl border border-gray-700 text-center">
        <h1 className="text-2xl font-bold text-red-400 mb-2">{statusText}</h1>
        <p className="text-gray-300 mb-6">{errorMessage}</p>
        <button
          onClick={() => (window.location.href = "/login")}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition cursor-pointer"
        >
          Go to Login
        </button>
      </div>
    </div>
  );
}

/**
 * The dashboard endpoint is already the backend's session validator.  Running
 * it before mounting the dashboard prevents protected UI from flashing for an
 * anonymous or expired browser session.
 */
const requireAuthenticatedSession = async () => {
  try {
    const response = await fetch(`${backendUrl}/dashboard/`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    });
    console.log("response", response);
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
  } catch (error) {
    if (error instanceof Response) {
      throw error;
    }
    console.error("Session verification failed:", error);
    throw redirect("/login");
  }
};

export const router = createBrowserRouter([
  {
    path: "/",
    element: <Home />,
    loader: requireAuthenticatedSession,
    errorElement: <RouteErrorBoundary />,
  },
  {
    path: "/login",
    element: <GitHubLoginOrRegister />,
  },
 
]);
