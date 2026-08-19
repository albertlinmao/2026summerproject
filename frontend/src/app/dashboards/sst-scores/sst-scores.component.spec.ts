import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SstScoresComponent } from './sst-scores.component';

describe('SstScoresComponent', () => {
  let component: SstScoresComponent;
  let fixture: ComponentFixture<SstScoresComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SstScoresComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SstScoresComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
