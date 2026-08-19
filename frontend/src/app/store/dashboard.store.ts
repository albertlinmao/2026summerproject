import { inject } from '@angular/core';
import { signalStore, withState, withMethods, patchState } from '@ngrx/signals';
import { ApiService } from '../shared/api.service';

export interface HeatmapData {
  athlete_id: string;
  figure_weaknesses: Record<string, number>;
  prediction_score: number;
  figure_score: number;
  routine_score: number;
}

export interface PersonalBest {
  figure_name: string;
  score: number;
  date: string;
}

export interface TrendPoint {
  date: string;
  score: number;
}

export interface FigureScore {
  figure_name: string;
  score: number;
  max_score: number;
}

export interface CoachRecommendation {
  recommendation_text: string;
  weakest_figure: string;
}

export interface SwimmerOverviewData {
  personalBests: PersonalBest[];
  currentRanking: number;
  trendData: TrendPoint[];
}

export interface VideoItem {
  id: string;
  storage_path: string;
  filename: string;
  duration_seconds: number;
  uploaded_at: string;
}

export interface TimerConfig {
  id: string;
  label: string;
  duration_seconds: number;
}

export interface DashboardState {
  teamHeatmap: HeatmapData[];
  isLoading: boolean;
  error: string | null;

  swimmerOverview: SwimmerOverviewData;
  radarData: FigureScore[];
  aiRecommendation: CoachRecommendation | null;
  swimmerInsightsLoaded: boolean;

  videoList: VideoItem[];
  timerConfigs: TimerConfig[];
}

const initialState: DashboardState = {
  teamHeatmap: [],
  isLoading: false,
  error: null,

  swimmerOverview: { personalBests: [], currentRanking: 0, trendData: [] },
  radarData: [],
  aiRecommendation: null,
  swimmerInsightsLoaded: false,

  videoList: [],
  timerConfigs: [],
};

export const DashboardStore = signalStore(
  { providedIn: 'root' },
  withState(initialState),
  withMethods((store, apiService = inject(ApiService)) => ({
    async loadDashboard() {
      patchState(store, { isLoading: true });
      try {
        const res = await apiService.get('/analytics/dashboard');
        const data = await res.json();
        patchState(store, {
          teamHeatmap: data.team_heatmap || [],
          isLoading: false,
        });
      } catch (err) {
        patchState(store, {
          isLoading: false,
          error: 'Failed to load dashboard data',
        });
      }
    },

    async loadSwimmerData(athleteId: string) {
      try {
        const res = await apiService.get(`/athletes/${athleteId}/insights`);
        const data = await res.json();

        patchState(store, {
          swimmerOverview: {
            personalBests: data.personal_bests || [],
            currentRanking: data.current_ranking ?? 0,
            trendData: data.trend_data || [],
          },
          radarData: data.figure_scores || [],
          aiRecommendation: data.ai_recommendation ?? null,
          swimmerInsightsLoaded: true,
        });
      } catch (err) {
        patchState(store, {
          aiRecommendation: {
            recommendation_text: 'AI temporarily unavailable',
            weakest_figure: '',
          },
          swimmerInsightsLoaded: true,
        });
      }
    },

    async loadVideoList() {
      try {
        const res = await apiService.get('/videos');
        const data = await res.json();
        patchState(store, { videoList: data.videos || [] });
      } catch (err) {
        patchState(store, { videoList: [] });
      }
    },

    async loadTimerConfigs() {
      try {
        const res = await apiService.get('/timers');
        const data = await res.json();
        patchState(store, { timerConfigs: data.timers || [] });
      } catch (err) {
        patchState(store, { timerConfigs: [] });
      }
    },

    refreshVideoList() {
      return store.loadVideoList();
    },

    refreshTimerConfigs() {
      return store.loadTimerConfigs();
    },
  }))
);
