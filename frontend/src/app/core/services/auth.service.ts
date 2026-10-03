import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { environment } from '../../../environments/environment';
import { firstValueFrom } from 'rxjs';

/** Coarse, club-scoped role. This is the only vocabulary that authorizes. */
export type ClubRole = 'admin' | 'coach' | 'swimmer' | 'parent' | 'official';

/**
 * Display titles carried by the old UI vocabulary. In the identity contract a
 * membership `title` is free text that never authorizes, so these are folded
 * onto the coarse role before any comparison. Single source of truth for the
 * display -> role mapping.
 */
const ROLE_ALIASES: Record<string, ClubRole> = {
  Athlete: 'swimmer',
  'Team Captain': 'swimmer',
  Coach: 'coach',
  'Lead Coach': 'coach',
  'Club Admin': 'admin',
  'Club Owner': 'admin',
  Parent: 'parent',
  Official: 'official',
};

export function toCoarseRole(role: string): ClubRole {
  return ROLE_ALIASES[role] ?? (role as ClubRole);
}

export interface User {
  id: string;
  /**
   * Mirror of the `person_id` claim, cached for display and for keying
   * person-scoped requests. Never an authorization input: roles are resolved
   * per club and enforced by the backend.
   */
  personId: string | null;
  /** Clubs with an invited/active membership. One login may span several. */
  clubIds: string[];
  /** `{ "<club_id>": ["swimmer", "coach"] }` — roles are scoped per club. */
  rolesByClub: Record<string, ClubRole[]>;
  permissions: string[];
  name?: string;
  email?: string;
}

interface LoginUserWire {
  /**
   * Raw `user` object from `POST /api/auth/login`. The API speaks the identity
   * contract's snake_case; `User` is the camelCase app model, so the two are
   * folded together in `toUser` rather than in every consumer.
   */
  person_id?: string | null;
  club_ids?: string[];
  roles_by_club?: Record<string, ClubRole[]>;
  permissions?: string[];
  name?: string;
  email?: string;
}

/**
 * Normalize the login response into the app's `User` shape.
 *
 * `person_id` is null until `scripts/user_mgmt_sync.py` has provisioned the
 * account, and `club_ids` is empty in that state, so both must survive as
 * empty rather than being defaulted into a club.
 */
function toUser(wire: LoginUserWire): User {
  const personId = wire.person_id ?? null;
  return {
    id: personId ?? '',
    personId,
    clubIds: wire.club_ids ?? [],
    rolesByClub: wire.roles_by_club ?? {},
    permissions: wire.permissions ?? [],
    name: wire.name,
    email: wire.email,
  };
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: LoginUserWire;
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
          // Normalize on read too: sessions stored before this mapping existed
          // hold the raw snake_case payload and would otherwise restore as an
          // unauthenticated-looking user with no roles.
          this._token.set(token);
          this._user.set(toUser(JSON.parse(userStr)));
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
      this.saveAuth(res.access_token, toUser(res.user));
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
    return this.hasAnyRole([role]);
  }

  /**
   * True when any of `roles` is held in any club the user is an invited or
   * active member of. Route matching only; the backend still authorizes.
   */
  hasAnyRole(roles: string[]): boolean {
    const required = roles.map(toCoarseRole);
    const rolesByClub = this._user()?.rolesByClub ?? {};
    return Object.values(rolesByClub).some((clubRoles) =>
      clubRoles.some((role) => required.includes(role))
    );
  }

  hasRoleInClub(clubId: string, role: string): boolean {
    return this._user()?.rolesByClub[clubId]?.includes(toCoarseRole(role)) ?? false;
  }

  hasPermission(permission: string): boolean {
    return this._user()?.permissions.includes(permission) ?? false;
  }

  getClubIds(): string[] {
    return this._user()?.clubIds ?? [];
  }

  // For development: quick role switching
  setMockRole(role: string): void {
    const user = this._user();
    if (user) {
      const coarse = toCoarseRole(role);
      const rolesByClub: Record<string, ClubRole[]> = {};
      for (const clubId of user.clubIds) {
        rolesByClub[clubId] = [coarse];
      }
      this.saveAuth(this._token()!, { ...user, rolesByClub });
    }
  }
}
