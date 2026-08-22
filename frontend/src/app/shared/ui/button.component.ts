import { Component, Input, HostBinding, HostListener } from '@angular/core';

export type ButtonVariant = 'filled' | 'outlined' | 'tonal' | 'text' | 'elevated';
export type ButtonSize = 'small' | 'medium' | 'large';

@Component({
  selector: 'app-button',
  standalone: true,
  imports: [],
  template: `
    <button
      [attr.type]="type"
      class="app-button"
      [class.disabled]="disabled"
      [class.loading]="loading"
      [attr.aria-disabled]="disabled || loading"
      [attr.aria-busy]="loading"
      (click)="onClick($event)"
    >
      @if (!loading) {
        <span class="button-content">
          <ng-content></ng-content>
        </span>
      }
      @if (loading) {
        <span class="button-loading" aria-hidden="true">
          <svg class="spinner" viewBox="0 0 24 24">
            <circle
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              stroke-width="3"
              fill="none"
              stroke-dasharray="31.4 31.4"
              stroke-linecap="round"
            />
          </svg>
        </span>
      }
    </button>
  `,
  styles: [
    `
      .app-button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: var(--md-sys-spacing-2);
        font-family: var(--md-sys-font-family-primary);
        font-weight: var(--md-sys-label-large-weight);
        font-size: var(--md-sys-label-large-size);
        line-height: var(--md-sys-label-large-line-height);
        letter-spacing: var(--md-sys-label-large-letter-spacing);
        border: none;
        border-radius: var(--md-sys-corner-full);
        cursor: pointer;
        transition: all var(--md-sys-motion-duration-short-2) var(--md-sys-motion-easing-standard);
        text-decoration: none;
        white-space: nowrap;
        user-select: none;
        position: relative;
        overflow: hidden;
      }

      .app-button:focus-visible {
        outline: 2px solid var(--md-sys-color-primary);
        outline-offset: 2px;
      }

      .app-button.disabled,
      .app-button.loading {
        cursor: not-allowed;
        opacity: 0.6;
        pointer-events: none;
      }

      .button-content {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: var(--md-sys-spacing-2);
      }

      .button-loading {
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .spinner {
        width: 20px;
        height: 20px;
        animation: spin 1s linear infinite;
      }

      @keyframes spin {
        from {
          transform: rotate(0deg);
        }
        to {
          transform: rotate(360deg);
        }
      }

      /* Sizes */
      .app-button.size-small {
        padding: var(--md-sys-spacing-1) var(--md-sys-spacing-3);
        min-height: 32px;
      }

      .app-button.size-medium {
        padding: var(--md-sys-spacing-2) var(--md-sys-spacing-4);
        min-height: 40px;
      }

      .app-button.size-large {
        padding: var(--md-sys-spacing-3) var(--md-sys-spacing-6);
        min-height: 48px;
        font-size: var(--md-sys-title-medium-size);
        font-weight: var(--md-sys-title-medium-weight);
      }

      /* Variants - Filled (Primary) */
      .app-button.variant-filled {
        background: var(--md-sys-color-primary);
        color: var(--md-sys-color-on-primary);
      }

      .app-button.variant-filled:hover:not(.disabled) {
        box-shadow: var(--md-sys-elevation-2);
      }

      .app-button.variant-filled:active:not(.disabled) {
        box-shadow: var(--md-sys-elevation-1);
      }

      /* Variants - Outlined */
      .app-button.variant-outlined {
        background: transparent;
        color: var(--md-sys-color-primary);
        border: 1px solid var(--md-sys-color-primary);
      }

      .app-button.variant-outlined:hover:not(.disabled) {
        background: var(--md-sys-color-primary-container);
      }

      /* Variants - Tonal */
      .app-button.variant-tonal {
        background: var(--md-sys-color-secondary-container);
        color: var(--md-sys-color-on-secondary-container);
      }

      .app-button.variant-tonal:hover:not(.disabled) {
        box-shadow: var(--md-sys-elevation-1);
      }

      /* Variants - Text */
      .app-button.variant-text {
        background: transparent;
        color: var(--md-sys-color-primary);
      }

      .app-button.variant-text:hover:not(.disabled) {
        background: var(--md-sys-color-primary-container);
      }

      /* Variants - Elevated */
      .app-button.variant-elevated {
        background: var(--md-sys-color-surface);
        color: var(--md-sys-color-primary);
        box-shadow: var(--md-sys-elevation-1);
      }

      .app-button.variant-elevated:hover:not(.disabled) {
        box-shadow: var(--md-sys-elevation-2);
      }

      /* Full width */
      .app-button.full-width {
        width: 100%;
      }
    `,
  ],
})
export class ButtonComponent {
  @Input() variant: ButtonVariant = 'filled';
  @Input() size: ButtonSize = 'medium';
  @Input() disabled = false;
  @Input() loading = false;
  @Input() fullWidth = false;
  @Input() type: 'button' | 'submit' | 'reset' = 'button';

  @HostBinding('class.variant-filled') get isFilled() {
    return this.variant === 'filled';
  }
  @HostBinding('class.variant-outlined') get isOutlined() {
    return this.variant === 'outlined';
  }
  @HostBinding('class.variant-tonal') get isTonal() {
    return this.variant === 'tonal';
  }
  @HostBinding('class.variant-text') get isText() {
    return this.variant === 'text';
  }
  @HostBinding('class.variant-elevated') get isElevated() {
    return this.variant === 'elevated';
  }
  @HostBinding('class.size-small') get isSmall() {
    return this.size === 'small';
  }
  @HostBinding('class.size-medium') get isMedium() {
    return this.size === 'medium';
  }
  @HostBinding('class.size-large') get isLarge() {
    return this.size === 'large';
  }
  @HostBinding('class.full-width') get isFullWidth() {
    return this.fullWidth;
  }
  @HostBinding('class.disabled') get isDisabled() {
    return this.disabled || this.loading;
  }

  @HostListener('click', ['$event'])
  onClick(event: MouseEvent): void {
    if (this.disabled || this.loading) {
      event.preventDefault();
      event.stopPropagation();
    }
  }
}
