import { Component, Input, HostBinding } from '@angular/core';

export type TypographyVariant =
  | 'display-large'
  | 'display-medium'
  | 'display-small'
  | 'headline-large'
  | 'headline-medium'
  | 'headline-small'
  | 'title-large'
  | 'title-medium'
  | 'title-small'
  | 'body-large'
  | 'body-medium'
  | 'body-small'
  | 'label-large'
  | 'label-medium'
  | 'label-small';

export type TypographyColor =
  'primary' | 'secondary' | 'on-surface' | 'on-surface-variant' | 'error' | 'gold';

@Component({
  selector: 'app-typography',
  standalone: true,
  imports: [],
  template: `
    @switch (element) {
      @case ('h1') {
        <h1 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h1>
      }
      @case ('h2') {
        <h2 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h2>
      }
      @case ('h3') {
        <h3 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h3>
      }
      @case ('h4') {
        <h4 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h4>
      }
      @case ('h5') {
        <h5 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h5>
      }
      @case ('h6') {
        <h6 [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></h6>
      }
      @case ('p') {
        <p [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></p>
      }
      @case ('span') {
        <span [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></span>
      }
      @case ('div') {
        <div [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></div>
      }
      @default {
        <span [class]="hostClasses" [style.color]="colorStyle"><ng-content></ng-content></span>
      }
    }
  `,
  styles: [
    `
      :host {
        display: contents;
      }

      .typography {
        font-family: var(--md-sys-font-family-primary);
        margin: 0;
      }

      /* Display */
      .variant-display-large {
        font-size: var(--md-sys-display-large-size);
        font-weight: var(--md-sys-display-large-weight);
        line-height: var(--md-sys-display-large-line-height);
        letter-spacing: var(--md-sys-display-large-letter-spacing);
      }

      .variant-display-medium {
        font-size: var(--md-sys-display-medium-size);
        font-weight: var(--md-sys-display-medium-weight);
        line-height: var(--md-sys-display-medium-line-height);
        letter-spacing: var(--md-sys-display-medium-letter-spacing);
      }

      .variant-display-small {
        font-size: var(--md-sys-display-small-size);
        font-weight: var(--md-sys-display-small-weight);
        line-height: var(--md-sys-display-small-line-height);
        letter-spacing: var(--md-sys-display-small-letter-spacing);
      }

      /* Headline */
      .variant-headline-large {
        font-size: var(--md-sys-headline-large-size);
        font-weight: var(--md-sys-headline-large-weight);
        line-height: var(--md-sys-headline-large-line-height);
        letter-spacing: var(--md-sys-headline-large-letter-spacing);
      }

      .variant-headline-medium {
        font-size: var(--md-sys-headline-medium-size);
        font-weight: var(--md-sys-headline-medium-weight);
        line-height: var(--md-sys-headline-medium-line-height);
        letter-spacing: var(--md-sys-headline-medium-letter-spacing);
      }

      .variant-headline-small {
        font-size: var(--md-sys-headline-small-size);
        font-weight: var(--md-sys-headline-small-weight);
        line-height: var(--md-sys-headline-small-line-height);
        letter-spacing: var(--md-sys-headline-small-letter-spacing);
      }

      /* Title */
      .variant-title-large {
        font-size: var(--md-sys-title-large-size);
        font-weight: var(--md-sys-title-large-weight);
        line-height: var(--md-sys-title-large-line-height);
        letter-spacing: var(--md-sys-title-large-letter-spacing);
      }

      .variant-title-medium {
        font-size: var(--md-sys-title-medium-size);
        font-weight: var(--md-sys-title-medium-weight);
        line-height: var(--md-sys-title-medium-line-height);
        letter-spacing: var(--md-sys-title-medium-letter-spacing);
      }

      .variant-title-small {
        font-size: var(--md-sys-title-small-size);
        font-weight: var(--md-sys-title-small-weight);
        line-height: var(--md-sys-title-small-line-height);
        letter-spacing: var(--md-sys-title-small-letter-spacing);
      }

      /* Body */
      .variant-body-large {
        font-size: var(--md-sys-body-large-size);
        font-weight: var(--md-sys-body-large-weight);
        line-height: var(--md-sys-body-large-line-height);
        letter-spacing: var(--md-sys-body-large-letter-spacing);
      }

      .variant-body-medium {
        font-size: var(--md-sys-body-medium-size);
        font-weight: var(--md-sys-body-medium-weight);
        line-height: var(--md-sys-body-medium-line-height);
        letter-spacing: var(--md-sys-body-medium-letter-spacing);
      }

      .variant-body-small {
        font-size: var(--md-sys-body-small-size);
        font-weight: var(--md-sys-body-small-weight);
        line-height: var(--md-sys-body-small-line-height);
        letter-spacing: var(--md-sys-body-small-letter-spacing);
      }

      /* Label */
      .variant-label-large {
        font-size: var(--md-sys-label-large-size);
        font-weight: var(--md-sys-label-large-weight);
        line-height: var(--md-sys-label-large-line-height);
        letter-spacing: var(--md-sys-label-large-letter-spacing);
      }

      .variant-label-medium {
        font-size: var(--md-sys-label-medium-size);
        font-weight: var(--md-sys-label-medium-weight);
        line-height: var(--md-sys-label-medium-line-height);
        letter-spacing: var(--md-sys-label-medium-letter-spacing);
      }

      .variant-label-small {
        font-size: var(--md-sys-label-small-size);
        font-weight: var(--md-sys-label-small-weight);
        line-height: var(--md-sys-label-small-line-height);
        letter-spacing: var(--md-sys-label-small-letter-spacing);
      }

      /* Deck-readable: tabular-nums for scores/timers */
      .tabular-nums {
        font-variant-numeric: tabular-nums;
        font-feature-settings: 'tnum' 1;
      }

      /* Colors */
      .color-primary {
        color: var(--md-sys-color-primary);
      }
      .color-secondary {
        color: var(--md-sys-color-secondary);
      }
      .color-on-surface {
        color: var(--md-sys-color-on-surface);
      }
      .color-on-surface-variant {
        color: var(--md-sys-color-on-surface-variant);
      }
      .color-error {
        color: var(--md-sys-color-error);
      }
      .color-gold {
        color: var(--md-sys-color-gold);
      }
      .color-on-primary {
        color: var(--md-sys-color-on-primary);
      }
      .color-on-secondary {
        color: var(--md-sys-color-on-secondary);
      }
    `,
  ],
})
export class TypographyComponent {
  @Input() variant: TypographyVariant = 'body-medium';
  @Input() element: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'p' | 'span' | 'div' = 'p';
  @Input() color: TypographyColor = 'on-surface';
  @Input() tabularNums = false;
  @Input() class = '';

  get hostClasses(): string {
    return `typography variant-${this.variant} ${this.tabularNums ? 'tabular-nums' : ''} ${this.class}`;
  }

  get colorStyle(): string {
    return `var(--md-sys-color-${this.color})`;
  }
}
