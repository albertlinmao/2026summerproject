import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiService } from '../../shared/api.service';

@Component({
  selector: 'app-sst-scores',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="sst-scores-widget">
      <h3>SST Team Figure & Routine Scores</h3>
      
      <div *ngIf="loading" class="loading">Loading scores...</div>
      <div *ngIf="error" class="error">{{ error }}</div>

      <div *ngIf="!loading && !error">
        
        <!-- Filter Pane -->
        <div class="filter-pane">
          <div class="filter-group">
            <label>Team Name</label>
            <input type="text" [(ngModel)]="filterTeam" (ngModelChange)="applyFilters()" placeholder="Filter by team...">
          </div>
          <div class="filter-group">
            <label>Athlete</label>
            <input type="text" [(ngModel)]="filterAthlete" (ngModelChange)="applyFilters()" placeholder="Filter by athlete...">
          </div>
          <div class="filter-group">
            <label>Game Name</label>
            <input type="text" [(ngModel)]="filterGame" (ngModelChange)="applyFilters()" placeholder="Filter by game...">
          </div>
          <div class="filter-group">
            <label>Game Type</label>
            <select [(ngModel)]="filterType" (ngModelChange)="applyFilters()">
              <option value="">All Types</option>
              <option value="Figure">Figure</option>
              <option value="Routine">Routine</option>
            </select>
          </div>
        </div>

        <div class="table-responsive">
          <table class="scores-table">
            <thead>
              <tr>
                <th>Team Name</th>
                <th>Athlete</th>
                <th>Game Name</th>
                <th>Game Type</th>
                <th>Score</th>
                <th>Rank</th>
                <th>Draw</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let score of filteredScores">
                <td>{{ score.team?.name || 'N/A' }}</td>
                <td>{{ score.athlete_name || 'N/A' }}</td>
                <td>{{ score.swim_game?.name || 'N/A' }}</td>
                <td>{{ score.swim_game?.game_type || 'N/A' }}</td>
                <td>{{ score.score || 'N/A' }}</td>
                <td>{{ score.rank || 'N/A' }}</td>
                <td>{{ score.draw || 'N/A' }}</td>
              </tr>
              <tr *ngIf="filteredScores.length === 0">
                <td colspan="7" class="no-data">No scores found matching the filters.</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .sst-scores-widget { 
      padding: 15px; 
      width: 100%;
    }
    .sst-scores-widget h3 {
      margin-top: 0;
      color: var(--text-color, #333);
      border-bottom: 1px solid #eee;
      padding-bottom: 10px;
    }
    .filter-pane {
      display: flex;
      flex-wrap: wrap;
      gap: 15px;
      margin-bottom: 20px;
      padding: 15px;
      background-color: var(--bg-alt, #f9f9f9);
      border: 1px solid var(--border-color, #ddd);
      border-radius: 6px;
    }
    .filter-group {
      display: flex;
      flex-direction: column;
      gap: 5px;
      flex: 1;
      min-width: 150px;
    }
    .filter-group label {
      font-size: 0.85rem;
      font-weight: 600;
      color: #555;
    }
    .filter-group input, .filter-group select {
      padding: 8px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-family: inherit;
    }
    .table-responsive {
      overflow-x: auto;
      overflow-y: auto;
      max-height: 250px; /* Header + approx 4 rows */
    }
    .scores-table {
      width: 100%; 
      border-collapse: collapse; 
      margin: 0;
    }
    .scores-table th, .scores-table td {
      padding: 8px 12px; 
      border: 1px solid var(--border-color, #ddd);
      text-align: left;
    }
    .scores-table th {
      background-color: var(--bg-alt, #f9f9f9);
      font-weight: 600;
      position: sticky;
      top: 0;
      z-index: 1;
    }
    .no-data {
      text-align: center !important;
      color: #777;
      padding: 20px !important;
    }
    .error { color: #d32f2f; }
    .loading { color: #666; font-style: italic; margin-top: 15px; }
  `]
})
export class SstScoresComponent implements OnInit {
  apiService = inject(ApiService);
  
  scores: any[] = [];
  filteredScores: any[] = [];
  
  filterTeam = '';
  filterAthlete = '';
  filterGame = '';
  filterType = '';

  loading = true;
  error = '';

  ngOnInit() {
    this.fetchScores();
  }

  async fetchScores() {
    try {
      const response = await this.apiService.get('/scores/sst');
      const result = await response.json();
      
      if (result.error) {
        this.error = result.error;
      } else {
        this.scores = result.data || [];
        this.filteredScores = this.scores;
      }
    } catch (err: any) {
      this.error = 'Failed to load scores: ' + err.message;
    } finally {
      this.loading = false;
    }
  }

  applyFilters() {
    this.filteredScores = this.scores.filter(s => {
      const matchTeam = !this.filterTeam || (s.team?.name || '').toLowerCase().includes(this.filterTeam.toLowerCase());
      const matchAthlete = !this.filterAthlete || (s.athlete_name || '').toLowerCase().includes(this.filterAthlete.toLowerCase());
      const matchGame = !this.filterGame || (s.swim_game?.name || '').toLowerCase().includes(this.filterGame.toLowerCase());
      const matchType = !this.filterType || (s.swim_game?.game_type || '').toLowerCase() === this.filterType.toLowerCase();
      
      return matchTeam && matchAthlete && matchGame && matchType;
    });
  }
}
