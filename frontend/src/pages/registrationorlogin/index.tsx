import React from "react";

const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export const GitHubLoginButton = () => {
  const handleLogin = () => {

window.location.href =
  `https://github.com/login/oauth/authorize?client_id=${clientId}`;
    // window.location.href =
    //   `${backendUrl}/account/api/auth/github/login/`;
  };

  return (
    <button onClick={handleLogin}>
      Login with GitHub
    </button>
  );
};