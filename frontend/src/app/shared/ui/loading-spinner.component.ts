import { Component, Input, HostBinding } from '@angular/core';

export type SpinnerSize = 'small' | 'medium' | 'large';
export type SpinnerColor = 'primary' | 'secondary' | 'on-surface' | 'white';

@Component({
  selector: 'app-loading-spinner',
  standalone: true,
  imports: [],
  template: `
    <div class="spinner-container" [style.width]="sizeValue" [style.height]="sizeValue">
      <svg class="spinner" viewBox="0 0 50 50" [style.color]="colorStyle" aria-hidden="true">
        <circle class="spinner-track" cx="25" cy="25" r="20" fill="none" stroke-width="4" />
        <circle
          class="spinner-progress"
          cx="25"
          cy="25"
          r="20"
          fill="none"
          stroke-width="4"
          stroke-linecap="round"
          stroke-dasharray="90 150"
        />
      </svg>
      @if (label) {
        <span class="sr-only">{{ label }}</span>
      }
    </div>
  `,
  styles: [
    `
      .spinner-container {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
      }

      .spinner {
        display: block;
        animation: rotate 1.4s linear infinite;
        transform-origin: center;
      }

      .spinner-track {
        opacity: 0.2;
      }

      .spinner-progress {
        stroke-dashoffset: 0;
      }

      @keyframes rotate {
        0% {
          transform: rotate(0deg);
        }
        100% {
          transform: rotate(360deg);
        }
      }

      .sr-only {
        position: absolute;
        width: 1px;
        height: 1px;
        padding: 0;
        margin: -1px;
        overflow: hidden;
        clip: rect(0, 0, 0, 0);
        white-space: nowrap;
        border: 0;
      }

      /* Overlay variant */
      .spinner-overlay {
        position: fixed;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(0, 0, 0, 0.3);
        z-index: var(--md-sys-z-index-modal);
        backdrop-filter: blur(2px);
      }

      .spinner-overlay .spinner-container {
        background: var(--md-sys-color-surface);
        border-radius: var(--md-sys-corner-large);
        padding: var(--md-sys-spacing-6);
        box-shadow: var(--md-sys-elevation-3);
      }
    `,
  ],
})
export class LoadingSpinnerComponent {
  @Input() size: SpinnerSize = 'medium';
  @Input() color: SpinnerColor = 'primary';
  @Input() label = 'Loading...';
  @Input() overlay = false;

  @HostBinding('class.spinner-overlay') get isOverlay() {
    return this.overlay;
  }

  get sizeValue(): string {
    switch (this.size) {
      case 'small':
        return '24px';
      case 'medium':
        return '40px';
      case 'large':
        return '56px';
      default:
        return '40px';
    }
  }

  get colorStyle(): string {
    switch (this.color) {
      case 'primary':
        return 'var(--md-sys-color-primary)';
      case 'secondary':
        return 'var(--md-sys-color-secondary)';
      case 'on-surface':
        return 'var(--md-sys-color-on-surface)';
      case 'white':
        return '#ffffff';
      default:
        return 'var(--md-sys-color-primary)';
    }
  }
}
