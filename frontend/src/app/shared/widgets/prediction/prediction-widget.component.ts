import { Component, Input, OnChanges, SimpleChanges, inject } from '@angular/core';

import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

import { CardComponent } from '../../ui/card.component';
import { TypographyComponent } from '../../ui/typography.component';
import { LoadingSpinnerComponent } from '../../ui/loading-spinner.component';
import { ErrorDisplayComponent } from '../../ui/error-display.component';
import { environment } from '../../../../environments/environment';

export interface PredictionInsight {
  athlete_id: string;
  next_score_prediction: number;
  plateau_risk: boolean;
  confidence_interval: number;
}

/**
 * Prediction widget: next score forecast, plateau risk, and qualification
 * probability for the selected athlete. Scores use display-large
 * tabular-nums typography (DR-005).
 */
@Component({
  selector: 'app-prediction-widget',
  standalone: true,
  imports: [
    CardComponent,
    TypographyComponent,
    LoadingSpinnerComponent,
    ErrorDisplayComponent,
  ],
  template: `
    <app-card title="Qualification Prediction" [subtitle]="subtitle()">
      @if (!athleteId) {
        <app-typography variant="body-medium" color="on-surface-variant">
          Select an athlete to view their prediction.
        </app-typography>
      } @else if (loading) {
        <app-loading-spinner label="Loading prediction"></app-loading-spinner>
      } @else if (error) {
        <app-error-display
          title="Prediction unavailable"
          [message]="error"
          [actions]="[retryActions]"
        ></app-error-display>
      } @else if (insight) {
        <div class="prediction-body">
          <div class="primary-metric">
            <app-typography variant="label-large" color="on-surface-variant">
              Next score forecast
            </app-typography>
            <app-typography
              variant="display-large"
              color="primary"
              [tabularNums]="true"
              class="deck-score"
            >
              {{ insight.next_score_prediction }}
            </app-typography>
            <app-typography variant="body-small" color="on-surface-variant" [tabularNums]="true">
              ± {{ insight.confidence_interval }} (95% CI)
            </app-typography>
          </div>

          <dl class="metric-row">
            <div class="metric">
              <dt>Plateau risk</dt>
              <dd>
                <span class="badge" [class.badge-risk]="insight.plateau_risk">
                  {{ insight.plateau_risk ? 'Elevated' : 'Low' }}
                </span>
              </dd>
            </div>
            <div class="metric">
              <dt>Qualification probability</dt>
              <dd>
                <app-typography variant="title-large" color="on-surface" [tabularNums]="true">
                  {{ qualificationProbability() }}%
                </app-typography>
              </dd>
            </div>
          </dl>
        </div>
      }
    </app-card>
  `,
  styles: [
    `
      .prediction-body {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-4);
      }

      .primary-metric {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-1);
      }

      /* Deck-readable forecast per DR-005 */
      .deck-score {
        font-size: clamp(3rem, 8vw, 4.5rem);
        line-height: 1.05;
      }

      .metric-row {
        display: flex;
        gap: var(--md-sys-spacing-6);
        margin: 0;
      }

      .metric dt {
        font-size: var(--md-sys-label-medium-size);
        color: var(--md-sys-color-on-surface-variant);
        margin-bottom: var(--md-sys-spacing-1);
      }

      .metric dd {
        margin: 0;
      }

      .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 999px;
        font-weight: 600;
        background: var(--md-sys-color-primary-container);
        color: var(--md-sys-color-on-primary-container);
      }

      .badge-risk {
        background: var(--md-sys-color-error-container);
        color: var(--md-sys-color-on-error-container);
      }
    `,
  ],
})
export class PredictionWidgetComponent implements OnChanges {
  @Input() athleteId: string | null = null;
  @Input() athleteName: string | null = null;

  insight: PredictionInsight | null = null;
  loading = false;
  error: string | null = null;

  retryActions = ErrorDisplayComponent.retryAction(() => this.load());

  private http = inject(HttpClient);

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['athleteId'] && this.athleteId) {
      void this.load();
    }
  }

  subtitle(): string {
    return this.athleteName ? `Forecast for ${this.athleteName}` : 'Select an athlete';
  }

  qualificationProbability(): number {
    if (!this.insight) {
      return 0;
    }
    // Heuristic: prediction relative to a typical qualification band.
    const { next_score_prediction: p, confidence_interval: ci } = this.insight;
    const target = 70; // baseline qualification threshold
    const z = (p - target) / Math.max(ci, 0.5);
    const prob = 1 / (1 + Math.exp(-z));
    return Math.round(prob * 100);
  }

  private async load(): Promise<void> {
    if (!this.athleteId) {
      return;
    }
    this.loading = true;
    this.error = null;
    try {
      const res = await firstValueFrom(
        this.http.get<PredictionInsight>(
          `${environment.apiUrl}/api/analytics/athletes/${this.athleteId}/prediction`
        )
      );
      this.insight = res;
    } catch {
      this.error = 'Could not load the prediction. Please try again.';
      this.insight = null;
    } finally {
      this.loading = false;
    }
  }
}
