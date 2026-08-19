import {
  Component,
  Input,
  signal,
  computed,
  ElementRef,
  ViewChild,
  OnDestroy,
  ChangeDetectionStrategy,
} from '@angular/core';
import { CommonModule } from '@angular/common';

export interface VideoMarker {
  id: number;
  time_offset: number;
  marker_type: string;
  label: string;
}

@Component({
  selector: 'app-video-analysis',
  standalone: true,
  imports: [CommonModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card video-analysis-card">
      <h3 class="card-heading">Video Analysis</h3>

      <div class="video-wrapper" #videoWrapper>
        <video
          #videoRef
          [src]="videoUrl"
          preload="metadata"
          playsinline
          (loadedmetadata)="onMetadataLoaded($event)"
          (timeupdate)="onTimeUpdate()"
          (ended)="isPlaying.set(false)"
        ></video>

        <div class="controls-overlay">
          <button
            class="control-btn play-btn"
            (click)="togglePlay()"
            [attr.aria-label]="isPlaying() ? 'Pause' : 'Play'"
          >
            <span class="material-icon">{{ isPlaying() ? 'pause' : 'play_arrow' }}</span>
          </button>

          <div class="timestamp-display">
            <span class="font-data">{{ formatTime(currentTime()) }}</span>
            <span class="separator">/</span>
            <span class="font-data">{{ formatTime(duration()) }}</span>
          </div>

          <div class="progress-bar-container" (click)="seekToPosition($event)">
            <div class="progress-bar-track">
              <div
                class="progress-bar-fill"
                [style.width.%]="progressPercent()"
              ></div>
              @for (marker of markers; track marker.id) {
                <div
                  class="marker-dot"
                  [style.left.%]="markerPosition(marker)"
                  (click)="seekToMarker(marker, $event)"
                  [attr.title]="marker.label"
                >
                  <span class="marker-tooltip">{{ marker.label }}</span>
                </div>
              }
            </div>
          </div>

          <button
            class="control-btn fullscreen-btn"
            (click)="toggleFullscreen()"
            aria-label="Toggle fullscreen"
          >
            <span class="material-icon">fullscreen</span>
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [`
    :host {
      display: block;
      height: 100%;
    }

    .video-analysis-card {
      height: 100%;
      display: flex;
      flex-direction: column;
      gap: var(--spacing-md);
    }

    .card-heading {
      margin: 0;
      color: var(--primary-navy);
    }

    .video-wrapper {
      position: relative;
      flex: 1;
      min-height: 280px;
      background: var(--primary-navy);
      border-radius: var(--border-radius);
      overflow: hidden;
    }

    video {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
      background: #000;
    }

    .controls-overlay {
      position: absolute;
      bottom: 0;
      left: 0;
      right: 0;
      display: flex;
      align-items: center;
      gap: var(--spacing-sm);
      padding: var(--spacing-sm) var(--spacing-md);
      background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
      z-index: 2;
    }

    .control-btn {
      min-width: 56px;
      min-height: 56px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: transparent;
      border: none;
      color: #fff;
      cursor: pointer;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .control-btn:hover {
      background: rgba(255, 255, 255, 0.15);
    }

    .material-icon {
      font-size: 28px;
      font-family: 'Material Icons';
      line-height: 1;
    }

    .timestamp-display {
      color: rgba(255, 255, 255, 0.9);
      font-size: 0.9rem;
      white-space: nowrap;
      padding: 0 var(--spacing-sm);
      min-width: 100px;
      text-align: center;
    }

    .font-data {
      font-family: var(--font-data);
      font-variant-numeric: tabular-nums;
    }

    .separator {
      margin: 0 4px;
      opacity: 0.5;
    }

    .progress-bar-container {
      flex: 1;
      cursor: pointer;
      padding: 12px 0;
      display: flex;
      align-items: center;
    }

    .progress-bar-track {
      position: relative;
      width: 100%;
      height: 6px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 3px;
    }

    .progress-bar-fill {
      position: absolute;
      top: 0;
      left: 0;
      height: 100%;
      background: var(--primary-teal);
      border-radius: 3px;
      transition: width 0.1s linear;
    }

    .marker-dot {
      position: absolute;
      top: 50%;
      width: 12px;
      height: 12px;
      margin-left: -6px;
      margin-top: -6px;
      background: var(--accent-gold);
      border: 2px solid #fff;
      border-radius: 50%;
      cursor: pointer;
      z-index: 3;
      min-width: 24px;
      min-height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .marker-dot:hover {
      transform: scale(1.3);
      background: var(--accent-coral);
    }

    .marker-tooltip {
      position: absolute;
      bottom: calc(100% + 8px);
      left: 50%;
      transform: translateX(-50%);
      background: var(--primary-navy);
      color: #fff;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 0.75rem;
      white-space: nowrap;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.15s;
    }

    .marker-dot:hover .marker-tooltip {
      opacity: 1;
    }

    :host(.fullscreen-mode) .video-wrapper {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      border-radius: 0;
      z-index: 9999;
    }

    :host(.fullscreen-mode) .video-analysis-card {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      z-index: 9999;
      padding: 0;
      border-radius: 0;
      background: #000;
    }
  `],
})
export class VideoAnalysisComponent implements OnDestroy {
  @Input({ required: true }) videoUrl = '';
  @Input() markers: VideoMarker[] = [];

  @ViewChild('videoRef') videoRef!: ElementRef<HTMLVideoElement>;
  @ViewChild('videoWrapper') videoWrapper!: ElementRef<HTMLDivElement>;

  isPlaying = signal(false);
  currentTime = signal(0);
  duration = signal(0);
  progressPercent = computed(() =>
    this.duration() > 0 ? (this.currentTime() / this.duration()) * 100 : 0
  );

  private fullscreenChangeHandler = () => {
    if (!document.fullscreenElement) {
      this.isFullscreen.set(false);
    }
  };

  isFullscreen = signal(false);

  ngOnDestroy(): void {
    document.removeEventListener('fullscreenchange', this.fullscreenChangeHandler);
  }

  onMetadataLoaded(event: Event): void {
    const video = event.target as HTMLVideoElement;
    this.duration.set(video.duration);
  }

  onTimeUpdate(): void {
    if (this.videoRef?.nativeElement) {
      this.currentTime.set(this.videoRef.nativeElement.currentTime);
    }
  }

  togglePlay(): void {
    const video = this.videoRef?.nativeElement;
    if (!video) return;

    if (video.paused) {
      video.play();
      this.isPlaying.set(true);
    } else {
      video.pause();
      this.isPlaying.set(false);
    }
  }

  seekToPosition(event: MouseEvent): void {
    const video = this.videoRef?.nativeElement;
    if (!video || this.duration() <= 0) return;

    const target = event.currentTarget as HTMLElement;
    const rect = target.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width));
    video.currentTime = ratio * this.duration();
    this.currentTime.set(video.currentTime);
  }

  seekToMarker(marker: VideoMarker, event: MouseEvent): void {
    event.stopPropagation();
    const video = this.videoRef?.nativeElement;
    if (!video) return;

    video.currentTime = marker.time_offset;
    this.currentTime.set(marker.time_offset);
  }

  markerPosition(marker: VideoMarker): number {
    const dur = this.duration();
    if (dur <= 0) return 0;
    return (marker.time_offset / dur) * 100;
  }

  formatTime(seconds: number): string {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }

  toggleFullscreen(): void {
    const wrapper = this.videoWrapper?.nativeElement;
    if (!wrapper) return;

    if (document.fullscreenElement) {
      document.exitFullscreen();
      this.isFullscreen.set(false);
    } else {
      wrapper.requestFullscreen();
      this.isFullscreen.set(true);
      document.addEventListener('fullscreenchange', this.fullscreenChangeHandler);
    }
  }
}
