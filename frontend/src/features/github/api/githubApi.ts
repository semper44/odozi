export const fetchRepos = async () => {
  const backendUrl = import.meta.env.VITE_DJANGO_BACKEND_URL;

  const response = await fetch(`${backendUrl}/dashboard/`, {
    method: "POST",
    credentials: "include", 
    headers: {
      "Content-Type": "application/json",
    },
  });

  // ✅ 1. Check if the response failed (any status outside 200-299)
  if (!response.ok) {
    let errorDetails = "Unknown API Error";
    try {
      // Try to extract Django's explicit JsonResponse message (e.g. {"error": "..."})
      const errorJson = await response.json();
      errorDetails = errorJson.error || errorDetails;
    } catch {
      errorDetails = response.statusText;
    }

    // ✅ 2. Create a custom error object and attach the exact HTTP status code
    const apiError = new Error(errorDetails);
    (apiError as any).status = response.status; // Carries 401, 403, 500 etc.
    
    // ✅ 3. Throwing here ensures your hook's "error" object is populated
    throw apiError; 
  }

  // Only reaches here if response.ok is true
  return response.json();
};
