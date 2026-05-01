> **Problem:** Login requests were failing with browser `Failed to fetch` when `VITE_API_URL` was set but unreachable/misconfigured, blocking authentication.
> **Solution:** Updated frontend auth API calls to normalize `VITE_API_URL` and retry auth requests through same-origin `/api/v1/auth/*` as a fallback before surfacing network errors.
> **Problem:** Safari surfaces fetch network failures as `Load failed`, so auth fallback logic did not trigger and login still failed.
> **Solution:** Expanded frontend network error detection to handle cross-browser messages (`Load failed` and related network variants) so fallback routing and user-facing errors work consistently.
