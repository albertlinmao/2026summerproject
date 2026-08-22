import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { PLATFORM_ID } from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

export type ThemeMode = 'light' | 'dark' | 'system';

@Injectable({
  providedIn: 'root',
})
export class ThemeService {
  private document = inject<Document>(DOCUMENT);
  private platformId = inject<object>(PLATFORM_ID);

  private readonly STORAGE_KEY = 'theme-preference';
  private readonly DATA_THEME_ATTR = 'data-theme';
  private readonly COLOR_SCHEME_ATTR = 'color-scheme';

  // Theme mode signal (user preference: light, dark, or system)
  readonly themeMode = signal<ThemeMode>('system');

  // Computed effective theme (resolved: light or dark)
  readonly effectiveTheme = signal<'light' | 'dark'>('light');

  // Whether the theme is currently dark
  readonly isDark = computed(() => this.effectiveTheme() === 'dark');

  constructor() {
    if (isPlatformBrowser(this.platformId)) {
      this.initializeTheme();
    }
  }

  private initializeTheme(): void {
    // Read persisted preference
    const stored = localStorage.getItem(this.STORAGE_KEY) as ThemeMode | null;
    if (stored) {
      this.themeMode.set(stored);
    }

    // Set up media query listener for system preference changes
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', () => this.updateEffectiveTheme());

    // Initial effective theme calculation
    this.updateEffectiveTheme();

    // Effect to persist theme mode changes
    effect(() => {
      const mode = this.themeMode();
      localStorage.setItem(this.STORAGE_KEY, mode);
      this.updateEffectiveTheme();
    });
  }

  private updateEffectiveTheme(): void {
    const mode = this.themeMode();
    let effective: 'light' | 'dark';

    if (mode === 'system') {
      effective = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    } else {
      effective = mode;
    }

    this.effectiveTheme.set(effective);
    this.applyTheme(effective);
  }

  private applyTheme(theme: 'light' | 'dark'): void {
    const html = this.document.documentElement;

    // Set data-theme attribute for CSS custom properties
    html.setAttribute(this.DATA_THEME_ATTR, theme);

    // Set color-scheme for native form controls
    html.setAttribute(this.COLOR_SCHEME_ATTR, theme);

    // Also set on body for component-level styling
    const body = this.document.body;
    body.setAttribute(this.DATA_THEME_ATTR, theme);
  }

  setThemeMode(mode: ThemeMode): void {
    this.themeMode.set(mode);
  }

  toggleTheme(): void {
    const current = this.effectiveTheme();
    this.setThemeMode(current === 'dark' ? 'light' : 'dark');
  }

  // Get CSS custom property value
  getCssVariable(name: string): string {
    return getComputedStyle(this.document.documentElement).getPropertyValue(name).trim();
  }
}
