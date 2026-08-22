import { Component, signal, inject } from '@angular/core';

import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';
import { ButtonComponent } from '../../shared/ui/button.component';
import { TypographyComponent } from '../../shared/ui/typography.component';
import { CardComponent } from '../../shared/ui/card.component';
import { ErrorDisplayComponent } from '../../shared/ui/error-display.component';
import { IconComponent } from '../../shared/ui/icon.component';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    FormsModule,
    ButtonComponent,
    TypographyComponent,
    CardComponent,
    ErrorDisplayComponent,
    IconComponent,
  ],
  template: `
    <div class="login-page">
      <div class="login-container">
        <app-card class="login-card" [elevated]="true">
          <div class="login-header">
            <app-icon name="trophy" size="xlarge" class="login-icon"></app-icon>
            <app-typography variant="headline-medium" color="primary">
              Artistic Swimming Analytics
            </app-typography>
            <app-typography variant="body-large" color="on-surface-variant">
              Sign in to your dashboard
            </app-typography>
          </div>

          @if (errorMessage()) {
            <app-error-display
              [message]="errorMessage()"
              [inline]="false"
              [actions]="dismissErrorActions"
            ></app-error-display>
          }

          <form (ngSubmit)="onSubmit()" #loginForm="ngForm" class="login-form">
            <div class="form-field">
              <label for="email" class="field-label">Email</label>
              <input
                id="email"
                type="email"
                class="field-input"
                [(ngModel)]="email"
                name="email"
                required
                email
                autocomplete="email"
                placeholder="coach@example.com"
                [disabled]="isLoading()"
              />
            </div>

            <div class="form-field">
              <label for="password" class="field-label">Password</label>
              <input
                id="password"
                type="password"
                class="field-input"
                [(ngModel)]="password"
                name="password"
                required
                autocomplete="current-password"
                placeholder="Enter your password"
                [disabled]="isLoading()"
              />
            </div>

            <app-button
              type="submit"
              variant="filled"
              size="large"
              [fullWidth]="true"
              [loading]="isLoading()"
              [disabled]="!loginForm.form.valid || isLoading()"
            >
              <app-icon name="arrow-forward" size="small"></app-icon>
              Sign In
            </app-button>
          </form>

          <div class="login-footer">
            <app-typography variant="body-small" color="on-surface-variant">
              Demo mode - any credentials work
            </app-typography>
          </div>
        </app-card>
      </div>
    </div>
  `,
  styles: [
    `
      .login-page {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: var(--md-sys-spacing-6);
        background: var(--md-sys-color-background);
      }

      .login-container {
        width: 100%;
        max-width: 400px;
      }

      .login-card {
        padding: var(--md-sys-spacing-2);
      }

      .login-header {
        text-align: center;
        margin-bottom: var(--md-sys-spacing-6);
      }

      .login-icon {
        color: var(--md-sys-color-primary);
        margin-bottom: var(--md-sys-spacing-3);
      }

      .login-form {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-4);
      }

      .form-field {
        display: flex;
        flex-direction: column;
        gap: var(--md-sys-spacing-1);
      }

      .field-label {
        font-size: var(--md-sys-label-medium-size);
        font-weight: var(--md-sys-label-medium-weight);
        color: var(--md-sys-color-on-surface-variant);
      }

      .field-input {
        padding: var(--md-sys-spacing-3) var(--md-sys-spacing-4);
        font-size: var(--md-sys-body-large-size);
        font-family: var(--md-sys-font-family-primary);
        border: 1px solid var(--md-sys-color-outline-variant);
        border-radius: var(--md-sys-corner-medium);
        background: var(--md-sys-color-surface);
        color: var(--md-sys-color-on-surface);
        transition:
          border-color var(--md-sys-motion-duration-short-2),
          box-shadow var(--md-sys-motion-duration-short-2);
      }

      .field-input:focus {
        outline: none;
        border-color: var(--md-sys-color-primary);
        box-shadow: 0 0 0 2px var(--md-sys-color-primary-container);
      }

      .field-input:disabled {
        opacity: 0.6;
        cursor: not-allowed;
      }

      .field-input::placeholder {
        color: var(--md-sys-color-on-surface-variant);
        opacity: 0.6;
      }

      .login-footer {
        text-align: center;
        margin-top: var(--md-sys-spacing-4);
        padding-top: var(--md-sys-spacing-4);
        border-top: 1px solid var(--md-sys-color-outline-variant);
      }
    `,
  ],
})
export class LoginComponent {
  private authService = inject(AuthService);

  email = '';
  password = '';
  isLoading = signal(false);
  errorMessage = signal('');

  get dismissErrorActions(): Array<{
    label: string;
    variant: 'text';
    handler: (event: MouseEvent) => void;
  }> {
    return [ErrorDisplayComponent.dismissAction(() => this.errorMessage.set(''))];
  }

  onSubmit(): void {
    this.errorMessage.set('');
    this.isLoading.set(true);

    this.authService.login({ email: this.email, password: this.password });

    // The auth service handles navigation, but we need to handle errors
    // In a real app, this would be an observable
    setTimeout(() => {
      if (this.isLoading()) {
        this.isLoading.set(false);
      }
    }, 1000);
  }
}
