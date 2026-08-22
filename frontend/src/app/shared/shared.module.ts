import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';

import { CardComponent } from './ui/card.component';
import { ButtonComponent } from './ui/button.component';
import { TypographyComponent } from './ui/typography.component';
import { IconComponent } from './ui/icon.component';
import { LoadingSpinnerComponent } from './ui/loading-spinner.component';
import { ErrorDisplayComponent } from './ui/error-display.component';

@NgModule({
  imports: [CommonModule],
  exports: [
    CardComponent,
    ButtonComponent,
    TypographyComponent,
    IconComponent,
    LoadingSpinnerComponent,
    ErrorDisplayComponent,
  ],
})
export class SharedModule {}
