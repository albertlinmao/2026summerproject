import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { tap, catchError, of } from 'rxjs';

export interface User {
  id: string;
  clubId: string;
  roles: string[];
  athleteIds: string[];
  permissions: string[];
  name?: string;
  email?: string;
}

@Injectable({
  providedIn: 'root',
})
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);

  private readonly TOKEN_KEY = 'auth_token';
  private readonly USER_KEY = 'auth_user';

  private _token = signal<string | null>(null);
  private _user = signal<User | null>(null);
  private _isLoading = signal(false);

  readonly token = computed(() => this._token());
  readonly user = computed(() => this._user());
  readonly isLoading = computed(() => this._isLoading());
  readonly isAuthenticated = computed(() => !!this._token() && !!this._user());

  constructor() {
    this.loadStoredAuth();
  }

  private loadStoredAuth(): void {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem(this.TOKEN_KEY);
      const userStr = localStorage.getItem(this.USER_KEY);

      if (token && userStr) {
        try {
          const user = JSON.parse(userStr);
          this._token.set(token);
          this._user.set(user);
        } catch {
          this.clearAuth();
        }
      }
    }
  }

  private saveAuth(token: string, user: User): void {
    this._token.set(token);
    this._user.set(user);

    if (typeof window !== 'undefined') {
      localStorage.setItem(this.TOKEN_KEY, token);
      localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    }
  }

  private clearAuth(): void {
    this._token.set(null);
    this._user.set(null);

    if (typeof window !== 'undefined') {
      localStorage.removeItem(this.TOKEN_KEY);
      localStorage.removeItem(this.USER_KEY);
    }
  }

  login(credentials: { email: string; password: string }): void {
    this._isLoading.set(true);

    // For now, simulate login with mock data
    // In production, this would call the actual auth API
    setTimeout(() => {
      const mockUser: User = {
        id: 'mock-user-id',
        clubId: 'mock-club-id',
        roles: ['Coach'],
        athleteIds: [],
        permissions: ['read:dashboard', 'read:analytics'],
        name: 'Coach User',
        email: credentials.email,
      };

      const mockToken = 'mock-jwt-token-' + Date.now();
      this.saveAuth(mockToken, mockUser);
      this._isLoading.set(false);

      // Navigate to dashboard
      this.router.navigate(['/dashboard']);
    }, 500);
  }

  logout(): void {
    this.clearAuth();
    this.router.navigate(['/login']);
  }

  hasRole(role: string): boolean {
    return this._user()?.roles.includes(role) ?? false;
  }

  hasAnyRole(roles: string[]): boolean {
    const userRoles = this._user()?.roles ?? [];
    return roles.some((role) => userRoles.includes(role));
  }

  hasPermission(permission: string): boolean {
    return this._user()?.permissions.includes(permission) ?? false;
  }

  getClubId(): string | null {
    return this._user()?.clubId ?? null;
  }

  getAthleteIds(): string[] {
    return this._user()?.athleteIds ?? [];
  }

  // For development: quick role switching
  setMockRole(role: string): void {
    const user = this._user();
    if (user) {
      this.saveAuth(this._token()!, { ...user, roles: [role] });
    }
  }
}
