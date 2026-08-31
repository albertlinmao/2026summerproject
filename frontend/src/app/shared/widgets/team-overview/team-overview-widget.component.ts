import { Component, Input, Output, EventEmitter } from '@angular/core';

import { CardComponent } from '../../ui/card.component';
import { TypographyComponent } from '../../ui/typography.component';
import { LoadingSpinnerComponent } from '../../ui/loading-spinner.component';

export interface TeamAthleteStat {
  athlete_id: string;
  name: string;
  avg_figure_score: number | null;
  avg_routine_score: number | null;
  improvement_trend: number | null;
  at_risk: boolean;
  records_count: number;
}

export interface TeamOverviewData {
  club_id: string;
  athletes: TeamAthleteStat[];
  most_improved: TeamAthleteStat | null;
  at_risk: TeamAthleteStat[];
}

/**
 * Team overview widget: team athletes list with most improved and at-risk
 * swimmers. Scores use display-large tabular-nums typography (DR-005).
 */
@Component({
  selector: 'app-team-overview-widget',
  standalone: true,
  imports: [CardComponent, TypographyComponent, LoadingSpinnerComponent],
  template: `
    <app-card title="Team Overview" subtitle="Athletes, most improved, and at-risk">
      @if (loading) {
        <app-loading-spinner label="Loading team overview"></app-loading-spinner>
      } @else if (!overview) {
        <span>{{ overview }} overview</span>
        <app-typography variant="body-medium" color="on-surface-variant">
          No team data available.
        </app-typography>
      } @else {
        <span>{{ overview.athletes.length }} athletes</span>
        <ul class="athlete-list" aria-label="Team athletes">
          @for (athlete of overview.athletes; track athlete.athlete_id) {
            <li>
              <button
                type="button"
                class="athlete-row"
                [class.selected]="athlete.athlete_id === selectedAthleteId"
                (click)="selectAthlete(athlete)"
              >
                <span class="athlete-name">{{ athlete.name }}</span>
                <span class="athlete-scores">
                  <span class="score-block">
                    <app-typography variant="label-small" color="on-surface-variant"
                      >Figures</app-typography
                    >
                    <app-typography
                      variant="display-small"
                      color="primary"
                      [tabularNums]="true"
                      class="score-value"
                    >
                      {{ athlete.avg_figure_score ?? '—' }}
                    </app-typography>
                  </span>
                  <span class="score-block">
                    <app-typography variant="label-small" color="on-surface-variant"
                      >Routines</app-typography
                    >
                    <app-typography
                      variant="display-small"
                      color="primary"
                      [tabularNums]="true"
                      class="score-value"
                    >
                      {{ athlete.avg_routine_score ?? '—' }}
                    </app-typography>
                  </span>
                </span>
                @if (athlete.at_risk) {
                  <span class="badge badge-risk">At risk</span>
                }
                @if (overview.most_improved?.athlete_id === athlete.athlete_id) {
                  <span class="badge badge-improved">Most improved</span>
                }
              </button>
            </li>
          } @empty {
            <li>
              <app-typography variant="body-medium" color="on-surface-variant">
                No athletes found for your club.
              </app-typography>
            </li>
          }
        </ul>
      }
    </app-card>
  `,
  styles: [
    `
      .athlete-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-2);
      }

      .athlete-row {
        display: flex;
        align-items: center;
        gap: var(--md-sys-spacing-3);
        width: 100%;
        padding: var(--md-sys-spacing-3);
        background: transparent;
        border: 1px solid var(--md-sys-color-outline-variant);
        border-radius: var(--md-sys-corner-medium);
        color: var(--md-sys-color-on-surface);
        cursor: pointer;
        text-align: left;
        min-height: 56px;
      }

      .athlete-row:hover {
        background: var(--md-sys-color-surface-variant);
      }

      .athlete-row.selected {
        border-color: var(--md-sys-color-primary);
        outline: 1px solid var(--md-sys-color-primary);
      }

      .athlete-row:focus-visible {
        outline: 2px solid var(--md-sys-color-primary);
        outline-offset: 2px;
      }

      .athlete-name {
        flex: 1;
        font-weight: 500;
      }

      .athlete-scores {
        display: flex;
        gap: var(--md-sys-spacing-4);
      }

      .score-block {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
      }

      /* Deck-readable scores per DR-005 */
      .score-value {
        font-size: clamp(1.75rem, 4vw, 2.5rem);
        line-height: 1.1;
      }

      .badge {
        padding: 0.125rem 0.5rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
      }

      .badge-risk {
        background: var(--md-sys-color-error-container);
        color: var(--md-sys-color-on-error-container);
      }

      .badge-improved {
        background: var(--md-sys-color-primary-container);
        color: var(--md-sys-color-on-primary-container);
      }
    `,
  ],
})
export class TeamOverviewWidgetComponent {
  @Input() overview: TeamOverviewData | null = null;
  @Input() loading = false;
  @Input() selectedAthleteId: string | null = null;
  @Output() athleteSelected = new EventEmitter<TeamAthleteStat>();

  selectAthlete(athlete: TeamAthleteStat): void {
    this.athleteSelected.emit(athlete);
  }
}
