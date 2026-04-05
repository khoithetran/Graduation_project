export type VideoAlert = {
  id: string;
  timestamp_sec: number;
  class_name: string;
  confidence: number;
  crop: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};
