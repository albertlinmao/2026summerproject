import { Component } from '@angular/core';

import { TypographyComponent } from '../../shared/ui/typography.component';
import { CardComponent } from '../../shared/ui/card.component';

@Component({
  selector: 'app-club-admin-dashboard',
  standalone: true,
  imports: [TypographyComponent, CardComponent],
  template: `
    <div class="club-admin-dashboard">
      <app-typography variant="headline-medium" color="on-surface">
        Club Administration
      </app-typography>
      <app-typography variant="body-medium" color="on-surface-variant">
        Club-wide aggregates, coach effectiveness, and retention analytics are implemented in User
        Story 3.
      </app-typography>
      <app-card class="placeholder-card">
        <app-typography variant="title-medium" color="primary">Club Overview</app-typography>
        <app-typography variant="body-small" color="on-surface-variant">
          Medal counts, rankings, and retention rates will appear here.
        </app-typography>
      </app-card>
    </div>
  `,
  styles: [
    `
      .club-admin-dashboard {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-4);
        padding: var(--md-sys-spacing-4);
      }
      .placeholder-card {
        padding: var(--md-sys-spacing-4);
      }
    `,
  ],
})
export class ClubAdminDashboardComponent {}
