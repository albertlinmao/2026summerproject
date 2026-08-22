import {
  AfterViewInit,
  Component,
  ElementRef,
  NgZone,
  OnDestroy,
  OnChanges,
  Input,
  SimpleChanges,
  ViewChild,
  inject,
} from '@angular/core';

import * as echarts from 'echarts/core';
import { HeatmapChart } from 'echarts/charts';
import {
  GridComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

import { CardComponent } from '../../ui/card.component';
import { TypographyComponent } from '../../ui/typography.component';
import { LoadingSpinnerComponent } from '../../ui/loading-spinner.component';

echarts.use([HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer]);

export interface HeatmapAthleteRow {
  athlete_id: string;
  name: string;
  weaknesses: Record<string, number>;
  weakest_figure: string | null;
}

export interface FigureHeatmapData {
  club_id: string;
  figures: string[];
  athletes: HeatmapAthleteRow[];
}

/**
 * Figure weakness heatmap (Apache ECharts): athletes x figures with average
 * scores; lower scores highlight weaknesses for the coach's club.
 */
@Component({
  selector: 'app-figure-heatmap-widget',
  standalone: true,
  imports: [CardComponent, TypographyComponent, LoadingSpinnerComponent],
  template: `
    <app-card title="Figure Weakness Heatmap" subtitle="Average scores per figure — lower is weaker">
      @if (loading) {
        <app-loading-spinner label="Loading heatmap"></app-loading-spinner>
      } @else if (!heatmap || !heatmap.athletes.length) {
        <app-typography variant="body-medium" color="on-surface-variant">
          No figure data available yet.
        </app-typography>
      } @else {
        <div
          #chartContainer
          class="chart-container"
          role="img"
          [attr.aria-label]="ariaLabel()"
        ></div>
        @if (heatmap.athletes.length > maxVisibleRows) {
          <app-typography variant="body-small" color="on-surface-variant">
            Showing {{ maxVisibleRows }} of {{ heatmap.athletes.length }} athletes.
          </app-typography>
        }
      }
    </app-card>
  `,
  styles: [
    `
      .chart-container {
        width: 100%;
        height: 360px;
        min-height: 300px;
      }
    `,
  ],
})
export class FigureHeatmapWidgetComponent implements AfterViewInit, OnDestroy, OnChanges {
  @Input() heatmap: FigureHeatmapData | null = null;
  @Input() loading = false;
  @Input() maxVisibleRows = 12;

  @ViewChild('chartContainer', { static: true }) chartContainer!: ElementRef<HTMLDivElement>;

  private zone = inject(NgZone);
  private chart: echarts.ECharts | null = null;
  private resizeObserver: ResizeObserver | null = null;

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.chart = echarts.init(this.chartContainer.nativeElement, undefined, {
        renderer: 'canvas',
      });
      this.resizeObserver = new ResizeObserver(() => this.chart?.resize());
      this.resizeObserver.observe(this.chartContainer.nativeElement);
      this.render();
    });
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
  }

  ngOnChanges(_changes: SimpleChanges): void {
    if (this.chart) {
      this.zone.runOutsideAngular(() => this.render());
    }
  }

  ariaLabel(): string {
    if (!this.heatmap) {
      return 'Figure weakness heatmap';
    }
    const weakest = this.weakestOverall();
    return `Figure weakness heatmap for ${this.heatmap.athletes.length} athletes across ${this.heatmap.figures.length} figures${
      weakest ? `, weakest overall: ${weakest}` : ''
    }`;
  }

  private render(): void {
    if (!this.chart || !this.heatmap?.athletes.length) {
      return;
    }

    const rows = this.heatmap.athletes.slice(0, this.maxVisibleRows);
    const figures = this.heatmap.figures;

    const values: Array<[number, number, number]> = [];
    let min = Number.POSITIVE_INFINITY;
    let max = Number.NEGATIVE_INFINITY;
    rows.forEach((athlete, y) => {
      figures.forEach((figure, x) => {
        const value = athlete.weaknesses[figure];
        if (value != null) {
          values.push([x, y, value]);
          min = Math.min(min, value);
          max = Math.max(max, value);
        }
      });
    });
    if (!values.length) {
      return;
    }

    // Theme-aware colors read from M3 tokens.
    const styles = getComputedStyle(document.documentElement);
    const onSurface =
      styles.getPropertyValue('--md-sys-color-on-surface').trim() || '#1b1b1f';
    const outline =
      styles.getPropertyValue('--md-sys-color-outline-variant').trim() || '#c4c7d0';
    const errorColor =
      styles.getPropertyValue('--md-sys-color-error').trim() || '#ba1a1a';
    const primaryColor =
      styles.getPropertyValue('--md-sys-color-primary').trim() || '#178082';

    this.chart.setOption({
      tooltip: {
        position: 'top',
        formatter: (params: unknown) => {
          const p = params as { value: [number, number, number] };
          const athlete = rows[p.value[1]]?.name ?? '';
          const figure = figures[p.value[0]] ?? '';
          return `${athlete}<br/>${figure}: <strong>${p.value[2]}</strong>`;
        },
      },
      grid: {
        left: 140,
        bottom: 90,
        right: 24,
        top: 16,
      },
      xAxis: {
        type: 'category',
        data: figures,
        axisLabel: { rotate: 45, color: onSurface, fontSize: 11 },
        axisLine: { lineStyle: { color: outline } },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'category',
        data: rows.map((r) => r.name),
        axisLabel: { color: onSurface, fontSize: 12 },
        axisLine: { lineStyle: { color: outline } },
        axisTick: { show: false },
      },
      visualMap: {
        min,
        max,
        calculable: true,
        orient: 'horizontal',
        left: 'center',
        bottom: 0,
        textStyle: { color: onSurface },
        inRange: {
          // Low score (weakness) maps to error red; high score to primary teal.
          color: [errorColor, primaryColor],
        },
      },
      series: [
        {
          type: 'heatmap',
          data: values,
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 6, shadowColor: 'rgba(0,0,0,0.4)' } },
        },
      ],
    });
  }

  private weakestOverall(): string | null {
    let worst: { name: string; value: number } | null = null;
    for (const athlete of this.heatmap?.athletes ?? []) {
      for (const [figure, value] of Object.entries(athlete.weaknesses)) {
        if (!worst || value < worst.value) {
          worst = { name: figure, value };
        }
      }
    }
    return worst?.name ?? null;
  }
}
