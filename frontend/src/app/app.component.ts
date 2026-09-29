import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BrandingService } from './branding.service';
import { DashboardComponent } from './dashboard.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, DashboardComponent],
  template: `
    <header class="topbar">
      <div class="topbar__brand">
        <img
          *ngIf="branding()?.assets?.logo as logo"
          [src]="logo"
          alt="logo"
          class="topbar__logo"
        />
        <div>
          <h1 class="topbar__title">
            {{ branding()?.destino?.nombre ?? 'Modelo Predictivo' }}
          </h1>
          <p class="topbar__subtitle">
            {{ branding()?.destino?.descripcion ?? '' }}
          </p>
        </div>
      </div>
    </header>

    <main class="content">
      <app-dashboard></app-dashboard>
    </main>

    <footer class="footer">
      {{ branding()?.textos?.['footer'] ?? '' }}
    </footer>
  `,
  styles: [`
    .topbar {
      display: flex; align-items: center;
      padding: 0.75rem 1.5rem;
      background: var(--color-primary-dark);
      color: #fff;
    }
    .topbar__brand { display: flex; align-items: center; gap: 1rem; }
    .topbar__logo { height: 40px; width: auto; background: #fff; border-radius: 4px; padding: 2px; }
    .topbar__title { margin: 0; font-size: 1.2rem; font-weight: 700; }
    .topbar__subtitle { margin: 0; font-size: 0.8rem; opacity: 0.85; }
    .content { max-width: 1100px; margin: 1.5rem auto; padding: 0 1rem; }
    .footer { text-align: center; padding: 1rem; color: var(--color-muted); font-size: 0.8rem; }
  `],
})
export class AppComponent {
  #brandingSvc = inject(BrandingService);
  branding = this.#brandingSvc.branding;
}
