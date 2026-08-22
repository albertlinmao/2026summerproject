import { Component } from '@angular/core';

import { TypographyComponent } from '../../shared/ui/typography.component';
import { CardComponent } from '../../shared/ui/card.component';

@Component({
  selector: 'app-swimmer-dashboard',
  standalone: true,
  imports: [TypographyComponent, CardComponent],
  template: `
    <div class="swimmer-dashboard">
      <app-typography variant="headline-medium" color="on-surface"> My Progress </app-typography>
      <app-typography variant="body-medium" color="on-surface-variant">
        Personal progress charts, personal bests, and AI recommendations are implemented in User
        Story 2.
      </app-typography>
      <app-card class="placeholder-card">
        <app-typography variant="title-medium" color="primary">Personal Progress</app-typography>
        <app-typography variant="body-small" color="on-surface-variant">
          Figure and routine trends over time will appear here.
        </app-typography>
      </app-card>
    </div>
  `,
  styles: [
    `
      .swimmer-dashboard {
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
export class SwimmerDashboardComponent {}
