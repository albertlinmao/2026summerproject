import { Component, Output, EventEmitter, signal, ChangeDetectionStrategy } from '@angular/core';

export interface UploadCompleteEvent {
  id: string;
  storage_path: string;
  duration_seconds: number;
}

const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024; // 2 GB
const VALID_MIME_PREFIX = 'video/';

@Component({
  selector: 'app-video-upload',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="card upload-card">
      <h3 class="card-heading">Upload Video</h3>

      @if (errorMessage()) {
        <div class="error-banner">
          <span class="material-icon error-icon">error</span>
          <span>{{ errorMessage() }}</span>
        </div>
      }

      @if (uploadProgress() !== null) {
        <div class="progress-section">
          <div class="progress-track">
            <div class="progress-fill" [style.width.%]="uploadProgress()"></div>
          </div>
          <span class="progress-label font-data">{{ uploadProgress() }}%</span>
        </div>
      }

      @if (!selectedFile()) {
        <div
          class="drop-zone"
          (dragover)="onDragOver($event)"
          (dragleave)="onDragLeave($event)"
          (drop)="onDrop($event)"
          [class.drag-over]="isDragging()"
          (click)="fileInput.click()"
        >
          <span class="material-icon drop-icon">cloud_upload</span>
          <p class="drop-text">Drag & drop a video file here</p>
          <p class="drop-subtext">or click to browse</p>
          <p class="drop-hint">MP4, MOV &middot; Max 2 GB</p>
        </div>
      } @else {
        <div class="file-info">
          <span class="material-icon file-icon">videocam</span>
          <div class="file-details">
            <span class="file-name">{{ selectedFile()!.name }}</span>
            <span class="file-size font-data">{{ formatFileSize(selectedFile()!.size) }}</span>
          </div>
          <button class="control-btn" (click)="clearSelection()" aria-label="Remove file">
            <span class="material-icon">close</span>
          </button>
        </div>

        <button
          class="btn btn-primary upload-btn"
          (click)="startUpload()"
          [disabled]="uploadProgress() !== null"
        >
          @if (uploadProgress() !== null) {
            <span class="material-icon spinning">sync</span>
            <span>Uploading&hellip;</span>
          } @else {
            <span class="material-icon">cloud_upload</span>
            <span>Upload</span>
          }
        </button>
      }

      <input #fileInput type="file" accept="video/*" hidden (change)="onFileSelected($event)" />
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        height: 100%;
      }

      .upload-card {
        height: 100%;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .card-heading {
        margin: 0;
        color: var(--primary-navy);
      }

      .error-banner {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm) var(--spacing-md);
        background: rgba(255, 107, 107, 0.12);
        border: 1px solid var(--accent-coral);
        border-radius: 8px;
        color: var(--accent-coral);
        font-weight: 500;
      }

      .error-icon {
        font-size: 20px;
        font-family: 'Material Icons';
      }

      .progress-section {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
      }

      .progress-track {
        flex: 1;
        height: 8px;
        background: var(--surface-color);
        border-radius: 4px;
        overflow: hidden;
      }

      .progress-fill {
        height: 100%;
        background: var(--primary-teal);
        border-radius: 4px;
        transition: width 0.25s ease;
      }

      .progress-label {
        font-family: var(--font-data);
        font-size: 0.9rem;
        color: var(--text-secondary);
        min-width: 40px;
        text-align: right;
      }

      .drop-zone {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-xl);
        border: 2px dashed var(--text-secondary);
        border-radius: var(--border-radius);
        cursor: pointer;
        transition:
          border-color 0.2s,
          background 0.2s;
        min-height: 180px;
      }

      .drop-zone:hover,
      .drop-zone.drag-over {
        border-color: var(--primary-teal);
        background: rgba(23, 128, 130, 0.05);
      }

      .drop-icon {
        font-size: 48px;
        font-family: 'Material Icons';
        color: var(--primary-teal);
      }

      .drop-text {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
      }

      .drop-subtext {
        font-size: 0.85rem;
        color: var(--text-secondary);
        margin: 0;
      }

      .drop-hint {
        font-size: 0.75rem;
        color: var(--text-secondary);
        margin: 0;
        opacity: 0.7;
      }

      .file-info {
        display: flex;
        align-items: center;
        gap: var(--spacing-md);
        padding: var(--spacing-md);
        background: var(--surface-color);
        border-radius: 8px;
      }

      .file-icon {
        font-size: 32px;
        font-family: 'Material Icons';
        color: var(--primary-teal);
      }

      .file-details {
        flex: 1;
        display: flex;
        flex-direction: column;
        min-width: 0;
      }

      .file-name {
        font-weight: 500;
        color: var(--text-primary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .file-size {
        font-family: var(--font-data);
        font-size: 0.85rem;
        color: var(--text-secondary);
      }

      .control-btn {
        min-width: 56px;
        min-height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: transparent;
        border: none;
        color: var(--text-secondary);
        cursor: pointer;
        border-radius: 50%;
      }

      .control-btn:hover {
        background: rgba(0, 0, 0, 0.05);
      }

      .material-icon {
        font-size: 24px;
        font-family: 'Material Icons';
        line-height: 1;
      }

      .upload-btn {
        width: 100%;
        min-height: 56px;
      }

      .spinning {
        animation: spin 1s linear infinite;
      }

      @keyframes spin {
        from {
          transform: rotate(0deg);
        }
        to {
          transform: rotate(360deg);
        }
      }
    `,
  ],
})
export class VideoUploadComponent {
  @Output() uploadComplete = new EventEmitter<UploadCompleteEvent>();

  selectedFile = signal<File | null>(null);
  uploadProgress = signal<number | null>(null);
  errorMessage = signal<string | null>(null);
  isDragging = signal(false);

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(true);
  }

  onDragLeave(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    event.stopPropagation();
    this.isDragging.set(false);

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.validateAndSelect(files[0]);
    }
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.validateAndSelect(input.files[0]);
    }
  }

  validateAndSelect(file: File): void {
    this.errorMessage.set(null);

    if (!file.type.startsWith(VALID_MIME_PREFIX)) {
      this.errorMessage.set('Only video files are accepted (MP4, MOV, etc.).');
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      this.errorMessage.set(`File exceeds the 2 GB limit. Size: ${this.formatFileSize(file.size)}`);
      return;
    }

    this.selectedFile.set(file);
  }

  clearSelection(): void {
    this.selectedFile.set(null);
    this.uploadProgress.set(null);
    this.errorMessage.set(null);
  }

  async startUpload(): Promise<void> {
    const file = this.selectedFile();
    if (!file) return;

    this.errorMessage.set(null);
    this.uploadProgress.set(0);

    try {
      // Step 1: Get presigned upload URL
      const signRes = await fetch('/api/uploads/sign', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token') || 'test-jwt-token'}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: file.name,
          mime_type: file.type,
          size_bytes: file.size,
        }),
      });

      if (!signRes.ok) {
        throw new Error(`Sign request failed (${signRes.status})`);
      }

      const signData = await signRes.json();
      const { upload_url, upload_id, storage_path } = signData;

      // Step 2: PUT file to presigned URL
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open('PUT', upload_url);
        xhr.setRequestHeader('Content-Type', file.type);

        xhr.upload.onprogress = (e) => {
          if (e.lengthComputable) {
            this.uploadProgress.set(Math.round((e.loaded / e.total) * 100));
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload failed (${xhr.status})`));
          }
        };

        xhr.onerror = () => reject(new Error('Network error during upload'));
        xhr.send(file);
      });

      // Step 3: Finalize upload
      const finalizeRes = await fetch('/api/uploads/finalize', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('auth_token') || 'test-jwt-token'}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ upload_id, storage_path }),
      });

      if (!finalizeRes.ok) {
        throw new Error(`Finalize request failed (${finalizeRes.status})`);
      }

      const finalizeData = await finalizeRes.json();

      this.uploadProgress.set(100);
      this.uploadComplete.emit({
        id: finalizeData.id || upload_id,
        storage_path,
        duration_seconds: finalizeData.duration_seconds ?? 0,
      });

      // Reset after success
      setTimeout(() => {
        this.clearSelection();
      }, 1500);
    } catch (err: any) {
      this.errorMessage.set(err?.message || 'Upload failed. Please try again.');
      this.uploadProgress.set(null);
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    const size = bytes / Math.pow(1024, i);
    return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
  }
}
