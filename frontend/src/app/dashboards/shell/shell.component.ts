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
          <!-- Logo/Brand -->
          <div class="nav-header">
            <app-icon name="trophy" size="large" class="nav-brand-icon"></app-icon>
            <app-typography variant="title-large" color="on-surface" class="nav-brand-text">
              Swim Analytics
            </app-typography>
          </div>

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
          <button
            mat-icon-button
            (click)="sidenav.toggle()"
            class="menu-button"
            aria-label="Toggle menu"
            matTooltip="Toggle navigation"
          >
            <app-icon name="menu"></app-icon>
          </button>

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

          <!-- User Menu -->
          <button
            mat-icon-button
            [matMenuTriggerFor]="userMenu"
            class="user-menu-button"
            aria-label="User menu"
          >
            <app-icon name="person" size="large"></app-icon>
          </button>

          <mat-menu #userMenu="matMenu">
            <div class="user-menu-header">
              <app-typography variant="label-large" color="on-surface">{{
                authService.user()?.name || 'User'
              }}</app-typography>
              <app-typography variant="body-small" color="on-surface-variant">{{
                authService.getClubId()
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

      .nav-brand-icon {
        color: var(--md-sys-color-primary);
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
        border-bottom: 1px solid var(--md-sys-color-outline-variant);
        position: sticky;
        top: 0;
        z-index: var(--md-sys-z-index-sticky);
      }

      .menu-button {
        margin-right: var(--md-sys-spacing-2);
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
    return this.authService.hasAnyRole(['Coach', 'Lead Coach', 'Club Admin', 'Club Owner']);
  }

  canAccessSwimmer(): boolean {
    return this.authService.hasAnyRole(['Athlete', 'Team Captain']);
  }

  canAccessClubAdmin(): boolean {
    return this.authService.hasAnyRole(['Club Admin', 'Club Owner']);
  }

  logout(): void {
    this.authService.logout();
  }
}
