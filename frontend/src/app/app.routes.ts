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
        path: 'coach',
        canActivate: [roleGuard],
        data: { roles: ['Coach', 'Lead Coach', 'Club Admin', 'Club Owner'] },
        loadComponent: () =>
          import('./dashboards/coach-dashboard.component').then(
            (m) => m.CoachDashboardComponent
          ),
      },
      {
        path: 'swimmer',
        canActivate: [roleGuard],
        data: { roles: ['Athlete', 'Team Captain'] },
        loadComponent: () =>
          import('./dashboards/swimmer/swimmer-dashboard.component').then(
            (m) => m.SwimmerDashboardComponent
          ),
      },
      {
        path: 'club-admin',
        canActivate: [roleGuard],
        data: { roles: ['Club Admin', 'Club Owner'] },
        loadComponent: () =>
          import('./dashboards/club-admin/club-admin-dashboard.component').then(
            (m) => m.ClubAdminDashboardComponent
          ),
      },
    ],
  },
  {
    path: '**',
    redirectTo: '/dashboard',
  },
];
