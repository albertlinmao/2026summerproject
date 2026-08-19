import { Component, signal } from "@angular/core";
import { CommonModule } from "@angular/common";

interface VideoTag {
  id: number;
  timestamp: string;
  note: string;
  type: "stroke" | "hybrid" | "timing";
}

@Component({
  selector: "app-video-correction",
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="video-card">
      <div class="header">
        <h3>Side-by-Side Video Correction</h3>
        <button class="btn btn-primary upload-btn">Upload Clip <span>(mp4, mov)</span></button>
      </div>

      <div class="video-workspace">
        <div class="player-container">
          <div class="mock-player">
            <div class="play-icon">▶</div>
            <div class="progress-bar">
              <div class="progress" style="width: 35%"></div>
              <div
                class="tag-marker"
                *ngFor="let tag of tags()"
                [style.left]="getMarkerPosition(tag.timestamp)"
              ></div>
            </div>
            <div class="time-display timer-display" style="font-size: 1.5rem; position: absolute; bottom: 8px; right: 20px;">00:14 / 02:30</div>
          </div>
        </div>

        <div class="tags-panel">
          <h4>Timestamp Tags</h4>
          <div class="add-tag">
            <input
              type="text"
              #noteInput
              placeholder="Add correction note..."
              class="input-field"
            />
            <select #typeInput class="input-field">
              <option value="stroke">Stroke</option>
              <option value="hybrid">Hybrid</option>
              <option value="timing">Timing</option>
            </select>
            <button
              class="btn btn-accent"
              (click)="
                addTag('00:14', noteInput.value, typeInput.value);
                noteInput.value = ''
              "
            >
              <span class="icon">🏷️</span> <span> Tag &#64; 0:44 </span>
            </button>
          </div>

          <ul class="tag-list">
            <li *ngFor="let tag of tags()" class="tag-item">
              <span class="time-badge">{{ tag.timestamp }}</span>
              <span class="type-badge" [ngClass]="tag.type">{{ tag.type }}</span>
              <span class="note">{{ tag.note }}</span>
            </li>
          </ul>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .video-card {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        height: 100%;
      }
      .header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid var(--surface-color);
        padding-bottom: var(--spacing-md);
      }
      .header h3 {
        margin: 0;
        color: var(--primary-navy);
      }
      .upload-btn span {
        font-size: 0.8em;
        opacity: 0.8;
      }

      .video-workspace {
        display: flex;
        gap: var(--spacing-lg);
        flex-wrap: wrap;
        height: 100%;
      }
      .player-container {
        flex: 2;
        min-width: 300px;
      }
      .mock-player {
        background: var(--primary-navy);
        height: 350px;
        border-radius: var(--border-radius);
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        position: relative;
      }
      .play-icon {
        font-size: 64px;
        color: rgba(255, 255, 255, 0.8);
        cursor: pointer;
      }
      .progress-bar {
        position: absolute;
        bottom: 40px;
        left: 20px;
        right: 20px;
        height: 8px;
        background: rgba(255,255,255,0.2);
        border-radius: 4px;
      }
      .progress {
        height: 100%;
        background: var(--primary-teal);
        border-radius: 4px;
      }
      .tag-marker {
        position: absolute;
        top: -4px;
        width: 4px;
        height: 16px;
        background: var(--accent-gold);
        border-radius: 2px;
      }
      .time-display {
        color: white;
      }

      .tags-panel {
        flex: 1;
        min-width: 250px;
        background: var(--surface-color);
        padding: var(--spacing-md);
        border-radius: var(--border-radius);
        display: flex;
        flex-direction: column;
      }
      .tags-panel h4 {
        margin-top: 0;
        margin-bottom: var(--spacing-sm);
        color: var(--text-primary);
      }
      .add-tag {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
        margin-bottom: var(--spacing-md);
      }
      .input-field {
        padding: 0.75rem;
        border: 1px solid var(--text-secondary);
        border-radius: 8px;
        font-family: var(--font-main);
        background: transparent;
        color: var(--text-primary);
      }

      .tag-list {
        list-style: none;
        padding: 0;
        margin: 0;
        overflow-y: auto;
        max-height: 250px;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-sm);
      }
      .tag-item {
        background: var(--bg-color);
        padding: var(--spacing-sm);
        border-radius: 8px;
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        font-size: 14px;
      }
      .time-badge {
        background: var(--primary-navy);
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-weight: bold;
        font-family: var(--font-data);
      }
      .type-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 11px;
        text-transform: uppercase;
        font-weight: bold;
      }
      .type-badge.stroke {
        background: var(--primary-teal);
        color: white;
      }
      .type-badge.hybrid {
        background: var(--accent-gold);
        color: var(--primary-navy);
      }
      .type-badge.timing {
        background: var(--accent-coral);
        color: white;
      }
      .note {
        flex: 1;
        color: var(--text-primary);
      }
    `,
  ],
})
export class VideoCorrectionComponent {
  tags = signal<VideoTag[]>([
    { id: 1, timestamp: "00:05", note: "Late entry on hybrid", type: "timing" },
    {
      id: 2,
      timestamp: "01:12",
      note: "Eggbeater height too low",
      type: "stroke",
    },
  ]);

  addTag(timestamp: string, note: string, type: string) {
    if (!note) return;
    this.tags.update((t) => [
      ...t,
      {
        id: Date.now(),
        timestamp,
        note,
        type: type as "stroke" | "hybrid" | "timing",
      },
    ]);
  }

  getMarkerPosition(timeStr: string): string {
    // Mock calculation for visual marker position on the progress bar
    const parts = timeStr.split(":");
    const seconds = parseInt(parts[0]) * 60 + parseInt(parts[1]);
    const totalSeconds = 150; // 02:30
    return `${(seconds / totalSeconds) * 100}%`;
  }
}
