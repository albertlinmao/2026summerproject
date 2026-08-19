import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';

interface PersonalBest {
  figure_name: string;
  score: number;
  date: string;
}

interface TrendPoint {
  date: string;
  score: number;
}

@Component({
  selector: 'app-swimmer-overview',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="card swimmer-overview">
      <h3 class="heading">My Progress</h3>

      <div class="ranking-section">
        <span class="ranking-label">Current Ranking</span>
        <span class="score-display ranking-value">{{ currentRanking }}</span>
      </div>

      <div class="section">
        <h4 class="section-title">Personal Bests</h4>
        <ul class="bests-list" *ngIf="personalBests?.length; else noBests">
          <li class="best-item" *ngFor="let pb of personalBests">
            <div class="best-info">
              <span class="figure-name">{{ pb.figure_name }}</span>
              <span class="best-date">{{ pb.date }}</span>
            </div>
            <span class="best-score">{{ pb.score | number:'1.2-2' }}</span>
          </li>
        </ul>
        <ng-template #noBests>
          <p class="empty-state">No personal bests recorded yet.</p>
        </ng-template>
      </div>

      <div class="section" *ngIf="trendData?.length">
        <h4 class="section-title">Score Trend</h4>
        <div class="sparkline">
          <div class="spark-bar"
               *ngFor="let point of trendData; let i = index"
               [style.height.%]="getBarHeight(point.score)"
               [style.background]="i === trendData.length - 1 ? 'var(--primary-teal)' : 'var(--primary-navy)'"
               [title]="point.date + ': ' + (point.score | number:'1.2-2')">
          </div>
        </div>
        <div class="sparkline-labels">
          <span *ngIf="trendData.length > 0">{{ trendData[0].date }}</span>
          <span *ngIf="trendData.length > 1">{{ trendData[trendData.length - 1].date }}</span>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .swimmer-overview {
      gap: var(--spacing-lg);
    }
    .heading {
      color: var(--primary-navy);
      margin: 0;
      padding-bottom: var(--spacing-md);
      border-bottom: 2px solid var(--surface-color);
    }

    .ranking-section {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: var(--spacing-md) 0;
    }
    .ranking-label {
      font-family: var(--font-main);
      font-size: 0.85rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: var(--spacing-sm);
    }
    .ranking-value {
      color: var(--primary-teal);
    }

    .section-title {
      font-size: 0.85rem;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: var(--spacing-sm);
    }

    .bests-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: var(--spacing-sm);
    }
    .best-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: var(--spacing-sm);
      background: var(--bg-color);
      border-radius: 8px;
    }
    .best-info {
      display: flex;
      flex-direction: column;
    }
    .figure-name {
      font-weight: 500;
      color: var(--text-primary);
    }
    .best-date {
      font-size: 0.75rem;
      color: var(--text-secondary);
    }
    .best-score {
      font-family: var(--font-data);
      font-weight: 700;
      font-size: 1.1rem;
      color: var(--primary-teal);
    }

    .empty-state {
      color: var(--text-secondary);
      font-style: italic;
      text-align: center;
      padding: var(--spacing-md);
    }

    .sparkline {
      display: flex;
      align-items: flex-end;
      gap: 4px;
      height: 80px;
      padding: var(--spacing-sm) 0;
    }
    .spark-bar {
      flex: 1;
      min-height: 4px;
      border-radius: 3px 3px 0 0;
      transition: opacity 0.2s;
      cursor: pointer;
    }
    .spark-bar:hover {
      opacity: 0.8;
    }
    .sparkline-labels {
      display: flex;
      justify-content: space-between;
      font-size: 0.7rem;
      color: var(--text-secondary);
    }
  `]
})
export class SwimmerOverviewComponent {
  @Input() personalBests: PersonalBest[] = [];
  @Input() currentRanking: number = 0;
  @Input() trendData: TrendPoint[] = [];

  private minScore = Infinity;
  private maxScore = 0;

  private computeScoreRange(): void {
    if (!this.trendData?.length) return;
    const scores = this.trendData.map(p => p.score);
    this.minScore = Math.min(...scores);
    this.maxScore = Math.max(...scores);
  }

  getBarHeight(score: number): number {
    this.computeScoreRange();
    const range = this.maxScore - this.minScore;
    if (range === 0) return 50;
    return 10 + ((score - this.minScore) / range) * 90;
  }
}
