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
    console.log("get access")
    return this.accessToken;
  }

  public getRefreshToken(): string | null {
    console.log("get refresh")
    return this.refreshToken;
  }

  public getExpiresAtTimestamp(): string | null {
    console.log("get expiry")
    return localStorage.getItem("gh_token_expires_at");
  }

  public isNearingExpiration(): boolean {
    console.log("expiry not working")
    const standardIsoStr = this.getExpiresAtTimestamp();
    const expiresAtStr = standardIsoStr.replace(/(\.\d{3})\d+/, '$1');

    console.log("hero",expiresAtStr)
    if (!expiresAtStr) return false;

    const expiryTime = new Date(expiresAtStr).getTime();
    const currentTime = Date.now();
    console.log("jesus must be seen")

    // Calculate how many milliseconds are left until total expiration
    const timeLeft = expiryTime - currentTime;
    console.log("time left",timeLeft)
    
    // 1 Hour in milliseconds = 3,600,000 ms
    // If less than 1 hour remains (meaning user has been active for ~7 hours), return true
    return timeLeft > 0 && timeLeft <= 100000;
  }
}

export const tokenStore = new TokenStore();
