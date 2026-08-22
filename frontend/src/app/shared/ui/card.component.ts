import { Component, Input, HostBinding } from '@angular/core';

@Component({
  selector: 'app-card',
  standalone: true,
  imports: [],
  template: `
    <div
      class="app-card"
      [class.elevated]="elevated"
      [class.outlined]="outlined"
      [class.filled]="filled"
      [class.interactive]="interactive"
      [style.--card-elevation]="elevationLevel"
    >
      @if (header || title || subtitle || headerActions.length) {
        <div class="card-header">
          <div class="header-content">
            @if (title) {
              <h3 class="card-title">{{ title }}</h3>
            }
            @if (subtitle) {
              <p class="card-subtitle">{{ subtitle }}</p>
            }
            <ng-content select="[slot=header]"></ng-content>
          </div>
          @if (headerActions.length) {
            <div class="header-actions">
              <ng-content select="[slot=header-action]"></ng-content>
            </div>
          }
        </div>
      }

      <div class="card-content">
        <ng-content></ng-content>
      </div>

      @if (footerActions.length) {
        <div class="card-footer">
          <ng-content select="[slot=footer]"></ng-content>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .app-card {
        background: var(--md-sys-color-surface);
        color: var(--md-sys-color-on-surface);
        border-radius: var(--md-sys-corner-large);
        overflow: hidden;
        transition: box-shadow var(--md-sys-motion-duration-medium-1)
          var(--md-sys-motion-easing-standard);
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      .app-card.elevated {
        box-shadow: var(--md-sys-elevation-1);
      }

      .app-card.elevated:hover {
        box-shadow: var(--md-sys-elevation-3);
      }

      .app-card.outlined {
        border: 1px solid var(--md-sys-color-outline-variant);
      }

      .app-card.filled {
        background: var(--md-sys-color-surface-variant);
      }

      .app-card.interactive {
        cursor: pointer;
      }

      .app-card.interactive:focus-visible {
        outline: 2px solid var(--md-sys-color-primary);
        outline-offset: 2px;
      }

      .card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: var(--md-sys-spacing-4) var(--md-sys-spacing-5);
        border-bottom: 1px solid var(--md-sys-color-outline-variant);
        gap: var(--md-sys-spacing-4);
      }

      .header-content {
        flex: 1;
        min-width: 0;
      }

      .card-title {
        margin: 0;
        font-size: var(--md-sys-title-large-size);
        font-weight: var(--md-sys-title-large-weight);
        line-height: var(--md-sys-title-large-line-height);
        color: var(--md-sys-color-on-surface);
      }

      .card-subtitle {
        margin: var(--md-sys-spacing-1) 0 0;
        font-size: var(--md-sys-body-small-size);
        font-weight: var(--md-sys-body-small-weight);
        line-height: var(--md-sys-body-small-line-height);
        color: var(--md-sys-color-on-surface-variant);
      }

      .header-actions {
        display: flex;
        gap: var(--md-sys-spacing-2);
        flex-shrink: 0;
      }

      .card-content {
        flex: 1;
        padding: var(--md-sys-spacing-5);
        overflow: auto;
      }

      .card-footer {
        display: flex;
        justify-content: flex-end;
        gap: var(--md-sys-spacing-3);
        padding: var(--md-sys-spacing-4) var(--md-sys-spacing-5);
        border-top: 1px solid var(--md-sys-color-outline-variant);
      }

      @media (prefers-color-scheme: dark) {
        .app-card.outlined {
          border-color: var(--md-sys-color-outline-variant);
        }
      }
    `,
  ],
})
export class CardComponent {
  @Input() title = '';
  @Input() subtitle = '';
  @Input() elevated = true;
  @Input() outlined = false;
  @Input() filled = false;
  @Input() interactive = false;
  @Input() elevationLevel = 1;
  @Input() header = false;
  @Input() headerActions: any[] = [];
  @Input() footerActions: any[] = [];
}
