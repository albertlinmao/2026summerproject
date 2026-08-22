import {
  Component,
  Input,
  signal,
  computed,
  OnDestroy,
  ChangeDetectionStrategy,
} from '@angular/core';

import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-routine-timer',
  standalone: true,
  imports: [FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card timer-card">
      <h3 class="card-heading">Routine Timer</h3>

      <div class="timer-display-wrapper" [class.flash-alert]="isAlerting()">
        <div class="score-display timer-value font-data" [class.alert-high]="isAlerting()">
          {{ formattedTime() }}
        </div>
      </div>

      <div class="duration-input-row">
        <label class="duration-label" for="durationInput">Duration (sec)</label>
        <input
          id="durationInput"
          type="number"
          class="input-field duration-field font-data"
          [ngModel]="totalDuration()"
          (ngModelChange)="onDurationChange($event)"
          min="1"
          max="600"
          [disabled]="isRunning()"
        />
      </div>

      <div class="controls-row">
        @if (!isRunning()) {
          <button class="control-btn play-btn" (click)="start()" aria-label="Start timer">
            <span class="material-icon">play_arrow</span>
          </button>
        } @else {
          <button class="control-btn pause-btn" (click)="pause()" aria-label="Pause timer">
            <span class="material-icon">pause</span>
          </button>
        }

        <button
          class="control-btn reset-btn"
          (click)="reset()"
          [disabled]="remainingSeconds() === totalDuration() && !isRunning()"
          aria-label="Reset timer"
        >
          <span class="material-icon">restart_alt</span>
        </button>
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        height: 100%;
      }

      .timer-card {
        height: 100%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-lg);
        text-align: center;
      }

      .card-heading {
        margin: 0;
        color: var(--primary-navy);
        align-self: flex-start;
      }

      .timer-display-wrapper {
        padding: var(--spacing-md) var(--spacing-xl);
        border-radius: var(--border-radius);
        transition: background 0.3s;
      }

      .timer-display-wrapper.flash-alert {
        animation: flashPulse 0.6s ease-in-out infinite;
      }

      .timer-value {
        font-family: var(--font-data);
        font-size: clamp(2rem, 5vw, 4rem);
        font-variant-numeric: tabular-nums;
        letter-spacing: 2px;
        user-select: none;
      }

      .duration-input-row {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
      }

      .duration-label {
        font-size: 0.85rem;
        color: var(--text-secondary);
        white-space: nowrap;
      }

      .input-field {
        padding: 0.6rem 0.75rem;
        border: 1px solid var(--text-secondary);
        border-radius: 8px;
        font-family: var(--font-data);
        background: transparent;
        color: var(--text-primary);
        width: 80px;
        text-align: center;
        font-size: 0.95rem;
      }

      .input-field:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .controls-row {
        display: flex;
        gap: var(--spacing-md);
      }

      .control-btn {
        min-width: 56px;
        min-height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        border: none;
        border-radius: 50%;
        cursor: pointer;
        transition:
          background 0.15s,
          transform 0.1s;
      }

      .control-btn:active {
        transform: scale(0.95);
      }

      .control-btn:disabled {
        opacity: 0.35;
        cursor: not-allowed;
        transform: none;
      }

      .play-btn {
        background: var(--primary-teal);
        color: #fff;
      }

      .play-btn:hover:not(:disabled) {
        background: #12666a;
      }

      .pause-btn {
        background: var(--accent-gold);
        color: var(--primary-navy);
      }

      .pause-btn:hover:not(:disabled) {
        background: #e6bc5c;
      }

      .reset-btn {
        background: var(--surface-color);
        color: var(--text-primary);
      }

      .reset-btn:hover:not(:disabled) {
        background: #e9ecef;
      }

      .material-icon {
        font-size: 28px;
        font-family: 'Material Icons';
        line-height: 1;
      }

      @keyframes flashPulse {
        0%,
        100% {
          background: transparent;
        }
        50% {
          background: rgba(255, 107, 107, 0.15);
        }
      }
    `,
  ],
})
export class RoutineTimerComponent implements OnDestroy {
  @Input()
  set durationSeconds(value: number) {
    const clamped = Math.max(1, Math.min(600, value || 120));
    this.totalDuration.set(clamped);
    if (!this.isRunning()) {
      this.remainingSeconds.set(clamped);
    }
  }

  totalDuration = signal(120);
  remainingSeconds = signal(120);
  isRunning = signal(false);
  isAlerting = computed(() => this.remainingSeconds() <= 0 && !this.isRunning());

  formattedTime = computed(() => {
    const total = Math.max(0, this.remainingSeconds());
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  });

  private intervalId: ReturnType<typeof setInterval> | null = null;

  ngOnDestroy(): void {
    this.clearTimer();
  }

  start(): void {
    if (this.isRunning()) return;
    if (this.remainingSeconds() <= 0) {
      this.remainingSeconds.set(this.totalDuration());
    }

    this.isRunning.set(true);
    this.intervalId = setInterval(() => {
      const next = this.remainingSeconds() - 1;
      this.remainingSeconds.set(next);

      if (next <= 0) {
        this.clearTimer();
        this.isRunning.set(false);
      }
    }, 1000);
  }

  pause(): void {
    this.clearTimer();
    this.isRunning.set(false);
  }

  reset(): void {
    this.clearTimer();
    this.isRunning.set(false);
    this.remainingSeconds.set(this.totalDuration());
  }

  onDurationChange(value: number): void {
    const clamped = Math.max(1, Math.min(600, value || 120));
    this.totalDuration.set(clamped);
    if (!this.isRunning()) {
      this.remainingSeconds.set(clamped);
    }
  }

  private clearTimer(): void {
    if (this.intervalId !== null) {
      clearInterval(this.intervalId);
      this.intervalId = null;
    }
  }
}
