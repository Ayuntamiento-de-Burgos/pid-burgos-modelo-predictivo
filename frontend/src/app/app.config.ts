import { ApplicationConfig, APP_INITIALIZER } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';
import { BrandingService } from './branding.service';

/** Carga el branding ANTES de arrancar la app (colores, título, favicon). */
function initBranding(branding: BrandingService) {
  return () => branding.load();
}

export const appConfig: ApplicationConfig = {
  providers: [
    provideHttpClient(),
    {
      provide: APP_INITIALIZER,
      useFactory: initBranding,
      deps: [BrandingService],
      multi: true,
    },
  ],
};
