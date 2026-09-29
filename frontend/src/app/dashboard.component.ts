import {
  Component, ElementRef, ViewChild, inject, signal, AfterViewInit,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { forkJoin } from 'rxjs';
import Chart from 'chart.js/auto';
import zoomPlugin from 'chartjs-plugin-zoom';
import { ApiService } from './api.service';
import { Zone, Punto } from './models';

Chart.register(zoomPlugin);

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="toolbar card">
      <div class="field">
        <label for="zona">Zona</label>
        <select id="zona" [(ngModel)]="zonaSel" (ngModelChange)="cargar()">
          <option *ngFor="let z of zonas()" [value]="z.num">{{ z.label }}</option>
        </select>
      </div>

      <div class="field">
        <label for="desde">Desde</label>
        <input id="desde" type="date" [(ngModel)]="desde" (ngModelChange)="render()" />
      </div>
      <div class="field">
        <label for="hasta">Hasta</label>
        <input id="hasta" type="date" [(ngModel)]="hasta" (ngModelChange)="render()" />
      </div>

      <button type="button" class="btn" (click)="reset()">Restablecer</button>

      <div class="kpi" *ngIf="totalPred() !== null">
        <span class="kpi__label">Afluencia prevista (rango visible)</span>
        <span class="kpi__value">{{ totalVisible() | number:'1.0-0' }}</span>
      </div>
    </div>

    <div class="card chart-card">
      <div class="chart-head">
        <h3 class="chart-title">Afluencia por hora — histórico y predicción</h3>
        <span class="chart-hint">Rueda del ratón para acercar · arrastrar para desplazar</span>
      </div>
      <div *ngIf="cargando()" class="msg">Cargando…</div>
      <div *ngIf="!cargando() && vacio()" class="msg">
        No hay datos todavía. El modelo los generará en su primera ejecución.
      </div>
      <canvas #canvas [style.display]="vacio() ? 'none' : 'block'"></canvas>
    </div>
  `,
  styles: [`
    .toolbar { display: flex; align-items: flex-end; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap; }
    .field { display: flex; flex-direction: column; gap: 0.25rem; }
    label { font-size: 0.75rem; color: var(--color-muted); }
    select, input[type="date"] { padding: 0.4rem 0.6rem; border: 1px solid #ccc; border-radius: 6px; }
    select { min-width: 240px; }
    .btn { padding: 0.45rem 0.9rem; border: 1px solid var(--color-primary); background: #fff;
           color: var(--color-primary); border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
    .btn:hover { background: var(--color-accent); }
    .kpi { margin-left: auto; text-align: right; }
    .kpi__label { display: block; font-size: 0.75rem; color: var(--color-muted); }
    .kpi__value { font-size: 1.4rem; font-weight: 700; color: var(--color-primary-dark); }
    .chart-card { min-height: 340px; }
    .chart-head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
    .chart-title { margin: 0 0 0.75rem; font-size: 1rem; color: var(--color-text); }
    .chart-hint { font-size: 0.72rem; color: var(--color-muted); }
    .msg { color: var(--color-muted); padding: 2rem 0; text-align: center; }
    canvas { width: 100% !important; max-height: 400px; }
  `],
})
export class DashboardComponent implements AfterViewInit {
  #api = inject(ApiService);
  @ViewChild('canvas') canvasRef!: ElementRef<HTMLCanvasElement>;

  zonas = signal<Zone[]>([]);
  zonaSel = 1;
  desde = '';
  hasta = '';
  cargando = signal(true);
  vacio = signal(false);
  totalPred = signal<number | null>(null);
  totalVisible = signal<number>(0);

  #hist: Punto[] = [];
  #pred: Punto[] = [];
  #chart?: Chart;

  ngAfterViewInit(): void {
    this.#api.getZones().subscribe((zs) => {
      this.zonas.set(zs);
      if (zs.length) { this.zonaSel = zs[0].num; this.cargar(); }
      else { this.cargando.set(false); this.vacio.set(true); }
    });
  }

  cargar(): void {
    this.cargando.set(true);
    forkJoin({
      hist: this.#api.getHistory(+this.zonaSel),
      pred: this.#api.getPredictions(+this.zonaSel),
    }).subscribe({
      next: ({ hist, pred }) => {
        this.#hist = hist;
        this.#pred = pred;
        this.totalPred.set(pred.reduce((s, p) => s + (p.visitor_prediction ?? 0), 0));
        this.vacio.set(hist.length === 0 && pred.length === 0);
        this.cargando.set(false);
        this.render();
      },
      error: () => { this.cargando.set(false); this.vacio.set(true); },
    });
  }

  reset(): void {
    this.desde = '';
    this.hasta = '';
    this.#chart?.resetZoom();
    this.render();
  }

  render(): void {
    if (this.vacio()) return;
    const d0 = this.desde ? new Date(this.desde + 'T00:00:00') : null;
    const d1 = this.hasta ? new Date(this.hasta + 'T23:59:59') : null;
    const enRango = (ts: string) => {
      const t = new Date(ts);
      return (!d0 || t >= d0) && (!d1 || t <= d1);
    };
    const hist = this.#hist.filter((p) => enRango(p.timestamp));
    const pred = this.#pred.filter((p) => enRango(p.timestamp));
    this.totalVisible.set(pred.reduce((s, p) => s + (p.visitor_prediction ?? 0), 0));

    const labels = Array.from(new Set([
      ...hist.map((p) => p.timestamp), ...pred.map((p) => p.timestamp),
    ])).sort();
    const idx = new Map(labels.map((l, i) => [l, i]));
    const serie = (pts: Punto[], key: 'visitors' | 'visitor_prediction') => {
      const arr: (number | null)[] = new Array(labels.length).fill(null);
      for (const p of pts) arr[idx.get(p.timestamp)!] = (p[key] as number) ?? null;
      return arr;
    };
    const css = getComputedStyle(document.documentElement);
    const primary = css.getPropertyValue('--color-primary').trim() || '#4b8312';
    const dark = css.getPropertyValue('--color-primary-dark').trim() || '#264a03';

    this.#chart?.destroy();
    this.#chart = new Chart(this.canvasRef.nativeElement, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'Histórico', data: serie(hist, 'visitors'), borderColor: dark,
            backgroundColor: dark, pointRadius: 0, tension: 0.3 },
          { label: 'Predicción', data: serie(pred, 'visitor_prediction'), borderColor: primary,
            backgroundColor: primary, borderDash: [5, 4], pointRadius: 0, tension: 0.3 },
        ],
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        scales: { x: { ticks: { maxTicksLimit: 12, autoSkip: true } }, y: { beginAtZero: true } },
        plugins: {
          legend: { position: 'top' },
          zoom: {
            zoom: {
              wheel: { enabled: true },
              pinch: { enabled: true },
              drag: { enabled: false },
              mode: 'x',
            },
            pan: { enabled: true, mode: 'x' },
            limits: { x: { minRange: 6 } },
          },
        },
      },
    });
  }
}
