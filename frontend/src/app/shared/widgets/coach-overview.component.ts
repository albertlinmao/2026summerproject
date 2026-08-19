import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HeatmapComponent } from './heatmap.component';
import { HeatmapData } from '../../store/dashboard.store';

@Component({
  selector: 'app-coach-overview',
  template: `
    <div class="overview-container">
      <h3 style="color: var(--primary-navy); margin-bottom: var(--spacing-md);">Team Overview & Predictions</h3>
      
      <div style="display: flex; gap: var(--spacing-lg); flex-wrap: wrap;">
        <!-- Visual component -->
        <div style="flex: 1; min-width: 300px;">
          <app-heatmap [chartData]="heatmapData"></app-heatmap>
        </div>

        <!-- Predictive Data Visualization -->
        <div class="predictions-panel">
          <h4 style="color: var(--text-primary); margin-top: 0; margin-bottom: var(--spacing-md);">Athlete Predictions</h4>
          <ul class="prediction-list">
            <li *ngFor="let athlete of heatmapData" class="prediction-card">
              <div class="athlete-header">
                <strong>{{ athlete.athlete_id }}</strong>
              </div>
              <div class="scores-grid">
                <div class="score-item">
                  <span class="label">Figure Score:</span>
                  <span class="value">{{ athlete.figure_score }}</span>
                </div>
                <div class="score-item">
                  <span class="label">Routine Score:</span>
                  <span class="value">{{ athlete.routine_score }}</span>
                </div>
                <div class="score-item highlight">
                  <span class="label">Predicted Next:</span>
                  <span class="value score-display" style="font-size: 1.5rem;">{{ athlete.prediction_score | number:'1.1-2' }}</span>
                </div>
              </div>
            </li>
          </ul>
          <p *ngIf="!heatmapData || heatmapData.length === 0" style="color: var(--text-secondary);">No athlete data available.</p>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .overview-container { height: 100%; display: flex; flex-direction: column; }
    .predictions-panel { flex: 1; min-width: 300px; background: var(--surface-color); padding: var(--spacing-md); border-radius: var(--border-radius); }
    .prediction-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--spacing-sm); }
    .prediction-card { background: var(--bg-color); border: 1px solid var(--surface-color); padding: var(--spacing-md); border-radius: 8px; }
    .athlete-header { font-size: 1.1em; margin-bottom: var(--spacing-sm); padding-bottom: var(--spacing-sm); border-bottom: 2px solid var(--surface-color); color: var(--primary-navy); }
    .scores-grid { display: flex; flex-direction: column; gap: var(--spacing-sm); }
    .score-item { display: flex; justify-content: space-between; font-family: var(--font-data); align-items: center; }
    .score-item.highlight { margin-top: var(--spacing-sm); padding-top: var(--spacing-sm); border-top: 1px dashed var(--text-secondary); font-weight: bold; }
    .label { color: var(--text-secondary); font-family: var(--font-main); }
    .value { font-weight: 500; color: var(--text-primary); }
  `],
  standalone: true,
  imports: [CommonModule, HeatmapComponent]
})
export class CoachOverviewComponent {
  @Input() heatmapData: HeatmapData[] = [];
}
