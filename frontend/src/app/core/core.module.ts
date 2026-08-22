import { NgModule, Optional, SkipSelf } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HTTP_INTERCEPTORS } from '@angular/common/http';
import { AuthService } from './services/auth.service';
import { apiInterceptor } from '../shared/api/api-client.service';

@NgModule({
  imports: [CommonModule],
  providers: [
    AuthService,
    {
      provide: HTTP_INTERCEPTORS,
      useValue: apiInterceptor,
      multi: true,
    },
  ],
})
export class CoreModule {
  constructor(@Optional() @SkipSelf() parentModule?: CoreModule) {
    if (parentModule) {
      throw new Error('CoreModule is already loaded. Import it only in the root AppModule.');
    }
  }
}
