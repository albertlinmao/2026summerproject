import {
  Component,
  Input,
  AfterViewInit,
  OnDestroy,
  ViewChild,
  ElementRef,
  NgZone,
  inject,
} from '@angular/core';
import * as echarts from 'echarts/core';
import { RadarChart as ERadarChart } from 'echarts/charts';
import { TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([ERadarChart, TooltipComponent, LegendComponent, CanvasRenderer]);

interface FigureScore {
  figure_name: string;
  score: number;
  max_score: number;
}

@Component({
  selector: 'app-radar-chart',
  standalone: true,
  template: `
    <div class="card radar-card">
      <h3 class="heading">Figure Scores</h3>
      <div #chartContainer class="chart-container"></div>
      <p *ngIf="!figureScores?.length" class="empty-state">No figure score data available.</p>
    </div>
  `,
  styles: [`
    .radar-card {
      gap: var(--spacing-md);
    }
    .heading {
      color: var(--primary-navy);
      margin: 0;
      padding-bottom: var(--spacing-md);
      border-bottom: 2px solid var(--surface-color);
    }
    .chart-container {
      width: 100%;
      height: 350px;
      min-height: 300px;
    }
    .empty-state {
      color: var(--text-secondary);
      font-style: italic;
      text-align: center;
      padding: var(--spacing-xl) 0;
    }
  `]
})
export class RadarChartComponent implements AfterViewInit, OnDestroy {
  @Input() figureScores: FigureScore[] = [];
  @ViewChild('chartContainer', { static: true }) chartContainer!: ElementRef<HTMLDivElement>;

  private zone = inject(NgZone);
  private chart: echarts.ECharts | null = null;
  private resizeObserver: ResizeObserver | null = null;

  ngAfterViewInit(): void {
    this.zone.runOutsideAngular(() => {
      this.initChart();
    });
  }

  ngOnDestroy(): void {
    this.resizeObserver?.disconnect();
    this.chart?.dispose();
  }

  private initChart(): void {
    const el = this.chartContainer.nativeElement;
    this.chart = echarts.init(el, undefined, { renderer: 'canvas' });

    this.resizeObserver = new ResizeObserver(() => {
      this.chart?.resize();
    });
    this.resizeObserver.observe(el);

    this.updateChart();
  }

  private updateChart(): void {
    if (!this.chart || !this.figureScores?.length) return;

    const indicators = this.figureScores.map((fs) => ({
      name: fs.figure_name,
      max: fs.max_score,
    }));

    const scores = this.figureScores.map((fs) => fs.score);

    const navy = getComputedStyle(document.documentElement)
      .getPropertyValue('--primary-navy')
      .trim() || '#0A2342';
    const teal = getComputedStyle(document.documentElement)
      .getPropertyValue('--primary-teal')
      .trim() || '#178082';

    this.chart.setOption({
      tooltip: {
        trigger: 'item',
      },
      radar: {
        indicator: indicators,
        shape: 'circle',
        radius: '65%',
        nameGap: 12,
        axisName: {
          color: navy,
          fontFamily: 'Inter, sans-serif',
          fontSize: 12,
        },
        axisLine: {
          lineStyle: { color: 'rgba(0, 0, 0, 0.1)' },
        },
        splitArea: {
          areaStyle: {
            color: ['rgba(23, 128, 130, 0.02)', 'rgba(23, 128, 130, 0.06)'],
          },
        },
        splitLine: {
          lineStyle: { color: 'rgba(0, 0, 0, 0.08)' },
        },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: scores,
              name: 'Score',
              areaStyle: {
                color: 'rgba(23, 128, 130, 0.2)',
              },
              lineStyle: {
                color: teal,
                width: 2,
              },
              itemStyle: {
                color: teal,
              },
            },
          ],
        },
      ],
    });
  }
}
