import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Branding, Zone, Punto } from './models';

/** Cliente de la API del modelo. Base '/api' (nginx la enruta al backend). */
@Injectable({ providedIn: 'root' })
export class ApiService {
  #http = inject(HttpClient);
  #base = '/api';

  getBranding(): Observable<Branding> {
    return this.#http.get<Branding>(`${this.#base}/branding`);
  }

  getZones(): Observable<Zone[]> {
    return this.#http.get<Zone[]>(`${this.#base}/zones`);
  }

  getPredictions(zone: number): Observable<Punto[]> {
    return this.#http.get<Punto[]>(`${this.#base}/predictions`, { params: { zone } });
  }

  getHistory(zone: number): Observable<Punto[]> {
    return this.#http.get<Punto[]>(`${this.#base}/history`, { params: { zone } });
  }
}
