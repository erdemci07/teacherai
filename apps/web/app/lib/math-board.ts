// TA-008: tahta matematik öğelerinin tipleri. İçe aktarma içermez (node:test ile doğrudan derlenebilir).
export interface GraphData { expression:string;roots:number[];y_intercept:number|null;critical_points:number[];sample_points:[number,number][];discontinuities?:number[] }
export interface IntervalView { lower:string|null;upper:string|null;lower_closed:boolean;upper_closed:boolean }
