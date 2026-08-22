import { Component, OnInit, inject } from '@angular/core';

import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { DashboardLayoutComponent } from './dashboard-layout.component';
import { TypographyComponent } from '../shared/ui/typography.component';
import { ErrorDisplayComponent } from '../shared/ui/error-display.component';
import { TeamOverviewWidgetComponent, TeamOverviewData, TeamAthleteStat } from '../shared/widgets/team-overview/team-overview-widget.component';
import {
  FigureHeatmapWidgetComponent,
  FigureHeatmapData,
} from '../shared/widgets/figure-heatmap/figure-heatmap-widget.component';
import { PredictionWidgetComponent } from '../shared/widgets/prediction/prediction-widget.component';
import { AIRecommendationWidgetComponent } from '../shared/widgets/ai-recommendation/ai-recommendation-widget.component';
import { environment } from '../../environments/environment';

interface DashboardResponse {
  role: string;
  club_id: string;
  widgets: {
    team_overview?: TeamOverviewData;
  };
}

/**
 * Coach dashboard: assembles the US1 widgets (team overview, figure weakness
 * heatmap, prediction, AI recommendation) with role-based data loading.
 */
@Component({
  selector: 'app-coach-dashboard',
  standalone: true,
  imports: [
    DashboardLayoutComponent,
    TypographyComponent,
    ErrorDisplayComponent,
    TeamOverviewWidgetComponent,
    FigureHeatmapWidgetComponent,
    PredictionWidgetComponent,
    AIRecommendationWidgetComponent,
  ],
  template: `
    <div class="coach-dashboard">
      <header class="dashboard-header">
        <app-typography variant="headline-medium" color="on-surface">
          Coach Dashboard
        </app-typography>
        <app-typography variant="body-medium" color="on-surface-variant">
          Team analysis, figure weaknesses, and qualification predictions.
        </app-typography>
      </header>

      @if (loadError) {
        <app-error-display
          title="Dashboard unavailable"
          [message]="loadError"
          [actions]="[retryActions]"
          [fullWidth]="true"
        ></app-error-display>
      } @else {
        <app-dashboard-layout>
          <div class="span-8">
            <app-team-overview-widget
              [overview]="teamOverview"
              [loading]="loading"
              [selectedAthleteId]="selectedAthlete()?.athlete_id ?? null"
              (athleteSelected)="onAthleteSelected($event)"
            ></app-team-overview-widget>
          </div>

          <div class="span-4">
            <app-prediction-widget
              [athleteId]="selectedAthlete()?.athlete_id ?? null"
              [athleteName]="selectedAthlete()?.name ?? null"
            ></app-prediction-widget>
          </div>

          <div class="span-12">
            <app-figure-heatmap-widget
              [heatmap]="heatmap"
              [loading]="loading"
            ></app-figure-heatmap-widget>
          </div>

          <div class="span-6">
            <app-ai-recommendation-widget
              [athleteId]="selectedAthlete()?.athlete_id ?? null"
              [athleteName]="selectedAthlete()?.name ?? null"
            ></app-ai-recommendation-widget>
          </div>
        </app-dashboard-layout>
      }
    </div>
  `,
  styles: [
    `
      .coach-dashboard {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-4);
      }

      .dashboard-header {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-1);
      }

      .coach-dashboard app-dashboard-layout ::ng-deep > div > * {
        height: 100%;
      }
    `,
  ],
})
export class CoachDashboardComponent implements OnInit {
  private http = inject(HttpClient);

  teamOverview: TeamOverviewData | null = null;
  heatmap: FigureHeatmapData | null = null;
  loading = false;
  loadError: string | null = null;
  selected: TeamAthleteStat | null = null;

  retryActions = ErrorDisplayComponent.retryAction(() => void this.load());

  ngOnInit(): void {
    void this.load();
  }

  selectedAthlete(): TeamAthleteStat | null {
    return this.selected;
  }

  onAthleteSelected(athlete: TeamAthleteStat): void {
    this.selected = athlete;
  }

  private async load(): Promise<void> {
    this.loading = true;
    this.loadError = null;
    try {
      const [dashboardRes, heatmapRes] = await Promise.all([
        firstValueFrom(
          this.http.get<DashboardResponse>(`${environment.apiUrl}/api/analytics/dashboard`)
        ),
        firstValueFrom(
          this.http.get<FigureHeatmapData>(`${environment.apiUrl}/api/analytics/team/heatmap`)
        ),
      ]);
      this.teamOverview = dashboardRes.widgets?.team_overview ?? null;
      this.heatmap = heatmapRes;
      if (!this.selected && this.teamOverview?.athletes.length) {
        this.selected = this.teamOverview.athletes[0];
      }
    } catch {
      this.loadError =
        'Could not load dashboard data. Check your connection and try again.';
    } finally {
      this.loading = false;
    }
  }
}
