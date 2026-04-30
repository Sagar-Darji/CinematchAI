> **Problem:** Login requests were failing with browser `Failed to fetch` when `VITE_API_URL` was set but unreachable/misconfigured, blocking authentication.
> **Solution:** Updated frontend auth API calls to normalize `VITE_API_URL` and retry auth requests through same-origin `/api/v1/auth/*` as a fallback before surfacing network errors.
