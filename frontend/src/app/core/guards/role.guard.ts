import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService, toCoarseRole } from '../services/auth.service';

export const roleGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  // Route data may still name a display title; fold it to the coarse role.
  const requiredRoles = (route.data?.['roles'] as string[] | undefined)?.map(toCoarseRole);

  if (!requiredRoles || requiredRoles.length === 0) {
    return true;
  }

  if (authService.hasAnyRole(requiredRoles)) {
    return true;
  }

  // Redirect to dashboard with error
  router.navigate(['/dashboard'], {
    queryParams: { error: 'insufficient_permissions' },
  });
  return false;
};
