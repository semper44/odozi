// tokenStore.ts

class TokenStore {
  private accessToken: string | null = null;
  private refreshToken: string | null = null;

  
  public setTokens(access: string, refresh: string, expiresAtIso: string) {
    this.accessToken = access;
    this.refreshToken = refresh;
    
    // Save only the expiry string to local storage to survive browser reloads
    localStorage.setItem("gh_token_expires_at", expiresAtIso);
    
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
  public getJWTTimestamp(): string | null {
    console.log("get jwt_token_expires_at expiry")
    const jwt_token_store = localStorage.getItem("jwt_token_expires_at");
    return jwt_token_store ? JSON.parse(jwt_token_store).token : null;
  }

  public isNearingExpiration(): boolean {
    console.log("expiry not working")
    const standardIsoStr = this.getExpiresAtTimestamp();
    const jwtstandardIsoStr = this.getJWTTimestamp();
    const expiresAtStr = standardIsoStr ? standardIsoStr.replace(/(\.\d{3})\d+/, '$1') : null;

    console.log(expiresAtStr,"hero",jwtstandardIsoStr)
    if (!expiresAtStr || !jwtstandardIsoStr) return false;

    const currentTime = Date.now();
    console.log("jesus must be seen")

    // Calculate how many milliseconds are left until total expiration
    const timeLeft = Number(jwtstandardIsoStr) - currentTime;
    console.log("time left", timeLeft)
    console.log("time left2", timeLeft <= 100000)
    
    // 1 Hour in milliseconds = 3,600,000 ms
    // If less than 1 hour remains (meaning user has been active for ~7 hours), return true
    // return timeLeft > 0 && timeLeft <= 100000;
    return true;
  }
}

export const tokenStore = new TokenStore();
