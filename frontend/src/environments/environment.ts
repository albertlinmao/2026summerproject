export const environment = {
  production: false,
  // NOTE: use 127.0.0.1 explicitly - `localhost` can resolve to ::1, where
  // Supabase's Kong gateway (published on port 8000 by docker-compose) answers
  // every request with 401 {"message": "Unauthorized"}.
  apiUrl: 'http://127.0.0.1:8000/api',
  supabaseUrl: 'http://localhost:54321',
  supabaseAnonKey: 'REPLACE_WITH_LOCAL_SUPABASE_ANON_KEY',
  userServiceUrl: 'http://localhost:8001',
  featureFlags: {
    aiCoach: true,
    videoAnalysis: true,
    routineTimer: true,
    resultsBrowser: true,
  },
};
