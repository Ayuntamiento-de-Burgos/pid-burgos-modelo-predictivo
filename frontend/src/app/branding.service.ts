import { Injectable, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { ApiService } from './api.service';
import { Branding } from './models';

/** Carga el branding en el arranque y aplica colores, título y favicon. */
@Injectable({ providedIn: 'root' })
export class BrandingService {
  #api = inject(ApiService);
  readonly branding = signal<Branding | null>(null);

  async load(): Promise<void> {
    try {
      const b = await firstValueFrom(this.#api.getBranding());
      this.branding.set(b);
      this.#applyColors(b.colores ?? {});
      if (b.destino?.nombre) document.title = b.destino.nombre;
      if (b.assets?.favicon) this.#setFavicon(b.assets.favicon);
    } catch {
      // Si falla, se mantienen los valores por defecto del CSS.
    }
  }

  #applyColors(colores: Record<string, string>): void {
    const root = document.documentElement.style;
    const map: Record<string, string> = {
      primary: '--color-primary',
      primary_dark: '--color-primary-dark',
      accent: '--color-accent',
      text: '--color-text',
      muted: '--color-muted',
      background: '--color-bg',
    };
    for (const [k, v] of Object.entries(colores)) {
      if (map[k]) root.setProperty(map[k], v);
    }
  }

  #setFavicon(href: string): void {
    const link = document.getElementById('favicon') as HTMLLinkElement | null;
    if (link) link.href = href;
  }
}
