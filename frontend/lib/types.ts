/* ── TypeScript interfaces for ClassPulse AI ─────────────── */

export interface Profile {
  id: string;
  full_name: string;
  role: "teacher" | "admin";
  avatar_url: string | null;
  school_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClassRoom {
  id: string;
  name: string;
  teacher_id: string;
  room_number: string | null;
  schedule: Record<string, string>;
  capacity: number;
  created_at: string;
  profiles?: { full_name: string };
}

export interface Student {
  id: string;
  student_code: string;
  full_name: string;
  class_id: string;
  photo_url: string | null;
  enrollment_date: string;
  is_active: boolean;
  created_at: string;
  classes?: { name: string };
}

export interface Session {
  id: string;
  class_id: string;
  teacher_id: string;
  started_at: string;
  ended_at: string | null;
  total_students: number;
  avg_engagement_score: number;
  status: "active" | "completed" | "cancelled";
  metadata: Record<string, unknown>;
  classes?: { name: string; room_number: string };
}

export interface AttendanceRecord {
  id: string;
  session_id: string;
  student_id: string;
  detected_at: string;
  recognition_confidence: number;
  status: "present" | "absent" | "late";
  marked_by: "ai" | "manual";
  students?: { full_name: string; student_code: string; photo_url: string | null };
}

export interface EmotionLog {
  id: string;
  session_id: string;
  student_id: string;
  emotion: EmotionLabel;
  confidence: number;
  timestamp: string;
}

export type EmotionLabel = "attentive" | "distracted" | "sleepy" | "confused" | "engaged";

export interface EngagementScore {
  id: string;
  session_id: string;
  student_id: string;
  score: number;
  attention_level: number;
  posture_score: number;
  emotion_score: number;
  timestamp: string;
}

export interface PhoneDetection {
  id: string;
  session_id: string;
  student_id: string | null;
  detected_at: string;
  confidence: number;
  bbox: { x: number; y: number; w: number; h: number };
}

export interface Alert {
  id: string;
  session_id: string;
  type: AlertType;
  message: string;
  severity: AlertSeverity;
  student_id: string | null;
  is_resolved: boolean;
  created_at: string;
}

export type AlertType = "phone_detected" | "low_engagement" | "mass_sleeping" | "high_confusion" | "attendance_anomaly";
export type AlertSeverity = "low" | "medium" | "high" | "critical";

export interface Report {
  id: string;
  session_id: string;
  teacher_id: string;
  title: string;
  summary: string;
  insights: ReportInsight[];
  recommendations: string[];
  metrics_snapshot: Record<string, unknown>;
  generated_at: string;
  pdf_url: string | null;
}

export interface ReportInsight {
  title: string;
  description: string;
  metric?: string;
  icon?: string;
}

/* ── WebSocket message types ─────────────────────────────── */

export interface BBox {
  x: number; y: number; w: number; h: number;
}

export interface DetectedStudent {
  track_id: number;
  student_id: string | null;
  student_name: string | null;
  bbox: BBox;
  confidence: number;
  emotion: EmotionLabel | null;
  emotion_confidence: number | null;
  engagement_score: number | null;
  has_phone: boolean;
}

export interface LiveMetrics {
  session_id: string;
  total_students: number;
  present_students: number;
  avg_engagement: number;
  emotion_distribution: Record<string, number>;
  phone_detections: number;
  alerts_count: number;
  fps: number;
  latency_ms: number;
  detection_count: number;
}

export interface WSFrameUpdate {
  type: "frame_update";
  data: {
    frame_number: number;
    detections: DetectedStudent[];
    phone_detections: { bbox: BBox; confidence: number; nearby_student_id: string | null }[];
    alerts: { type: AlertType; message: string; severity: AlertSeverity }[];
    metrics: LiveMetrics | null;
    processing_time_ms: number;
  };
  timestamp: string;
}

/* ── Dashboard types ─────────────────────────────────────── */

export interface SessionMetrics {
  attendance_rate: number;
  total_students: number;
  present_count: number;
  absent_count: number;
  avg_engagement: number;
  emotion_distribution: Record<string, number>;
  phone_detections: number;
  alerts_count: number;
  alerts_unresolved: number;
  duration_minutes: number;
  status: string;
}

export interface EngagementTrendPoint {
  time: string;
  score: number;
}

export interface PerStudentEngagement {
  student_id: string;
  student_name: string;
  avg_engagement: number;
  data_points: number;
}
