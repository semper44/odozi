// tokenStore.ts

class TokenStore {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  public setTokens(access: string, refresh: string, expiresAtIso: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    
    // Save only the expiry string to local storage to survive browser reloads
    localStorage.setItem("gh_token_expires_at", expiresAtIso);
    console.log("🔒 Tokens captured in RAM. Timestamp cached to localStorage.");
  }

  public getAccessToken(): string | null {
    return this.accessToken;
  }

  public getRefreshToken(): string | null {
    return this.refreshToken;
  }

  public getExpiresAtTimestamp(): string | null {
    return localStorage.getItem("gh_token_expires_at");
  }

  public isNearingExpiration(): boolean {
    const expiresAtStr = this.getExpiresAtTimestamp();
    if (!expiresAtStr) return false;

    const expiryTime = new Date(expiresAtStr).getTime();
    const currentTime = Date.now();

    // Calculate how many milliseconds are left until total expiration
    const timeLeft = expiryTime - currentTime;
    
    // 1 Hour in milliseconds = 3,600,000 ms
    // If less than 1 hour remains (meaning user has been active for ~7 hours), return true
    return timeLeft > 0 && timeLeft <= 3600000;
  }
}

export const tokenStore = new TokenStore();
