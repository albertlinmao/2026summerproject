import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { CoachOverviewComponent } from '../../shared/widgets/coach-overview.component';
import { VideoCorrectionComponent } from '../../shared/widgets/video-correction.component';
import { RoutineChoreographyComponent } from '../../shared/widgets/routine-choreography.component';
import { SstScoresComponent } from '../sst-scores/sst-scores.component';
import { DashboardStore } from '../../store/dashboard.store';

@Component({
  selector: 'app-shell',
  template: `
    <div class="dashboard-shell">
      <nav class="sticky-nav">
        <div class="brand">
          <img src="/icons/as_dashboard_logo.png" alt="Artistic Swimming Dashboard Logo" class="logo" />
          <h2 class="brand-title"><span class="fancy-ez">ez</span> Artistic Swimming Dashboard</h2>
        </div>
        <div class="controls">
          <button class="btn btn-icon" title="Upload Video">⬆️</button>
          <button class="btn btn-primary" title="Play">▶</button>
          <button class="btn btn-primary" title="Pause">⏸</button>
          <button class="btn btn-accent" title="Mark Timestamp">⏱</button>
        </div>
      </nav>
      
      <div *ngIf="store.isLoading()">Loading dashboard...</div>
      <div *ngIf="store.error()" class="error">{{ store.error() }}</div>
      
      <div class="dashboard-grid">
        <div class="card" style="grid-column: 1 / -1;">
          <app-sst-scores></app-sst-scores>
        </div>

        <div class="card">
          <app-coach-overview 
            *ngIf="isCoach && !store.isLoading()" 
            [heatmapData]="store.teamHeatmap()">
          </app-coach-overview>
        </div>
        
        <div class="card">
          <app-routine-choreography></app-routine-choreography>
        </div>
        
        <div class="card">
          <app-video-correction></app-video-correction>
        </div>
      </div>

      <ng-content></ng-content>
    </div>
  `,
  styles: [`
    .dashboard-shell { display: flex; flex-direction: column; min-height: 100vh; }
    .brand { display: flex; align-items: center; height: 100%; gap: 15px; }
    .brand-title { margin: 0; font-weight: 600; font-family: var(--font-main); font-size: 1.5rem; color: white; display: flex; align-items: center; gap: 8px; }
    .fancy-ez { font-family: 'Dancing Script', cursive; font-size: 2.2rem; color: var(--accent-gold); font-weight: 700; }
    .logo { height: 80px; width: auto; object-fit: contain; }
  `],
  standalone: true,
  imports: [CommonModule, CoachOverviewComponent, VideoCorrectionComponent, RoutineChoreographyComponent, SstScoresComponent]
})
export class ShellComponent implements OnInit {
  isCoach = true; // Placeholder for Phase 3 role logic
  store = inject(DashboardStore);

  ngOnInit() {
    this.store.loadDashboard();
  }
}
