// useAutonomicTokenRefresh.ts
import { useEffect } from "react";
import { tokenStore } from "@/services/auth/tokenStore";

export const useAutonomicTokenRefresh = () => {
  useEffect(() => {
    // 1. Check for tokens in the incoming redirect URL query parameters on boot
    // const urlParams = new URLSearchParams(window.location.search);
    // const access = urlParams.get("access_token");
    // const refresh = urlParams.get("refresh_token");
    // const expiresAt = urlParams.get("expires_at");
    const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;


    // if (access && expiresAt) {
    //   tokenStore.setTokens(access, refresh || "", expiresAt);
    //   // Clean up the address bar completely so tokens are hidden from sight
    //   window.history.replaceState({}, document.title, window.location.pathname);
    // }

    // 2. Core Scraper Task: Processes data completely in the background
    const performBackgroundLifespanScrape = async () => {
      // Condition Evaluation: Checks localized time numbers offline. 
      // If 7 hours haven't passed, execution terminates here (Zero Overhead)
      if (!tokenStore.isNearingExpiration()) {
        console.log("💤 Background check: Token lifecycle healthy. Going back to sleep.");
        return;
      }

      console.warn("🔄 Token has passed the 7-hour active threshold. Spinning up flight rotation...");
      const currentRefresh = tokenStore.getRefreshToken();
      if (!currentRefresh) return;

      try {
        const response = await fetch(`${backendUrl}/account/api/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          // 1. Leave the body empty! Django reads it directly from the cookie
          body: JSON.stringify({}), 
          // 2. CRITICAL: Forwards your secure HttpOnly cookies across origins automatically
          credentials: "include" 
        });

        if (response.ok) {
          const data = await response.json();
          // Update RAM references and write the fresh 8-hour timestamp limit to disk
          tokenStore.setTokens(data.accessToken, data.refreshToken, data.expiresAt);
          console.log("✅ Proactive GitHub token rotation executed successfully in memory.");
        }
      } catch (err) {
        console.error("🚨 Background proactive rotation flight failed:", err);
      }
    };

    // Run the scrape flight once immediately on mounting the dashboard layout
    performBackgroundLifespanScrape();

    // Execute the passive timestamp calculation check every 30 minutes (1,800,000 ms)
    const intervalId = setInterval(performBackgroundLifespanScrape, 1800000);

    return () => clearInterval(intervalId); // Clear background timers clean on unmount
  }, []);
};
