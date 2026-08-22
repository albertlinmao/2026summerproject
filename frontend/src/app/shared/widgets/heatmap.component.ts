import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-heatmap',
  template: '<div class="heatmap-container">Heatmap chart placeholder</div>',
  standalone: true,
})
export class HeatmapComponent {
  @Input() chartData: any;
}
