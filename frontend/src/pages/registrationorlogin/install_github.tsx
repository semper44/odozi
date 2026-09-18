import React from "react";

interface GitHubInstallationProps {
  className?: string;
  isOpen?: boolean;
  onClose?: () => void;
}

export const GitHubInstallation: React.FC<GitHubInstallationProps> = ({
  className,
  isOpen = false,
  onClose,
}) => {
  const handleInstallation = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();

    const appSlug = "odozy-ci-agent";
    const githubAppInstallUrl =`https://github.com/apps/${appSlug}/installations/new`;
    console.log("✈️ Redirecting browser frame directly to App Setup Canvas:", githubAppInstallUrl);

    if (onClose) {
      onClose();
    }

    window.location.href = githubAppInstallUrl;
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Install GitHub App</h2>
            <p className="mt-2 text-sm text-gray-600">
              Connect the GitHub App to enable repository actions and automation from your dashboard.
            </p>
          </div>
          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="text-gray-500 transition-colors hover:text-gray-700"
              aria-label="Close"
            >
              ×
            </button>
          )}
        </div>

        <div className="mt-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 cursor-pointer"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleInstallation}
            className={className || "rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-green-700 cursor-pointer"}
          >
            Install GitHub App
          </button>
        </div>
      </div>
    </div>
  );
};
