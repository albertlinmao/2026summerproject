import { Component, inject } from '@angular/core';

import { RouterOutlet, RouterLink, RouterLinkActive } from '@angular/router';
import { MatSidenavModule } from '@angular/material/sidenav';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDividerModule } from '@angular/material/divider';
import { MatListModule } from '@angular/material/list';
import { ThemeService } from '../../shared/theme/theme.service';
import { AuthService } from '../../core/services/auth.service';
import { IconComponent } from '../../shared/ui/icon.component';
import { TypographyComponent } from '../../shared/ui/typography.component';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatSidenavModule,
    MatToolbarModule,
    MatIconModule,
    MatButtonModule,
    MatMenuModule,
    MatTooltipModule,
    MatDividerModule,
    MatListModule,
    IconComponent,
    TypographyComponent,
  ],
  template: `
    <mat-sidenav-container
      class="shell-container"
      [attr.data-theme]="themeService.effectiveTheme()"
    >
      <!-- Side Navigation -->
      <mat-sidenav
        #sidenav
        mode="side"
        [opened]="true"
        class="sidenav"
        [fixedInViewport]="true"
        [fixedTopGap]="64"
      >
        <mat-nav-list class="nav-list">
          <!-- Navigation Items -->
          @if (canAccessCoach()) {
            <a
              mat-list-item
              routerLink="/dashboard/coach"
              routerLinkActive="active"
              class="nav-item"
            >
              <app-icon matListItemIcon name="groups" size="medium"></app-icon>
              <span matListItemTitle>Coach Dashboard</span>
            </a>
          }

          @if (canAccessSwimmer()) {
            <a
              mat-list-item
              routerLink="/dashboard/swimmer"
              routerLinkActive="active"
              class="nav-item"
            >
              <app-icon matListItemIcon name="person" size="medium"></app-icon>
              <span matListItemTitle>My Progress</span>
            </a>
          }

          @if (canAccessParent()) {
            <a
              mat-list-item
              routerLink="/dashboard/parent"
              routerLinkActive="active"
              class="nav-item"
            >
              <app-icon matListItemIcon name="group" size="medium"></app-icon>
              <span matListItemTitle>My Swimmers</span>
            </a>
          }

          @if (canAccessClubAdmin()) {
            <a
              mat-list-item
              routerLink="/dashboard/club-admin"
              routerLinkActive="active"
              class="nav-item"
            >
              <app-icon matListItemIcon name="business" size="medium"></app-icon>
              <span matListItemTitle>Club Admin</span>
            </a>
          }
        </mat-nav-list>
      </mat-sidenav>

      <!-- Main Content Area -->
      <mat-sidenav-content class="main-content">
        <!-- Top Toolbar -->
        <mat-toolbar class="toolbar">
          <!-- Logo/Brand -->
          <div class="toolbar-brand" routerLink="/">
            <img src="/icons/as_dashboard_logo.png" alt="Logo" class="toolbar-brand-logo" />
            <span class="toolbar-brand-text"
              ><span class="brand-ez">ez</span> ArtisticSwimming</span
            >
          </div>

          <button
            mat-icon-button
            (click)="sidenav.toggle()"
            class="menu-button"
            aria-label="Toggle menu"
            matTooltip="Toggle navigation"
          >
            <app-icon name="menu"></app-icon>
          </button>

          <!-- Top-level Navigation Items -->
          <div class="nav-items">
            <button mat-button routerLink="/" class="nav-link">
              <app-icon name="home" style="margin-right: 4px;"></app-icon>
              Home
            </button>
            <button mat-button routerLink="/about" class="nav-link">
              <app-icon name="info" style="margin-right: 4px;"></app-icon>
              About Us
            </button>
            <button mat-button [matMenuTriggerFor]="clubsMenu" class="nav-link">
              <app-icon name="groups" style="margin-right: 4px;"></app-icon>
              Clubs
            </button>
            <button mat-button [matMenuTriggerFor]="resourcesMenu" class="nav-link">
              <app-icon name="assessment" style="margin-right: 4px;"></app-icon>
              Resources
            </button>
          </div>

          <div class="toolbar-spacer"></div>

          <!-- Theme Toggle -->
          <button
            mat-icon-button
            (click)="themeService.toggleTheme()"
            matTooltip="Toggle theme"
            class="theme-toggle"
            [attr.aria-label]="
              themeService.isDark() ? 'Switch to light mode' : 'Switch to dark mode'
            "
          >
            <app-icon [name]="themeService.isDark() ? 'light_mode' : 'dark_mode'"></app-icon>
          </button>

          <!-- Logout Button -->
          <button
            mat-button
            (click)="logout()"
            class="logout-button"
            matTooltip="Sign Out"
            style="margin-right: 8px; color: var(--md-sys-color-primary);"
          >
            <app-icon name="logout" style="margin-right: 4px; vertical-align: middle;"></app-icon>
            <span style="vertical-align: middle;">Logout</span>
          </button>

          <!-- User Menu -->
          <button
            mat-icon-button
            [matMenuTriggerFor]="userMenu"
            class="user-menu-button"
            aria-label="User menu"
          >
            <app-icon name="person" size="large"></app-icon>
          </button>

          <mat-menu #clubsMenu="matMenu">
            <button mat-menu-item routerLink="/clubs/seattle-synchro">
              <span>Seattle Synchro Swimming</span>
            </button>
            <button mat-menu-item routerLink="/clubs/santa-clara-artistic">
              <span>Santa Clara Artistic Swimming</span>
            </button>
          </mat-menu>

          <mat-menu #resourcesMenu="matMenu">
            <button mat-menu-item routerLink="/dashboard/results">
              <app-icon matMenuItemIcon name="score"></app-icon>
              <span>Competition Scores</span>
            </button>
            <button mat-menu-item routerLink="/dashboard/athlete-figure">
              <app-icon matMenuItemIcon name="trending_up"></app-icon>
              <span>Athlete Figure Trend</span>
            </button>
            <button mat-menu-item routerLink="/dashboard/results/pdf">
              <app-icon matMenuItemIcon name="picture_as_pdf"></app-icon>
              <span>Competition Result (PDF)</span>
            </button>
          </mat-menu>

          <mat-menu #userMenu="matMenu">
            <div class="user-menu-header">
              <app-typography variant="label-large" color="on-surface">{{
                authService.user()?.name || 'User'
              }}</app-typography>
              <app-typography variant="body-small" color="on-surface-variant">{{
                clubList()
              }}</app-typography>
            </div>
            <mat-divider></mat-divider>
            <button mat-menu-item (click)="logout()">
              <app-icon matMenuItemIcon name="logout"></app-icon>
              <span>Sign Out</span>
            </button>
          </mat-menu>
        </mat-toolbar>

        <!-- Page Content -->
        <main class="page-content" [attr.data-theme]="themeService.effectiveTheme()">
          <router-outlet></router-outlet>
        </main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: [
    `
      .shell-container {
        height: 100vh;
        background: var(--md-sys-color-background);
      }

      .sidenav {
        width: 280px;
        background: var(--md-sys-color-surface);
        border-right: 1px solid var(--md-sys-color-outline-variant);
        height: calc(100vh - 64px);
      }

      .nav-header {
        display: flex;
        align-items: center;
        gap: var(--md-sys-spacing-3);
        padding: var(--md-sys-spacing-4) var(--md-sys-spacing-4) var(--md-sys-spacing-2);
        border-bottom: 1px solid var(--md-sys-color-outline-variant);
      }

      .nav-brand-logo {
        height: 32px;
        width: auto;
        object-fit: contain;
      }

      .nav-brand-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .nav-list {
        padding: var(--md-sys-spacing-2) 0;
      }

      .nav-item {
        border-radius: 0;
        margin: 0 var(--md-sys-spacing-2);
        border-radius: var(--md-sys-corner-medium);
        color: var(--md-sys-color-on-surface-variant);
      }

      .nav-item:hover {
        background: var(--md-sys-color-surface-variant);
        color: var(--md-sys-color-on-surface);
      }

      .nav-item.active {
        background: var(--md-sys-color-primary-container);
        color: var(--md-sys-color-on-primary-container);
      }

      .nav-item.active app-icon {
        color: var(--md-sys-color-on-primary-container);
      }

      .nav-divider {
        margin: var(--md-sys-spacing-2) var(--md-sys-spacing-4);
      }

      .nav-section {
        margin-top: var(--md-sys-spacing-4);
      }

      .section-title {
        padding: 0 var(--md-sys-spacing-4) var(--md-sys-spacing-2);
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }

      .toolbar {
        height: 64px;
        background: var(--md-sys-color-surface);
        position: sticky;
        top: 0;
        z-index: var(--md-sys-z-index-sticky);
        align-items: flex-end;
        padding-bottom: 0;
      }

      .toolbar::before {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        width: 100%;
        height: 10px;
        background: linear-gradient(
          90deg,
          #e0f2fe 0%,
          #bae6fd 25%,
          #f0f9ff 50%,
          #7dd3fc 75%,
          #e0f2fe 100%
        );
        box-shadow:
          0 2px 4px rgba(125, 211, 252, 0.4),
          inset 0 1px 1px rgba(255, 255, 255, 0.8),
          inset 0 -1px 1px rgba(56, 189, 248, 0.3);
      }

      .toolbar::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: -100%;
        width: 200%;
        height: 10px;
        background: linear-gradient(
          90deg,
          rgba(255, 255, 255, 0) 0%,
          rgba(255, 255, 255, 0.6) 50%,
          rgba(255, 255, 255, 0) 100%
        );
        animation: liquid-flow 6s infinite linear;
        pointer-events: none;
      }

      @keyframes liquid-flow {
        0% {
          transform: translateX(0);
        }
        100% {
          transform: translateX(30%);
        }
      }

      .toolbar-brand {
        display: flex;
        align-items: flex-end;
        gap: var(--md-sys-spacing-2);
        cursor: pointer;
        padding: 0 var(--md-sys-spacing-2) 0 0;
        border-radius: var(--md-sys-corner-medium);
        transition: background 0.2s;
        height: 100%;
      }

      .toolbar-brand:hover {
        background: var(--md-sys-color-surface-variant);
      }

      .toolbar-brand-logo {
        height: 80px;
        width: 80px;
        object-fit: contain;
        margin-bottom: -20px;
        z-index: 10;
      }

      .toolbar-brand-text {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-family: 'Georgia', 'Times New Roman', serif;
        font-size: 1.5rem;
        font-weight: 600;
        letter-spacing: 0.5px;
        background: linear-gradient(
          135deg,
          var(--md-sys-color-primary),
          var(--md-sys-color-secondary)
        );
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 4px;
      }

      .brand-ez {
        font-family: 'Brush Script MT', 'Snell Roundhand', cursive;
        font-size: 2rem;
        font-weight: 400;
        letter-spacing: -1px;
      }

      .nav-items {
        display: flex;
        align-items: flex-end;
        gap: var(--md-sys-spacing-1);
        margin-bottom: 4px;
      }

      .menu-button {
        margin-right: var(--md-sys-spacing-2);
        margin-bottom: 4px;
      }

      .toolbar-spacer {
        flex: 1 1 auto;
      }

      .theme-toggle {
        margin-right: var(--md-sys-spacing-2);
      }

      .user-menu-button {
        margin-left: var(--md-sys-spacing-2);
      }

      .user-menu-header {
        padding: var(--md-sys-spacing-3) var(--md-sys-spacing-4);
      }

      .main-content {
        padding: var(--md-sys-spacing-6);
        overflow-y: auto;
        height: calc(100vh - 64px);
      }

      .page-content {
        max-width: 1400px;
        margin: 0 auto;
      }

      @media (max-width: 768px) {
        .sidenav {
          width: 100%;
          max-width: 300px;
        }
      }
    `,
  ],
})
export class ShellComponent {
  themeService = inject(ThemeService);
  authService = inject(AuthService);

  canAccessCoach(): boolean {
    return this.authService.hasAnyRole(['coach', 'admin']);
  }

  canAccessSwimmer(): boolean {
    return this.authService.hasAnyRole(['swimmer']);
  }

  canAccessParent(): boolean {
    return this.authService.hasAnyRole(['parent']);
  }

  canAccessClubAdmin(): boolean {
    return this.authService.hasAnyRole(['admin']);
  }

  clubList(): string {
    return this.authService.getClubIds().join(', ');
  }

  logout(): void {
    this.authService.logout();
  }
}
