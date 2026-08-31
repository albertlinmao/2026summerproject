import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { firstValueFrom } from 'rxjs';

export interface User {
  id: string;
  clubId: string;
  roles: string[];
  athleteIds: string[];
  permissions: string[];
  name?: string;
  email?: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
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

  async login(credentials: { email: string; password: string }): Promise<void> {
    this._isLoading.set(true);

    try {
      const res = await firstValueFrom(
        this.http.post<LoginResponse>(`${environment.apiUrl}/auth/login`, credentials)
      );
      this.saveAuth(res.access_token, res.user);
      // Navigate to dashboard
      this.router.navigate(['/dashboard']);
    } finally {
      this._isLoading.set(false);
    }
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
