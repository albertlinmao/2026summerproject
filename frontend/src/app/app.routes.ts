import { Routes } from '@angular/router';

export const routes: Routes = [
  { 
    path: 'dashboard', 
    loadComponent: () => import('./dashboards/shell/shell.component').then(m => m.ShellComponent)
  },
  { 
    path: 'sst-scores', 
    loadComponent: () => import('./dashboards/sst-scores/sst-scores.component').then(m => m.SstScoresComponent)
  },
  { path: '', redirectTo: '/dashboard', pathMatch: 'full' }
];
