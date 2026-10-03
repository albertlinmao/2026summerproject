import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';
import { roleGuard } from './core/guards/role.guard';

export const routes: Routes = [
  {
    path: '',
    redirectTo: '/dashboard',
    pathMatch: 'full',
  },
  {
    path: 'login',
    loadComponent: () => import('./auth/login/login.component').then((m) => m.LoginComponent),
  },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    loadComponent: () => import('./dashboards/shell/shell.component').then((m) => m.ShellComponent),
    children: [
      {
        path: '',
        redirectTo: 'coach',
        pathMatch: 'full',
      },
      {
        path: 'results',
        canActivate: [roleGuard],
        data: { roles: ['coach', 'admin'] },
        loadComponent: () =>
          import('./dashboards/results/results-browser.component').then(
            (m) => m.ResultsBrowserComponent
          ),
      },
      {
        path: 'coach',
        canActivate: [roleGuard],
        data: { roles: ['coach', 'admin'] },
        loadComponent: () =>
          import('./dashboards/coach-dashboard.component').then(
            (m) => m.CoachDashboardComponent
          ),
      },
      {
        path: 'swimmer',
        canActivate: [roleGuard],
        data: { roles: ['swimmer'] },
        loadComponent: () =>
          import('./dashboards/swimmer/swimmer-dashboard.component').then(
            (m) => m.SwimmerDashboardComponent
          ),
      },
      {
        path: 'parent',
        canActivate: [roleGuard],
        data: { roles: ['parent'] },
        loadComponent: () =>
          import('./dashboards/parent/parent-dashboard.component').then(
            (m) => m.ParentDashboardComponent
          ),
      },
      {
        path: 'athlete-figure',
        canActivate: [roleGuard],
        data: { roles: ['coach', 'admin'] },
        loadComponent: () =>
          import('./dashboards/athlete-figure-dashboard/athlete-figure-dashboard.component').then(
            (m) => m.AthleteFigureDashboardComponent
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: '/dashboard',
  },
];
