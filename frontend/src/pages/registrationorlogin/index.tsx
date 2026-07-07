import React from "react";

const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export const GitHubLoginOrRegister = () => {
  const handleLogin = () => {

window.location.href =
      `${backendUrl}/account/api/auth/login/`;
  };

  return (
    <button onClick={handleLogin} className="px-4 py-2 bg-green-500 text-white font-medium rounded-md hover:bg-green-800 transition-colors cursor-pointer">
      Login with GitHub
    </button>
  );
};