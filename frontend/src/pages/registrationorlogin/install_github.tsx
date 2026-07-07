import React from "react";

interface GitHubLoginOrRegisterProps {
  className?: string;
}
const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

export const GitHubLoginOrRegister: React.FC<GitHubLoginOrRegisterProps> = ({ className }) => {
  
const handleGitHubLogin = (e: React.MouseEvent<HTMLButtonElement>) => {
  e.preventDefault();

  // 🚀 THE APP INSTALLATION FLOW FIX: Use your unique GitHub App slug/name
  const appSlug = "odozy-ci-agent"; 
  
  // Optional query param: lets GitHub know where to send the user after a successful setup
  const redirectUri = `${backendUrl}/account/api/auth/github/callback/`;

  // Construct the explicit GitHub App Installation Link
  const githubAppInstallUrl =
  `https://github.com/apps/${appSlug}/installations/new?redirect_url=${encodeURIComponent(redirectUri)}`;
  console.log("✈️ Redirecting browser frame directly to App Setup Canvas:", githubAppInstallUrl);

  // Force the tab to navigate to the installation screen
  window.location.href = githubAppInstallUrl;
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
