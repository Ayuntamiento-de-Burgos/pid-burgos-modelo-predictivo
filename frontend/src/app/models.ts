export interface Branding {
  destino: { nombre: string; nombre_corto?: string; descripcion?: string };
  colores: Record<string, string>;
  assets: { logo: string; login_background?: string; favicon?: string };
  textos: Record<string, string>;
  enlaces?: Record<string, string>;
}

export interface Zone {
  num: number;
  nombre: string;
  label: string;
}

export interface Punto {
  timestamp: string;
  zone_num: number;
  zone_name: string;
  visitor_prediction?: number;
  visitors?: number;
}
