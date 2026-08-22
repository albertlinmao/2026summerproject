import { Injectable, inject } from '@angular/core';
import {
  HttpClient,
  HttpErrorResponse,
  HttpHeaders,
  HttpInterceptor,
  HttpInterceptorFn,
  HttpRequest,
  HttpHandlerFn,
  HttpEvent,
} from '@angular/common/http';
import { Observable, throwError, BehaviorSubject, timer, of } from 'rxjs';
import { catchError, retry, switchMap, filter, take } from 'rxjs/operators';
import { environment } from '../../../environments/environment';

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  details?: any;
  timestamp: string;
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

@Injectable({
  providedIn: 'root',
})
export class ApiClientService {
  private http = inject(HttpClient);

  private readonly baseUrl = environment.apiUrl || '/api';
  private refreshTokenSubject = new BehaviorSubject<string | null>(null);
  private isRefreshing = false;

  private getHeaders(): HttpHeaders {
    const token = this.getAuthToken();
    let headers = new HttpHeaders({
      'Content-Type': 'application/json',
    });

    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }

    return headers;
  }

  private getAuthToken(): string | null {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('auth_token');
    }
    return null;
  }

  private setAuthToken(token: string): void {
    if (typeof window !== 'undefined') {
      localStorage.setItem('auth_token', token);
    }
  }

  private clearAuthToken(): void {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
    }
  }

  // Generic request methods
  get<T>(endpoint: string, params?: any): Observable<ApiResponse<T>> {
    return this.request<T>('GET', endpoint, null, params);
  }

  post<T>(endpoint: string, body: any): Observable<ApiResponse<T>> {
    return this.request<T>('POST', endpoint, body);
  }

  put<T>(endpoint: string, body: any): Observable<ApiResponse<T>> {
    return this.request<T>('PUT', endpoint, body);
  }

  patch<T>(endpoint: string, body: any): Observable<ApiResponse<T>> {
    return this.request<T>('PATCH', endpoint, body);
  }

  delete<T>(endpoint: string): Observable<ApiResponse<T>> {
    return this.request<T>('DELETE', endpoint);
  }

  private request<T>(
    method: string,
    endpoint: string,
    body?: any,
    params?: any
  ): Observable<ApiResponse<T>> {
    const url = `${this.baseUrl}${endpoint}`;

    return this.http
      .request<ApiResponse<T>>(method, url, {
        headers: this.getHeaders(),
        body,
        params,
      })
      .pipe(
        retry({
          count: 2,
          delay: (error: HttpErrorResponse, retryCount: number) => {
            if (error.status === 429 || error.status >= 500) {
              return timer(Math.min(1000 * Math.pow(2, retryCount), 10000));
            }
            throw error;
          },
        }),
        catchError((error: HttpErrorResponse) => this.handleError(error))
      );
  }

  private handleError(error: HttpErrorResponse): Observable<never> {
    let errorMessage = 'An unexpected error occurred';
    let details: any = null;

    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Client error: ${error.error.message}`;
    } else {
      // Server-side error
      switch (error.status) {
        case 0:
          errorMessage = 'Network error. Please check your connection.';
          break;
        case 400:
          errorMessage = error.error?.error || 'Bad request';
          details = error.error?.details;
          break;
        case 401:
          errorMessage = 'Authentication required. Please log in.';
          this.clearAuthToken();
          // Trigger logout/redirect
          break;
        case 403:
          errorMessage = 'You do not have permission to access this resource.';
          break;
        case 404:
          errorMessage = 'Resource not found.';
          break;
        case 413:
          errorMessage = 'File size exceeds the maximum allowed limit.';
          break;
        case 422:
          errorMessage = 'Validation error';
          details = error.error?.details;
          break;
        case 429:
          errorMessage = 'Too many requests. Please try again later.';
          break;
        case 500:
          errorMessage = 'Server error. Please try again later.';
          break;
        case 503:
          errorMessage = 'Service temporarily unavailable. Please try again later.';
          break;
        default:
          errorMessage = error.error?.error || `Error ${error.status}`;
      }
    }

    return throwError(() => ({
      message: errorMessage,
      status: error.status,
      details,
      timestamp: new Date().toISOString(),
    }));
  }

  // File upload
  uploadFile(
    endpoint: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Observable<ApiResponse<any>> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http
      .post<ApiResponse<any>>(`${this.baseUrl}${endpoint}`, formData, {
        headers: new HttpHeaders({
          Authorization: `Bearer ${this.getAuthToken() || ''}`,
        }),
        reportProgress: true,
        observe: 'events',
      })
      .pipe(
        filter((event) => event.type === 4),
        switchMap((event) => of((event as any).body)),
        catchError(this.handleError.bind(this))
      );
  }

  // Download file
  downloadFile(endpoint: string): Observable<Blob> {
    return this.http
      .get(`${this.baseUrl}${endpoint}`, {
        headers: this.getHeaders(),
        responseType: 'blob',
      })
      .pipe(catchError(this.handleError.bind(this)));
  }

  // Set token (for login)
  setToken(token: string): void {
    this.setAuthToken(token);
  }

  // Clear token (for logout)
  logout(): void {
    this.clearAuthToken();
  }

  // Check if authenticated
  isAuthenticated(): boolean {
    return !!this.getAuthToken();
  }
}

// HTTP Interceptor function
export const apiInterceptor: HttpInterceptorFn = (
  req: HttpRequest<unknown>,
  next: HttpHandlerFn
) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;

  if (token) {
    const authReq = req.clone({
      headers: req.headers.set('Authorization', `Bearer ${token}`),
    });
    return next(authReq);
  }

  return next(req);
};
