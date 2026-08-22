export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
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
