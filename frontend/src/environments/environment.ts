export const environment = {
  production: false,
  // NOTE: use 127.0.0.1 explicitly - `localhost` can resolve to ::1, where the
  // Supabase stack's Kong gateway answers every request with 401
  // {"message": "Unauthorized"}.
  //
  // apiUrl is the FastAPI backend, NOT Kong. Kong owns host port 8000, so a
  // local backend run must use a different port (see IMPLEMENTATION_SUMMARY.md
  // step 3); the compose path publishes the backend on 18081 instead.
  apiUrl: 'http://127.0.0.1:8080/api',
  // Kong, the Supabase stack's only HTTP entry point (supabase/.env
  // KONG_HTTP_PORT). The Supabase CLI's 54321 is not in use.
  supabaseUrl: 'http://127.0.0.1:8000',
  supabaseAnonKey: 'REPLACE_WITH_LOCAL_SUPABASE_ANON_KEY',
  userServiceUrl: 'http://localhost:8001',
  featureFlags: {
    aiCoach: true,
    videoAnalysis: true,
    routineTimer: true,
    resultsBrowser: true,
  },
};
