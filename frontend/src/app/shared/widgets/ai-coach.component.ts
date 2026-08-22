import { Component, Input } from '@angular/core';

interface CoachRecommendation {
  recommendation_text: string;
  weakest_figure: string;
}

@Component({
  selector: 'app-ai-coach',
  standalone: true,
  imports: [],
  template: `
    <div class="card ai-coach" [class.error-state]="isUnavailable">
      <h3 class="heading"><span class="coach-icon">🏊</span> AI Coach</h3>

      @if (isUnavailable) {
        <div class="unavailable-banner">
          <span class="status-dot error"></span>
          <p class="unavailable-text">{{ recommendation?.recommendation_text }}</p>
        </div>
      } @else {
        @if (recommendation) {
          <div class="recommendation-body">
            <p class="recommendation-text">{{ recommendation.recommendation_text }}</p>
            @if (recommendation.weakest_figure) {
              <div class="weakest-highlight">
                <span class="weak-label">Area to Focus</span>
                <span class="weak-figure">{{ recommendation.weakest_figure }}</span>
              </div>
            }
          </div>
        }
      }

      @if (!recommendation) {
        <div class="empty-state">
          <p>No recommendations available.</p>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .ai-coach {
        gap: var(--spacing-md);
        position: relative;
      }
      .heading {
        color: var(--primary-navy);
        margin: 0;
        padding-bottom: var(--spacing-md);
        border-bottom: 2px solid var(--surface-color);
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }
      .coach-icon {
        font-size: 1.4rem;
      }

      .recommendation-body {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }
      .recommendation-text {
        font-family: var(--font-main);
        font-size: 1rem;
        line-height: 1.6;
        color: var(--text-primary);
      }

      .weakest-highlight {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs, 4px);
        background: var(--bg-color);
        border-left: 4px solid var(--accent-gold);
        padding: var(--spacing-sm) var(--spacing-md);
        border-radius: 0 8px 8px 0;
      }
      .weak-label {
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-secondary);
      }
      .weak-figure {
        font-family: var(--font-data);
        font-weight: 700;
        font-size: 1.1rem;
        color: var(--primary-teal);
      }

      /* Error / unavailable state */
      .error-state {
        border-left: 4px solid var(--accent-coral);
      }
      .unavailable-banner {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-md);
        background: rgba(255, 107, 107, 0.08);
        border-radius: 8px;
      }
      .status-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        flex-shrink: 0;
      }
      .status-dot.error {
        background: var(--accent-coral);
      }
      .unavailable-text {
        color: var(--accent-coral);
        font-weight: 500;
        margin: 0;
      }

      .empty-state {
        color: var(--text-secondary);
        font-style: italic;
        text-align: center;
        padding: var(--spacing-md);
      }
    `,
  ],
})
export class AiCoachComponent {
  @Input() recommendation: CoachRecommendation | null = null;

  get isUnavailable(): boolean {
    return (
      !!this.recommendation &&
      this.recommendation.recommendation_text === 'AI temporarily unavailable'
    );
  }
}
