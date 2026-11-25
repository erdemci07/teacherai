// TA-008: tahta matematik öğelerinin tipleri. İçe aktarma içermez (node:test ile doğrudan derlenebilir).
// TA-008B: doğrulanmış parçalar (açık/kapalı uçlar), kaldırılabilir süreksizlik (delik) ve düşey asimptot ayrı taşınır.
export interface GraphSegment { start:number;end:number;start_closed:boolean;end_closed:boolean }
export interface GraphData {
  expression:string;roots:number[];y_intercept:number|null;critical_points:number[];sample_points:[number,number][];
  discontinuities?:number[];segments?:GraphSegment[];holes?:[number,number][];asymptotes?:number[];
}
export interface IntervalView { lower:string|null;upper:string|null;lower_closed:boolean;upper_closed:boolean }
