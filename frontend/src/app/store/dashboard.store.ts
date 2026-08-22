import { signal, computed, effect } from '@angular/core';
import { Injectable } from '@angular/core';

// Widget types
export type WidgetType =
  | 'team-overview'
  | 'figure-heatmap'
  | 'prediction'
  | 'ai-recommendation'
  | 'personal-progress'
  | 'personal-bests'
  | 'club-overview'
  | 'coach-effectiveness'
  | 'athlete-retention'
  | 'video-analysis'
  | 'routine-timer'
  | 'results-browser';

export interface WidgetConfig {
  id: string;
  type: WidgetType;
  title: string;
  position: { x: number; y: number };
  size: { width: number; height: number };
  isVisible: boolean;
  config?: Record<string, any>;
}

export interface UserPreferences {
  themeMode: 'light' | 'dark' | 'system';
  compactMode: boolean;
  autoRefresh: boolean;
  refreshInterval: number;
}

export interface DashboardState {
  widgets: WidgetConfig[];
  activeDashboard: string;
  userPreferences: UserPreferences;
  isLoading: boolean;
  error: string | null;
}

// Initial state
const initialState: DashboardState = {
  widgets: [],
  activeDashboard: 'coach',
  userPreferences: {
    themeMode: 'system',
    compactMode: false,
    autoRefresh: true,
    refreshInterval: 300000, // 5 minutes
  },
  isLoading: false,
  error: null,
};

// Store using Angular Signals
@Injectable({
  providedIn: 'root',
})
export class DashboardStore {
  // Private state signals
  private _widgets = signal<WidgetConfig[]>(initialState.widgets);
  private _activeDashboard = signal<string>(initialState.activeDashboard);
  private _userPreferences = signal<UserPreferences>(initialState.userPreferences);
  private _isLoading = signal<boolean>(initialState.isLoading);
  private _error = signal<string | null>(initialState.error);

  // Public computed selectors
  readonly widgets = computed(() => this._widgets());
  readonly activeDashboard = computed(() => this._activeDashboard());
  readonly userPreferences = computed(() => this._userPreferences());
  readonly isLoading = computed(() => this._isLoading());
  readonly error = computed(() => this._error());

  // Visible widgets for current dashboard
  readonly visibleWidgets = computed(() => this._widgets().filter((w) => w.isVisible));

  // Widgets by type
  readonly widgetsByType = computed(() => {
    const grouped: Record<WidgetType, WidgetConfig[]> = {} as any;
    for (const widget of this._widgets()) {
      if (!grouped[widget.type]) {
        grouped[widget.type] = [];
      }
      grouped[widget.type].push(widget);
    }
    return grouped;
  });

  // Actions
  setWidgets(widgets: WidgetConfig[]): void {
    this._widgets.set(widgets);
  }

  addWidget(widget: WidgetConfig): void {
    this._widgets.update((current) => [...current, widget]);
  }

  removeWidget(widgetId: string): void {
    this._widgets.update((current) => current.filter((w) => w.id !== widgetId));
  }

  updateWidget(widgetId: string, updates: Partial<WidgetConfig>): void {
    this._widgets.update((current) =>
      current.map((w) => (w.id === widgetId ? { ...w, ...updates } : w))
    );
  }

  setActiveDashboard(dashboard: string): void {
    this._activeDashboard.set(dashboard);
  }

  setUserPreferences(preferences: Partial<UserPreferences>): void {
    this._userPreferences.update((current) => ({ ...current, ...preferences }));
  }

  setLoading(isLoading: boolean): void {
    this._isLoading.set(isLoading);
  }

  setError(error: string | null): void {
    this._error.set(error);
  }

  clearError(): void {
    this._error.set(null);
  }

  // Persist user preferences to localStorage
  constructor() {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('dashboard-preferences');
      if (stored) {
        try {
          const prefs = JSON.parse(stored);
          this._userPreferences.set({ ...initialState.userPreferences, ...prefs });
        } catch {
          // Ignore parse errors
        }
      }

      effect(() => {
        const prefs = this._userPreferences();
        localStorage.setItem('dashboard-preferences', JSON.stringify(prefs));
      });
    }
  }
}

// Dashboard-specific stores
@Injectable({
  providedIn: 'root',
})
export class CoachDashboardStore {
  private _teamAthletes = signal<any[]>([]);
  private _heatmapData = signal<any>(null);
  private _predictions = signal<any[]>([]);

  readonly teamAthletes = computed(() => this._teamAthletes());
  readonly heatmapData = computed(() => this._heatmapData());
  readonly predictions = computed(() => this._predictions());

  setTeamAthletes(athletes: any[]): void {
    this._teamAthletes.set(athletes);
  }

  setHeatmapData(data: any): void {
    this._heatmapData.set(data);
  }

  setPredictions(predictions: any[]): void {
    this._predictions.set(predictions);
  }
}

@Injectable({
  providedIn: 'root',
})
export class SwimmerDashboardStore {
  private _progressData = signal<any>(null);
  private _personalBests = signal<any>(null);
  private _recommendation = signal<string | null>(null);

  readonly progressData = computed(() => this._progressData());
  readonly personalBests = computed(() => this._personalBests());
  readonly recommendation = computed(() => this._recommendation());

  setProgressData(data: any): void {
    this._progressData.set(data);
  }

  setPersonalBests(bests: any): void {
    this._personalBests.set(bests);
  }

  setRecommendation(text: string | null): void {
    this._recommendation.set(text);
  }
}

@Injectable({
  providedIn: 'root',
})
export class ClubAdminDashboardStore {
  private _overviewStats = signal<any>(null);
  private _coachEffectiveness = signal<any[]>([]);
  private _retentionData = signal<any>(null);

  readonly overviewStats = computed(() => this._overviewStats());
  readonly coachEffectiveness = computed(() => this._coachEffectiveness());
  readonly retentionData = computed(() => this._retentionData());

  setOverviewStats(stats: any): void {
    this._overviewStats.set(stats);
  }

  setCoachEffectiveness(data: any[]): void {
    this._coachEffectiveness.set(data);
  }

  setRetentionData(data: any): void {
    this._retentionData.set(data);
  }
}
