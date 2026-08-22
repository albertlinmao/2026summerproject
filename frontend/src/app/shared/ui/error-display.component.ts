import { Component, Input } from '@angular/core';

import { IconComponent } from './icon.component';
import { ButtonComponent } from './button.component';
import { TypographyComponent } from './typography.component';

export interface ErrorDetail {
  field?: string;
  message: string;
  type?: string;
}

@Component({
  selector: 'app-error-display',
  standalone: true,
  imports: [IconComponent, ButtonComponent, TypographyComponent],
  template: `
    <div
      class="error-display"
      [class.inline]="inline"
      [class.full-width]="fullWidth"
      role="alert"
      [attr.aria-live]="inline ? 'polite' : 'assertive'"
    >
      <div class="error-content">
        @if (showIcon) {
          <div class="error-icon">
            <app-icon [name]="iconName" [size]="'large'" [color]="'error'"> </app-icon>
          </div>
        }

        <div class="error-text">
          @if (title) {
            <app-typography variant="title-medium" [color]="'error'">{{ title }}</app-typography>
          }

          <app-typography variant="body-medium" [color]="'on-surface-variant'">{{
            message
          }}</app-typography>

          @if (details && details.length) {
            <div class="error-details">
              @for (detail of details; track detail) {
                <app-typography
                  variant="body-small"
                  [color]="'on-surface-variant'"
                  class="detail-item"
                  >{{ detail.field ? detail.field + ': ' : '' }}{{ detail.message }}</app-typography
                >
              }
            </div>
          }
        </div>
      </div>

      @if (actions.length) {
        <div class="error-actions">
          @for (action of actions; track action) {
            <app-button
              [variant]="action.variant || 'text'"
              [size]="'small'"
              (click)="action.handler($event)"
              >{{ action.label }}</app-button
            >
          }
        </div>
      }
    </div>
  `,
  styles: [
    `
      .error-display {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-3);
        padding: var(--md-sys-spacing-4);
        background: var(--md-sys-color-error-container);
        border: 1px solid var(--md-sys-color-error);
        border-radius: var(--md-sys-corner-medium);
        color: var(--md-sys-color-on-error-container);
      }

      .error-display.inline {
        flex-direction: row;
        align-items: flex-start;
      }

      .error-display.full-width {
        width: 100%;
      }

      .error-content {
        display: flex;
        gap: var(--md-sys-spacing-3);
        flex: 1;
      }

      .error-icon {
        flex-shrink: 0;
        margin-top: var(--md-sys-spacing-1);
      }

      .error-text {
        flex: 1;
        min-width: 0;
      }

      .error-text :global(app-typography) {
        margin-bottom: var(--md-sys-spacing-1);
      }

      .error-text :global(app-typography):last-child {
        margin-bottom: 0;
      }

      .detail-item {
        margin-top: var(--md-sys-spacing-1);
        padding-left: var(--md-sys-spacing-4);
        border-left: 2px solid var(--md-sys-color-error);
      }

      .error-actions {
        display: flex;
        gap: var(--md-sys-spacing-2);
        flex-wrap: wrap;
        margin-top: var(--md-sys-spacing-2);
        padding-top: var(--md-sys-spacing-2);
        border-top: 1px solid var(--md-sys-color-error);
      }

      .error-actions :global(app-button) {
        color: var(--md-sys-color-on-error-container);
      }

      /* Inline variant */
      .error-display.inline .error-content {
        flex-direction: row;
      }

      .error-display.inline .error-actions {
        margin-top: 0;
        padding-top: 0;
        border-top: none;
        margin-left: auto;
      }
    `,
  ],
})
export class ErrorDisplayComponent {
  @Input() title = '';
  @Input() message = '';
  @Input() details: ErrorDetail[] = [];
  @Input() actions: Array<{
    label: string;
    variant?: 'filled' | 'outlined' | 'tonal' | 'text';
    handler: (event: MouseEvent) => void;
  }> = [];
  @Input() inline = false;
  @Input() fullWidth = false;
  @Input() showIcon = true;
  @Input() iconName = 'error';

  // Retry action helper
  static retryAction(handler: () => void): {
    label: string;
    variant: 'text';
    handler: (event: MouseEvent) => void;
  } {
    return {
      label: 'Retry',
      variant: 'text',
      handler: () => handler(),
    };
  }

  // Dismiss action helper
  static dismissAction(onDismiss: () => void): {
    label: string;
    variant: 'text';
    handler: (event: MouseEvent) => void;
  } {
    return {
      label: 'Dismiss',
      variant: 'text',
      handler: () => onDismiss(),
    };
  }
}
