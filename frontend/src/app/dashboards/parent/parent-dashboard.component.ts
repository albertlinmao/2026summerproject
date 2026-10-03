import { Component } from '@angular/core';

import { TypographyComponent } from '../../shared/ui/typography.component';
import { CardComponent } from '../../shared/ui/card.component';

@Component({
  selector: 'app-parent-dashboard',
  standalone: true,
  imports: [TypographyComponent, CardComponent],
  template: `
    <div class="parent-dashboard">
      <app-typography variant="headline-medium" color="on-surface"> My Swimmers </app-typography>
      <app-typography variant="body-medium" color="on-surface-variant">
        Linked swimmers and the family video access granted by your club membership will appear
        here.
      </app-typography>
      <app-card class="placeholder-card">
        <app-typography variant="title-medium" color="primary">Linked Swimmers</app-typography>
        <app-typography variant="body-small" color="on-surface-variant">
          Progress summaries and uploaded video will appear here.
        </app-typography>
      </app-card>
    </div>
  `,
  styles: [
    `
      .parent-dashboard {
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
export class ParentDashboardComponent {}
