// useAutonomicTokenRefresh.ts
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { tokenStore } from "@/services/auth/tokenStore";

export const useAutonomicTokenRefresh = () => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;
  const navigate = useNavigate();

  useEffect(() => {
    const performBackgroundLifespanScrape = async () => {
      // 1. Check if the token needs refreshing
      console.log("checking token lifespan in background...", !tokenStore.isNearingExpiration(), tokenStore.isNearingExpiration());
      if (tokenStore.isNearingExpiration() === false) {
        console.log("💤 Background check: Token lifecycle healthy. Going back to sleep.");
        return;
      }

      console.warn("🔄 Token has passed its active boundary threshold. Spinning up flight rotation...");

      try {
        const response = await fetch(`${backendUrl}/account/api/auth/token/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}), 
          credentials: "include" // Automatically transmits your HttpOnly refresh_token cookie
        });

        if (response.ok) {
          const data = await response.json();
          console.log("📥 Raw refresh data payload received from Django:", data);

          // ✅ FIX: SimpleJWT outputs 'access' and 'refresh'. 
          // Match your calculated timestamp strategy to whatever key handles your absolute expiration date string
          const freshAccess = data.access;
          const freshRefresh = data.refresh || "";
          
          // Fallback timestamp generation if your refresh view doesn't explicitly return an 'expiresAt' field
          const futureTimestamp = data.expires_at || new Date(Date.now() + 15 * 60 * 1000).toISOString();

          if (freshAccess && freshRefresh) {
            tokenStore.setTokens(freshAccess, freshRefresh, futureTimestamp);
            console.log("✅ Proactive local token rotation executed successfully in memory store.");
          } else {
            console.error("⚠️ Response ok, but 'access' token string was missing from data map payload.");
          }
        } else {
          console.error(`❌ Refresh flight aborted by Django backend server. Status: ${response.status}`);
          if (response.status === 401 || response.status === 403) {
            tokenStore.clear();
            navigate("/login", { replace: true });
          }
        }
      } catch (err) {
        console.error("🚨 Background proactive rotation flight failed:", err);
      }
    };

    // Run the check once immediately on mounting the layout view
    performBackgroundLifespanScrape();

    // ✅ FIX: Reduced from 30 minutes (1,800,000ms) down to 2 minutes (120,000ms) for high-speed testing loops
    const testIntervalMs = 120000; 
    const intervalId = setInterval(performBackgroundLifespanScrape, testIntervalMs);

    return () => clearInterval(intervalId); // Clean up active timers cleanly on component unmount
  }, [backendUrl, navigate]);
};
