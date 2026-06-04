import React from "react";

interface GitHubLoginOrRegisterProps {
  className?: string;
}
const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export const GitHubLoginOrRegister: React.FC<GitHubLoginOrRegisterProps> = ({ className }) => {
  
  const handleGitHubLogin = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();

    // 1. Define OAuth Core credentials (Pulled from configuration environment variables)
    const clientId = "Iv23liUEbKH7D09scRIZ";
    
    // 2. The callback route handled by your Django backend
    const redirectUri = `${backendUrl}/account/api/auth/github/callback/`;
    
    // 3. Expanded access parameters required to manage workflows and parse logs
    const scope = "repo workflow user:email";

    // 4. Safely encode URL segments to construct a valid OAuth gateway handshake string
    const githubAuthUrl = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${encodeURIComponent(
      redirectUri
    )}&scope=${encodeURIComponent(scope)}`;

    console.log("✈️ Redirecting browser frame directly to GitHub Gateway:", githubAuthUrl);

    // 5. Force the active tab session to travel down the GitHub OAuth pipeline
    window.location.href = githubAuthUrl;
  };

  return (
    <button
      onClick={handleGitHubLogin}
      className={className || "px-4 py-2 bg-green-500 text-white font-medium rounded-md hover:bg-green-800 transition-colors"}
    >
      Register / Login with GitHub
    </button>
  );
};
