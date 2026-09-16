import {
  Component,
  OnInit,
  inject,
  OnDestroy,
  ViewChild,
  ElementRef,
  NgZone,
  ChangeDetectorRef,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTableModule } from '@angular/material/table';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import * as echarts from 'echarts';
import { ApiClientService } from '../../shared/api/api-client.service';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-athlete-figure-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatSelectModule,
    MatFormFieldModule,
    MatTableModule,
    MatProgressSpinnerModule,
    MatIconModule,
    MatButtonModule
  ],
  template: `
    <div class="athlete-figure-dashboard">
      <mat-card class="filter-card">
        <mat-card-content>
          <div class="filters-row">
            <!-- Club Selection -->
            <mat-form-field appearance="outline">
              <mat-label>Select Club</mat-label>
              <mat-select [(ngModel)]="selectedClub" (selectionChange)="onClubChange()">
                <mat-option *ngFor="let club of clubs" [value]="club">
                  {{ club.name }}
                </mat-option>
              </mat-select>
            </mat-form-field>

            <!-- Athlete Selection -->
            <mat-form-field appearance="outline" *ngIf="selectedClub">
              <mat-label>Select Athlete</mat-label>
              <mat-select [(ngModel)]="selectedAthlete" (selectionChange)="onAthleteChange()">
                <mat-option *ngFor="let athlete of athletes" [value]="athlete">
                  {{ athlete.name }}
                </mat-option>
              </mat-select>
            </mat-form-field>
          </div>

          <div *ngIf="isLoading" class="loading-indicator">
            <mat-spinner diameter="32"></mat-spinner>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- Results Area -->
      <div *ngIf="selectedAthlete && !isLoading" class="results-area">
        <h3>
          {{ selectedAthlete.name }} - Figure Scores Across Competitions
          <span *ngIf="selectedClub" class="club-label">({{ selectedClub.name }})</span>
        </h3>

        <mat-card *ngIf="figureHistory.length > 0" class="history-card">
          <mat-card-content>
            <table mat-table [dataSource]="figureHistory" class="mat-elevation-z2">

              <!-- Competition Column -->
              <ng-container matColumnDef="competition">
                <th mat-header-cell *matHeaderCellDef> Competition </th>
                <td mat-cell *matCellDef="let element">
                  <div class="comp-name">{{ element.meetName || element.eventName || 'Unknown' }}</div>
                  <div class="comp-date">{{ element.meetDate | date:'mediumDate' }}</div>
                </td>
              </ng-container>

              <!-- Event Column -->
              <ng-container matColumnDef="event">
                <th mat-header-cell *matHeaderCellDef> Event </th>
                <td mat-cell *matCellDef="let element"> {{ element.eventName || '-' }} </td>
              </ng-container>

              <!-- Team Column -->
              <ng-container matColumnDef="team">
                <th mat-header-cell *matHeaderCellDef> Team </th>
                <td mat-cell *matCellDef="let element"> {{ element.teamName || element.teamCode || '-' }} </td>
              </ng-container>

              <!-- Figure Score Column -->
              <ng-container matColumnDef="figureScore">
                <th mat-header-cell *matHeaderCellDef> Figure Score </th>
                <td mat-cell *matCellDef="let element">{{ element.figureScore ?? '-' }}</td>
              </ng-container>

              <!-- Figures Column -->
              <ng-container matColumnDef="figures">
                <th mat-header-cell *matHeaderCellDef> Figures </th>
                <td mat-cell *matCellDef="let element">
                  <div class="figure-chip" *ngFor="let item of element.figures">
                    <span class="figure-name">{{ item.name }}</span>
                    <span class="figure-score">{{ item.score }}</span>
                  </div>
                </td>
              </ng-container>

              <tr mat-header-row *matHeaderRowDef="displayedColumns"></tr>
              <tr mat-row *matRowDef="let row; columns: displayedColumns;"></tr>
            </table>
          </mat-card-content>
        </mat-card>

        <div *ngIf="figureHistory.length === 0" class="no-data">
          No figure scores available for this athlete.
        </div>

        <!-- Charts -->
        <div class="charts-section" [hidden]="figureHistory.length === 0">
          <!-- Multi-figure line chart (score trend per figure across competitions) -->
          <mat-card class="chart-card" [hidden]="figureNames.length === 0">
            <mat-card-content>
              <h4>Figure Score Trends Across Competitions</h4>
              <div #lineChartContainer class="chart-container"></div>
              <p class="chart-hint">Each line represents one figure's score over time (by competition date).</p>
            </mat-card-content>
          </mat-card>

          <!-- Total / figure score bar chart across competitions -->
          <mat-card class="chart-card" [hidden]="figureHistory.length === 0">
            <mat-card-content>
              <h4>Figure Score by Competition</h4>
              <div #barChartContainer class="chart-container"></div>
              <p class="chart-hint">Bar chart of total figure score for each competition (ordered chronologically).</p>
            </mat-card-content>
          </mat-card>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .athlete-figure-dashboard {
        padding: 20px;
        max-width: 1400px;
        margin: 0 auto;
      }
      .filter-card {
        margin-bottom: 24px;
      }
      .filters-row {
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
        align-items: center;
      }
      mat-form-field {
        flex: 1;
        min-width: 200px;
        max-width: 400px;
      }
      .loading-indicator {
        display: flex;
        justify-content: center;
        margin-top: 16px;
      }
      .results-area {
        margin-top: 20px;
      }
      .club-label {
        color: var(--md-sys-color-on-surface-variant);
        font-weight: normal;
        font-size: 0.9rem;
      }
      table {
        width: 100%;
      }
      .comp-name {
        font-weight: 500;
      }
      .comp-date {
        color: var(--md-sys-color-on-surface-variant);
        font-size: 0.8rem;
        margin-top: 2px;
      }
      .figure-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: var(--md-sys-color-surface-variant);
        border-radius: 4px;
        padding: 2px 8px;
        margin: 2px 4px 2px 0;
        font-size: 0.75rem;
      }
      .figure-name {
        font-weight: 500;
      }
      .figure-score {
        color: var(--md-sys-color-primary);
        font-weight: 600;
      }
      .no-data {
        padding: 20px;
        text-align: center;
        color: #666;
        font-style: italic;
      }
      .history-card {
        margin-top: 16px;
      }
      .charts-section {
        display: flex;
        flex-direction: column;
        gap: 24px;
        margin-top: 24px;
      }
      .chart-card {
        margin-top: 0;
      }
      .chart-container {
        width: 100%;
        height: 380px;
        min-height: 300px;
      }
      .chart-hint {
        color: var(--md-sys-color-on-surface-variant);
        font-style: italic;
        font-size: 0.8rem;
        margin-top: 8px;
        margin-bottom: 0;
      }
    `
  ]
})
export class AthleteFigureDashboardComponent implements OnInit, OnDestroy {
  private apiClient = inject(ApiClientService);
  private zone = inject(NgZone);
  private cdr = inject(ChangeDetectorRef);

  @ViewChild('lineChartContainer', { static: false }) lineChartContainer!: ElementRef<HTMLDivElement>;
  @ViewChild('barChartContainer', { static: false }) barChartContainer!: ElementRef<HTMLDivElement>;

  clubs: any[] = [];
  athletes: any[] = [];
  figureHistory: any[] = [];

  selectedClub: any = null;
  selectedAthlete: any = null;

  isLoading = false;

  lineChart: echarts.ECharts | null = null;
  barChart: echarts.ECharts | null = null;
  private resizeObservers: ResizeObserver[] = [];

  displayedColumns = ['competition', 'event', 'team', 'figureScore', 'figures'];

  ngOnInit() {
    this.loadClubs();
  }

  ngOnDestroy() {
    this.resizeObservers.forEach((obs) => obs.disconnect());
    this.lineChart?.dispose();
    this.barChart?.dispose();
  }

  private initCharts() {
    if (this.lineChartContainer?.nativeElement && !this.lineChart) {
      this.lineChart = echarts.init(this.lineChartContainer.nativeElement, undefined, { renderer: 'canvas' });
      this.watchResize(this.lineChartContainer.nativeElement, this.lineChart);
    }
    if (this.barChartContainer?.nativeElement && !this.barChart) {
      this.barChart = echarts.init(this.barChartContainer.nativeElement, undefined, { renderer: 'canvas' });
      this.watchResize(this.barChartContainer.nativeElement, this.barChart);
    }
  }

  private watchResize(el: HTMLDivElement, chart: echarts.ECharts | null) {
    const obs = new ResizeObserver(() => chart?.resize());
    obs.observe(el);
    this.resizeObservers.push(obs);
  }

  get figureNames(): string[] {
    const names = new Set<string>();
    for (const entry of this.figureHistory) {
      for (const fig of entry.figures || []) {
        names.add(fig.name);
      }
    }
    return Array.from(names);
  }

  loadClubs() {
    this.isLoading = true;
    this.apiClient.get<any>('/results/clubs').pipe(
      catchError(() => {
        this.isLoading = false;
        return of({ data: [] });
      })
    ).subscribe((res: any) => {
      this.clubs = res.data || [];
      this.isLoading = false;
    });
  }

  onClubChange() {
    this.selectedAthlete = null;
    this.athletes = [];
    this.figureHistory = [];
    this.clearCharts();

    if (this.selectedClub) {
      this.isLoading = true;
      this.apiClient.get<any>(`/results/clubs/${this.selectedClub.id}/athletes`).pipe(
        catchError(() => {
          this.isLoading = false;
          return of({ data: [] });
        })
      ).subscribe((res: any) => {
        this.athletes = res.data || [];
        this.isLoading = false;
      });
    }
  }

  onAthleteChange() {
    this.figureHistory = [];
    this.clearCharts();

    if (this.selectedAthlete) {
      this.isLoading = true;
      this.apiClient.get<any>(`/results/athletes/${encodeURIComponent(this.selectedAthlete.name)}/figure-history`).pipe(
        catchError(() => {
          this.isLoading = false;
          return of({ data: [] });
        })
      ).subscribe((res: any) => {
        const history = (res.data || []) as any[];

        // Enrich each history entry with a parsed figures list
        this.figureHistory = history.map((entry: any) => ({
          ...entry,
          figures: this.parseFigures(entry.figureScores)
        }));

        this.isLoading = false;
        
        // Force synchronous DOM update so [hidden] bindings are resolved
        this.cdr.detectChanges();

        this.zone.runOutsideAngular(() => {
          this.initCharts();
          this.renderCharts();
          
          // Small delay to ensure the browser has computed layouts
          setTimeout(() => {
            this.lineChart?.resize();
            this.barChart?.resize();
          }, 50);
        });
      });
    }
  }

  private clearCharts() {
    this.resizeObservers.forEach((obs) => obs.disconnect());
    this.resizeObservers = [];
    this.lineChart?.dispose();
    this.lineChart = null;
    this.barChart?.dispose();
    this.barChart = null;
  }

  private renderCharts() {
    if (!this.figureHistory.length) {
      this.clearCharts();
      return;
    }

    if (this.lineChart) {
      this.renderLineChart();
    }
    if (this.barChart) {
      this.renderBarChart();
    }
  }

  private renderLineChart() {
    const names = this.figureNames;
    const labels = this.figureHistory.map((e) => this.chartLabel(e));
    const navy = this.cssVar('--primary-navy', '#0A2342');

    // Build one series per figure
    const colors = ['#178082', '#0A2342', '#E07A5F', '#81B29A', '#3D405B', '#F2CC8F', '#4F6272', '#9B5DE5'];
    const series = names.map((name, i) => ({
      name,
      type: 'line' as const,
      smooth: true,
      connectNulls: true,
      symbol: 'circle',
      symbolSize: 8,
      lineStyle: { width: 2 },
      data: this.figureHistory.map((e) => {
        const fig = (e.figures || []).find((f: any) => f.name === name);
        return fig ? fig.score : null;
      }),
    }));

    this.lineChart!.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0, textStyle: { color: navy, fontFamily: 'Inter, sans-serif' } },
      grid: { left: 50, right: 24, top: 40, bottom: 60, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: navy, interval: 0, rotate: 30 },
      },
      yAxis: {
        type: 'value',
        name: 'Score',
        axisLabel: { color: navy },
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', height: 20, bottom: 8 },
      ],
      color: colors,
      series,
    });
  }

  private renderBarChart() {
    const labels = this.figureHistory.map((e) => this.chartLabel(e));
    const teal = this.cssVar('--primary-teal', '#178082');

    this.barChart!.setOption({
      tooltip: { trigger: 'axis' },
      legend: { top: 0 },
      grid: { left: 50, right: 24, top: 40, bottom: 60, containLabel: true },
      xAxis: {
        type: 'category',
        data: labels,
        axisLabel: { color: this.cssVar('--primary-navy', '#0A2342'), interval: 0, rotate: 30 },
      },
      yAxis: {
        type: 'value',
        name: 'Total Score',
        axisLabel: { color: this.cssVar('--primary-navy', '#0A2342') },
        splitLine: { lineStyle: { color: 'rgba(0,0,0,0.08)' } },
      },
      dataZoom: [
        { type: 'inside', start: 0, end: 100 },
        { type: 'slider', height: 20, bottom: 8 },
      ],
      series: [
        {
          name: 'Total Figure Score',
          type: 'bar',
          data: this.figureHistory.map((e) => e.figureScore),
          itemStyle: { color: teal, borderRadius: [4, 4, 0, 0] },
          barMaxWidth: 48,
        },
      ],
    });
  }

  private chartLabel(entry: any): string {
    const date = entry.meetDate ? new Date(entry.meetDate).toLocaleDateString() : '';
    const event = entry.eventName || entry.meetName || 'Competition';
    return date ? `${event}\n${date}` : event;
  }

  private cssVar(name: string, fallback: string): string {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
  }

  private parseFigures(figureScores: any): Array<{ name: string; score: number }> {
    if (!figureScores) return [];
    if (typeof figureScores === 'string') {
      try {
        figureScores = JSON.parse(figureScores);
      } catch {
        return [];
      }
    }
    if (typeof figureScores === 'object') {
      return Object.entries(figureScores).map(([name, score]) => ({
        name,
        score: typeof score === 'number' ? score : Number(score) || 0
      }));
    }
    return [];
  }
}