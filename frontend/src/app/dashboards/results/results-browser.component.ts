import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatTabsModule } from '@angular/material/tabs';
import { MatListModule } from '@angular/material/list';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { ApiClientService } from '../../shared/api/api-client.service';
import { of } from 'rxjs';
import { catchError } from 'rxjs/operators';

@Component({
  selector: 'app-results-browser',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatCardModule,
    MatSelectModule,
    MatFormFieldModule,
    MatTabsModule,
    MatListModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatIconModule,
    MatTableModule
  ],
  template: `
    <div class="results-container">
      <h2>Competition Results Browser</h2>
      
      <mat-card class="filter-card">
        <mat-card-content>
          <div class="filters-row">
            <!-- Event Selection -->
            <mat-form-field appearance="outline">
              <mat-label>Select Event</mat-label>
              <mat-select [(ngModel)]="selectedEvent" (selectionChange)="onEventChange()">
                <mat-option *ngFor="let event of events" [value]="event">{{ event.name }}</mat-option>
              </mat-select>
            </mat-form-field>

            <!-- Meet Selection -->
            <mat-form-field appearance="outline" *ngIf="selectedEvent">
              <mat-label>Select Meet</mat-label>
              <mat-select [(ngModel)]="selectedMeet" (selectionChange)="onMeetChange()">
                <mat-option *ngFor="let meet of meets" [value]="meet">{{ meet.name }}</mat-option>
              </mat-select>
            </mat-form-field>

            <!-- Team Selection -->
            <mat-form-field appearance="outline" *ngIf="selectedMeet">
              <mat-label>Select Team</mat-label>
              <mat-select [(ngModel)]="selectedTeam" (selectionChange)="onTeamChange()">
                <mat-option *ngFor="let team of teams" [value]="team">{{ team.id }}{{ team.name ? ' - ' + team.name : '' }}</mat-option>
              </mat-select>
            </mat-form-field>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- Results Area -->
      <div *ngIf="selectedTeam" class="results-area">
        <mat-tab-group>
          <!-- Figure Results Tab -->
          <mat-tab label="Figure Results">
            <div class="tab-content">
              <mat-form-field appearance="outline" class="athlete-select">
                <mat-label>Select Athlete</mat-label>
                <mat-select [(ngModel)]="selectedAthlete" (selectionChange)="onAthleteChange()">
                  <mat-option *ngFor="let athlete of athletes" [value]="athlete">{{ athlete.name }}</mat-option>
                </mat-select>
              </mat-form-field>

              <mat-card *ngIf="selectedAthlete && figureScores.length > 0" class="scores-card">
                <mat-card-header>
                  <mat-card-title>Figure Scores for {{ selectedAthlete.name }}</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <table mat-table [dataSource]="figureScores" class="mat-elevation-z2">
                    <ng-container matColumnDef="figureName">
                      <th mat-header-cell *matHeaderCellDef> Figure </th>
                      <td mat-cell *matCellDef="let element"> {{element.figureName}} </td>
                    </ng-container>
                    
                    <ng-container matColumnDef="dd">
                      <th mat-header-cell *matHeaderCellDef> DD </th>
                      <td mat-cell *matCellDef="let element"> {{element.dd}} </td>
                    </ng-container>

                    <ng-container matColumnDef="score">
                      <th mat-header-cell *matHeaderCellDef> Score </th>
                      <td mat-cell *matCellDef="let element"> {{element.score}} </td>
                    </ng-container>

                    <tr mat-header-row *matHeaderRowDef="['figureName', 'dd', 'score']"></tr>
                    <tr mat-row *matRowDef="let row; columns: ['figureName', 'dd', 'score'];"></tr>
                  </table>
                </mat-card-content>
              </mat-card>
              
              <div *ngIf="selectedAthlete && figureScores.length === 0" class="no-data">
                No figure scores available for this athlete.
              </div>
            </div>
          </mat-tab>

          <!-- Routine Results Tab -->
          <mat-tab label="Routine Results">
            <div class="tab-content">
              <mat-card class="scores-card">
                <mat-card-header>
                  <mat-card-title>Routine Scores for {{ selectedTeam.name }}</mat-card-title>
                </mat-card-header>
                <mat-card-content>
                  <div *ngIf="routineScores.length > 0; else noRoutines">
                    <table mat-table [dataSource]="routineScores" class="mat-elevation-z2">
                      <ng-container matColumnDef="routineName">
                        <th mat-header-cell *matHeaderCellDef> Routine </th>
                        <td mat-cell *matCellDef="let element"> {{element.routineName}} </td>
                      </ng-container>
                      
                      <ng-container matColumnDef="type">
                        <th mat-header-cell *matHeaderCellDef> Type </th>
                        <td mat-cell *matCellDef="let element"> {{element.type}} </td>
                      </ng-container>

                      <ng-container matColumnDef="score">
                        <th mat-header-cell *matHeaderCellDef> Score </th>
                        <td mat-cell *matCellDef="let element"> {{element.score}} </td>
                      </ng-container>

                      <ng-container matColumnDef="athletes">
                        <th mat-header-cell *matHeaderCellDef> Athletes </th>
                        <td mat-cell *matCellDef="let element"> 
                          <span *ngIf="element.athletes?.length">{{ element.athletes.join(', ') }}</span>
                          <span *ngIf="!element.athletes?.length" class="no-data">N/A</span>
                        </td>
                      </ng-container>

                      <tr mat-header-row *matHeaderRowDef="['routineName', 'type', 'score', 'athletes']"></tr>
                      <tr mat-row *matRowDef="let row; columns: ['routineName', 'type', 'score', 'athletes'];"></tr>
                    </table>
                  </div>
                  <ng-template #noRoutines>
                    <div class="no-data">No routine scores available for this team.</div>
                  </ng-template>
                </mat-card-content>
              </mat-card>
            </div>
          </mat-tab>
        </mat-tab-group>
      </div>
    </div>
  `,
  styles: [`
    .results-container {
      padding: 20px;
      max-width: 1200px;
      margin: 0 auto;
    }
    .filters-row {
      display: flex;
      gap: 16px;
      flex-wrap: wrap;
    }
    .filter-card {
      margin-bottom: 24px;
    }
    .results-area {
      margin-top: 20px;
    }
    .tab-content {
      padding: 20px 0;
    }
    .athlete-select {
      margin-bottom: 16px;
      width: 300px;
    }
    .scores-card {
      margin-top: 16px;
    }
    .no-data {
      padding: 20px;
      text-align: center;
      color: #666;
      font-style: italic;
    }
    table {
      width: 100%;
    }
  `]
})
export class ResultsBrowserComponent implements OnInit {
  private apiClient = inject(ApiClientService);

  events: any[] = [];
  meets: any[] = [];
  teams: any[] = [];
  athletes: any[] = [];
  
  selectedEvent: any = null;
  selectedMeet: any = null;
  selectedTeam: any = null;
  selectedAthlete: any = null;

  figureScores: any[] = [];
  routineScores: any[] = [];

  ngOnInit() {
    this.loadEvents();
  }

  loadEvents() {
    this.apiClient.get<any>('/results/events').pipe(
      catchError(() => {
        // Mock data if endpoint fails
        return of({ data: [
          { id: 1, name: '2026 National Championship' },
          { id: 2, name: 'Regional Qualifier Spring 2026' }
        ] });
      })
    ).subscribe((res: any) => {
      this.events = res.data || [];
    });
  }

  onEventChange() {
    this.selectedMeet = null;
    this.selectedTeam = null;
    this.selectedAthlete = null;
    this.meets = [];
    this.teams = [];
    this.athletes = [];
    this.figureScores = [];
    this.routineScores = [];
    
    if (this.selectedEvent) {
      this.apiClient.get<any>(`/results/events/${this.selectedEvent.id}/meets`).pipe(
        catchError(() => {
          return of({ data: [
            { id: 101, name: 'Preliminaries' },
            { id: 102, name: 'Finals' }
          ] });
        })
      ).subscribe((res: any) => {
        this.meets = res.data || [];
      });
    }
  }

  onMeetChange() {
    this.selectedTeam = null;
    this.selectedAthlete = null;
    this.teams = [];
    this.athletes = [];
    this.figureScores = [];
    this.routineScores = [];

    if (this.selectedMeet) {
      this.apiClient.get<any>(`/results/meets/${this.selectedMeet.id}/teams`).pipe(
        catchError(() => {
          return of({ data: [
            { id: 201, name: 'Aqua Stars' },
            { id: 202, name: 'Water Nymphs' }
          ] });
        })
      ).subscribe((res: any) => {
        this.teams = res.data || [];
      });
    }
  }

  onTeamChange() {
    this.selectedAthlete = null;
    this.athletes = [];
    this.figureScores = [];
    this.routineScores = [];

    if (this.selectedTeam) {
      // Load athletes for team
      this.apiClient.get<any>(`/results/meets/${this.selectedMeet.id}/teams/${this.selectedTeam.id}/athletes`).pipe(
        catchError(() => {
          return of({ data: [
            { id: 'Jane Doe', name: 'Jane Doe' },
            { id: 'Alice Smith', name: 'Alice Smith' }
          ] });
        })
      ).subscribe((res: any) => {
        this.athletes = res.data || [];
      });

      // Load routine scores for team
      this.apiClient.get<any>(`/results/meets/${this.selectedMeet.id}/teams/${this.selectedTeam.id}/routines`).pipe(
        catchError(() => {
          return of({ data: [
            { routineName: 'Free Routine', type: 'Team', score: 85.5 },
            { routineName: 'Technical Routine', type: 'Team', score: 82.3 },
            { routineName: 'Duet Free', type: 'Duet', score: 88.0 }
          ] });
        })
      ).subscribe((res: any) => {
        this.routineScores = res.data || [];
      });
    }
  }

  onAthleteChange() {
    this.figureScores = [];
    
    if (this.selectedAthlete && this.selectedMeet) {
      this.apiClient.get<any>(`/results/meets/${this.selectedMeet.id}/athletes/${encodeURIComponent(this.selectedAthlete.id)}/figures`).pipe(
        catchError(() => {
          return of({ data: [
            { figureName: 'Ballet Leg', dd: 1.6, score: 7.2 },
            { figureName: 'Barracuda', dd: 1.9, score: 6.8 },
            { figureName: 'Kip', dd: 1.8, score: 7.5 },
            { figureName: 'Walkover', dd: 2.1, score: 7.0 }
          ] });
        })
      ).subscribe((res: any) => {
        this.figureScores = res.data || [];
      });
    }
  }
}
