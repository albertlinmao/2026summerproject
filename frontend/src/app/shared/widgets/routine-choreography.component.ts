import { Component, signal, computed } from '@angular/core';
import { CommonModule } from '@angular/common';

interface RoutineElement {
  id: number;
  name: string;
  category: 'acrobatic' | 'hybrid' | 'transition';
  baseMark: number;
}

@Component({
  selector: 'app-routine-choreography',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="choreography-card">
      <div class="header">
        <h3>Routine Choreography Calculator</h3>
        <div class="total-difficulty score-display">
          {{ totalDifficulty() | number: '1.1-2' }}
        </div>
      </div>

      <div class="choreography-workspace">
        <div class="add-element-form">
          <input type="text" #nameInput placeholder="Element Name" class="input-field" />
          <select #catInput class="input-field">
            <option value="hybrid">Hybrid</option>
            <option value="acrobatic">Acrobatic</option>
            <option value="transition">Transition</option>
          </select>
          <input type="number" #diffInput placeholder="DD" step="0.1" class="input-field" />
          <button
            class="btn btn-primary"
            (click)="
              addElement(nameInput.value, catInput.value, diffInput.value);
              nameInput.value = '';
              diffInput.value = ''
            "
          >
            Add
          </button>
        </div>

        <table class="elements-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Element</th>
              <th>Category</th>
              <th>DD</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            @for (el of elements(); track el; let i = $index) {
              <tr>
                <td>{{ i + 1 }}</td>
                <td>{{ el.name }}</td>
                <td>
                  <span class="cat-badge" [ngClass]="el.category">{{ el.category }}</span>
                </td>
                <td>
                  <strong>{{ el.baseMark | number: '1.1-2' }}</strong>
                </td>
                <td>
                  <button class="btn btn-icon remove-btn" (click)="removeElement(el.id)">✕</button>
                </td>
              </tr>
            }
            @if (elements().length === 0) {
              <tr>
                <td colspan="5" class="empty-state">No elements added.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    </div>
  `,
  styles: [
    `
      .choreography-card {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
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
      .total-difficulty {
        font-size: 3rem;
        color: var(--primary-teal);
      }

      .add-element-form {
        display: flex;
        gap: var(--spacing-sm);
        margin-bottom: var(--spacing-lg);
      }
      .input-field {
        padding: 0.75rem;
        border: 1px solid var(--text-secondary);
        border-radius: 8px;
        font-family: var(--font-main);
        background: transparent;
        color: var(--text-primary);
      }
      .add-element-form input[type='text'] {
        flex: 2;
      }
      .add-element-form select {
        flex: 1;
      }
      .add-element-form input[type='number'] {
        flex: 1;
      }

      .elements-table {
        width: 100%;
        border-collapse: collapse;
      }
      .elements-table th,
      .elements-table td {
        padding: var(--spacing-sm);
        text-align: left;
        border-bottom: 1px solid var(--surface-color);
      }
      .elements-table th {
        font-weight: 600;
        color: var(--text-secondary);
      }
      .cat-badge {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        text-transform: uppercase;
        font-weight: bold;
      }
      .cat-badge.hybrid {
        background: var(--primary-navy);
        color: white;
      }
      .cat-badge.acrobatic {
        background: var(--accent-coral);
        color: white;
      }
      .cat-badge.transition {
        background: var(--accent-gold);
        color: var(--primary-navy);
      }

      .remove-btn {
        width: 32px;
        height: 32px;
        font-size: 14px;
        color: var(--accent-coral);
        background: transparent;
        border: 1px solid var(--accent-coral);
        border-radius: 50%;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .remove-btn:hover {
        background: var(--accent-coral);
        color: white;
      }
      .empty-state {
        text-align: center;
        color: var(--text-secondary);
        font-style: italic;
      }
    `,
  ],
})
export class RoutineChoreographyComponent {
  elements = signal<RoutineElement[]>([
    { id: 1, name: 'Thrust to vertical', category: 'hybrid', baseMark: 1.8 },
    { id: 2, name: 'Platform lift', category: 'acrobatic', baseMark: 2.3 },
  ]);

  totalDifficulty = computed(() => {
    return this.elements().reduce((sum, el) => sum + el.baseMark, 0);
  });

  addElement(name: string, category: string, baseMarkStr: string) {
    const baseMark = parseFloat(baseMarkStr);
    if (!name || isNaN(baseMark)) return;

    this.elements.update((items) => [
      ...items,
      {
        id: Date.now(),
        name,
        category: category as 'acrobatic' | 'hybrid' | 'transition',
        baseMark,
      },
    ]);
  }

  removeElement(id: number) {
    this.elements.update((items) => items.filter((el) => el.id !== id));
  }
}
