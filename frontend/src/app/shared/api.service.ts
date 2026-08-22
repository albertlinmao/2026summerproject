import { Injectable } from '@angular/core';

@Injectable({
  providedIn: 'root',
})
export class ApiService {
  constructor() {}

  get(endpoint: string) {
    // Retrieve token from local storage or use a fallback for local testing
    const token = localStorage.getItem('auth_token') || 'test-jwt-token';

    return fetch(`/api${endpoint}`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    });
  }
}
