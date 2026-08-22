import { Component } from '@angular/core';

/**
 * Responsive card-based grid layout for dashboard widgets (DR-003/DR-004).
 * Navigation stickiness is provided by the app shell; this layout arranges
 * widget cards in an adaptive grid that collapses on smaller screens.
 */
@Component({
  selector: 'app-dashboard-layout',
  standalone: true,
  imports: [],
  template: `
    <div class="dashboard-grid" role="list">
      <ng-content></ng-content>
    </div>
  `,
  styles: [
    `
      .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(12, 1fr);
        gap: var(--md-sys-spacing-4);
        align-items: stretch;
      }

      .dashboard-grid ::ng-deep > * {
        grid-column: span 12;
      }

      @media (min-width: 640px) {
        .dashboard-grid ::ng-deep > *.span-6 {
          grid-column: span 6;
        }
        .dashboard-grid ::ng-deep > *.span-12 {
          grid-column: span 12;
        }
      }

      @media (min-width: 1024px) {
        .dashboard-grid ::ng-deep > *.span-4 {
          grid-column: span 4;
        }
        .dashboard-grid ::ng-deep > *.span-6 {
          grid-column: span 6;
        }
        .dashboard-grid ::ng-deep > *.span-8 {
          grid-column: span 8;
        }
        .dashboard-grid ::ng-deep > *.span-12 {
          grid-column: span 12;
        }
      }
    `,
  ],
})
export class DashboardLayoutComponent {}
