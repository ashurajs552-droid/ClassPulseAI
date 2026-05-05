-- ============================================================
-- ClassPulse AI — Complete Database Schema
-- Run this in Supabase SQL Editor
-- ============================================================

-- 1. EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pgvector" WITH SCHEMA "extensions";
CREATE EXTENSION IF NOT EXISTS "pg_trgm" WITH SCHEMA "extensions";

-- 2. CUSTOM ENUM TYPES
-- ============================================================
DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('teacher', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE session_status AS ENUM ('active', 'completed', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE attendance_status AS ENUM ('present', 'absent', 'late');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE attendance_marker AS ENUM ('ai', 'manual');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE emotion_type AS ENUM ('attentive', 'distracted', 'sleepy', 'confused', 'engaged');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alert_type AS ENUM (
    'phone_detected', 'low_engagement', 'mass_sleeping',
    'high_confusion', 'attendance_anomaly'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 3. TABLES
-- ============================================================

-- 3.1 profiles
CREATE TABLE IF NOT EXISTS public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name   TEXT NOT NULL,
  role        user_role NOT NULL DEFAULT 'teacher',
  avatar_url  TEXT,
  school_name TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.2 classes
CREATE TABLE IF NOT EXISTS public.classes (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name         TEXT NOT NULL,
  teacher_id   UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  room_number  TEXT,
  schedule     JSONB DEFAULT '{}',
  capacity     INTEGER NOT NULL DEFAULT 60 CHECK (capacity > 0),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.3 students
CREATE TABLE IF NOT EXISTS public.students (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_code    TEXT UNIQUE NOT NULL,
  full_name       TEXT NOT NULL,
  class_id        UUID NOT NULL REFERENCES public.classes(id) ON DELETE CASCADE,
  face_encoding   extensions.vector(512),
  photo_url       TEXT,
  enrollment_date DATE NOT NULL DEFAULT CURRENT_DATE,
  is_active       BOOLEAN NOT NULL DEFAULT true,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.4 sessions
CREATE TABLE IF NOT EXISTS public.sessions (
  id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  class_id             UUID NOT NULL REFERENCES public.classes(id) ON DELETE CASCADE,
  teacher_id           UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at             TIMESTAMPTZ,
  total_students       INTEGER DEFAULT 0,
  avg_engagement_score DOUBLE PRECISION DEFAULT 0.0,
  status               session_status NOT NULL DEFAULT 'active',
  metadata             JSONB DEFAULT '{}',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.5 attendance
CREATE TABLE IF NOT EXISTS public.attendance (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id              UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  student_id              UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
  detected_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  recognition_confidence  DOUBLE PRECISION CHECK (recognition_confidence >= 0 AND recognition_confidence <= 1),
  status                  attendance_status NOT NULL DEFAULT 'present',
  marked_by               attendance_marker NOT NULL DEFAULT 'ai',
  UNIQUE(session_id, student_id)
);

-- 3.6 emotion_logs
CREATE TABLE IF NOT EXISTS public.emotion_logs (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  student_id  UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
  emotion     emotion_type NOT NULL,
  confidence  DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
  timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.7 engagement_scores
CREATE TABLE IF NOT EXISTS public.engagement_scores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  student_id      UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
  score           DOUBLE PRECISION CHECK (score >= 0 AND score <= 100),
  attention_level DOUBLE PRECISION CHECK (attention_level >= 0 AND attention_level <= 1),
  posture_score   DOUBLE PRECISION CHECK (posture_score >= 0 AND posture_score <= 1),
  emotion_score   DOUBLE PRECISION CHECK (emotion_score >= 0 AND emotion_score <= 1),
  timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.8 phone_detections
CREATE TABLE IF NOT EXISTS public.phone_detections (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  student_id  UUID REFERENCES public.students(id) ON DELETE SET NULL,
  detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  confidence  DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
  bbox        JSONB DEFAULT '{}'
);

-- 3.9 alerts
CREATE TABLE IF NOT EXISTS public.alerts (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  type        alert_type NOT NULL,
  message     TEXT NOT NULL,
  severity    alert_severity NOT NULL DEFAULT 'medium',
  student_id  UUID REFERENCES public.students(id) ON DELETE SET NULL,
  is_resolved BOOLEAN NOT NULL DEFAULT false,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.10 reports
CREATE TABLE IF NOT EXISTS public.reports (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id       UUID NOT NULL REFERENCES public.sessions(id) ON DELETE CASCADE,
  teacher_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,
  summary          TEXT,
  insights         JSONB DEFAULT '[]',
  recommendations  JSONB DEFAULT '[]',
  metrics_snapshot JSONB DEFAULT '{}',
  generated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  pdf_url          TEXT
);

-- 4. INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_classes_teacher      ON public.classes(teacher_id);
CREATE INDEX IF NOT EXISTS idx_students_class       ON public.students(class_id);
CREATE INDEX IF NOT EXISTS idx_students_code        ON public.students(student_code);
CREATE INDEX IF NOT EXISTS idx_students_active      ON public.students(is_active);
CREATE INDEX IF NOT EXISTS idx_sessions_class       ON public.sessions(class_id);
CREATE INDEX IF NOT EXISTS idx_sessions_teacher     ON public.sessions(teacher_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status      ON public.sessions(status);
CREATE INDEX IF NOT EXISTS idx_sessions_started     ON public.sessions(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_attendance_session   ON public.attendance(session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_student   ON public.attendance(student_id);
CREATE INDEX IF NOT EXISTS idx_emotion_session      ON public.emotion_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_emotion_student      ON public.emotion_logs(student_id);
CREATE INDEX IF NOT EXISTS idx_emotion_ts           ON public.emotion_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_engagement_session   ON public.engagement_scores(session_id);
CREATE INDEX IF NOT EXISTS idx_engagement_student   ON public.engagement_scores(student_id);
CREATE INDEX IF NOT EXISTS idx_engagement_ts        ON public.engagement_scores(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_phone_session        ON public.phone_detections(session_id);
CREATE INDEX IF NOT EXISTS idx_phone_ts             ON public.phone_detections(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_session       ON public.alerts(session_id);
CREATE INDEX IF NOT EXISTS idx_alerts_severity      ON public.alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved    ON public.alerts(is_resolved) WHERE is_resolved = false;
CREATE INDEX IF NOT EXISTS idx_reports_session      ON public.reports(session_id);
CREATE INDEX IF NOT EXISTS idx_reports_teacher      ON public.reports(teacher_id);

-- 5. UPDATED_AT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS set_profiles_updated_at ON public.profiles;
CREATE TRIGGER set_profiles_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.handle_updated_at();

-- 6. AUTO-CREATE PROFILE ON SIGNUP
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, full_name, role, avatar_url)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data ->> 'full_name', NEW.email),
    COALESCE((NEW.raw_user_meta_data ->> 'role')::user_role, 'teacher'),
    NEW.raw_user_meta_data ->> 'avatar_url'
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 7. FACE MATCHING FUNCTION (pgvector cosine similarity)
-- ============================================================
CREATE OR REPLACE FUNCTION public.match_face(
  query_embedding extensions.vector(512),
  match_threshold DOUBLE PRECISION DEFAULT 0.68,
  max_results INTEGER DEFAULT 5
)
RETURNS TABLE (
  student_id   UUID,
  student_code TEXT,
  full_name    TEXT,
  photo_url    TEXT,
  similarity   DOUBLE PRECISION
)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id AS student_id,
    s.student_code,
    s.full_name,
    s.photo_url,
    1 - (s.face_encoding <=> query_embedding) AS similarity
  FROM public.students s
  WHERE s.is_active = true
    AND s.face_encoding IS NOT NULL
    AND 1 - (s.face_encoding <=> query_embedding) >= match_threshold
  ORDER BY s.face_encoding <=> query_embedding
  LIMIT max_results;
END;
$$;

-- 8. ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE public.profiles          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.classes           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.students          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.sessions          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_logs      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phone_detections  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.reports           ENABLE ROW LEVEL SECURITY;

-- profiles: users can read all, update own
CREATE POLICY "profiles_select" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- classes: teachers see own classes, admins see all
CREATE POLICY "classes_select" ON public.classes FOR SELECT USING (
  teacher_id = auth.uid()
  OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "classes_insert" ON public.classes FOR INSERT WITH CHECK (teacher_id = auth.uid());
CREATE POLICY "classes_update" ON public.classes FOR UPDATE USING (teacher_id = auth.uid());
CREATE POLICY "classes_delete" ON public.classes FOR DELETE USING (teacher_id = auth.uid());

-- students: teachers see students in their classes, admins see all
CREATE POLICY "students_select" ON public.students FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.classes c WHERE c.id = class_id AND c.teacher_id = auth.uid())
  OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "students_insert" ON public.students FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.classes c WHERE c.id = class_id AND c.teacher_id = auth.uid())
);
CREATE POLICY "students_update" ON public.students FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.classes c WHERE c.id = class_id AND c.teacher_id = auth.uid())
);
CREATE POLICY "students_delete" ON public.students FOR DELETE USING (
  EXISTS (SELECT 1 FROM public.classes c WHERE c.id = class_id AND c.teacher_id = auth.uid())
);

-- sessions: teachers see own sessions
CREATE POLICY "sessions_select" ON public.sessions FOR SELECT USING (
  teacher_id = auth.uid()
  OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "sessions_insert" ON public.sessions FOR INSERT WITH CHECK (teacher_id = auth.uid());
CREATE POLICY "sessions_update" ON public.sessions FOR UPDATE USING (teacher_id = auth.uid());

-- attendance: via session ownership
CREATE POLICY "attendance_select" ON public.attendance FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND (s.teacher_id = auth.uid() OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')))
);
CREATE POLICY "attendance_insert" ON public.attendance FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);
CREATE POLICY "attendance_update" ON public.attendance FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);

-- emotion_logs: via session ownership
CREATE POLICY "emotion_logs_select" ON public.emotion_logs FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND (s.teacher_id = auth.uid() OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')))
);
CREATE POLICY "emotion_logs_insert" ON public.emotion_logs FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);

-- engagement_scores: via session ownership
CREATE POLICY "engagement_scores_select" ON public.engagement_scores FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND (s.teacher_id = auth.uid() OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')))
);
CREATE POLICY "engagement_scores_insert" ON public.engagement_scores FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);

-- phone_detections: via session ownership
CREATE POLICY "phone_detections_select" ON public.phone_detections FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND (s.teacher_id = auth.uid() OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')))
);
CREATE POLICY "phone_detections_insert" ON public.phone_detections FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);

-- alerts: via session ownership
CREATE POLICY "alerts_select" ON public.alerts FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND (s.teacher_id = auth.uid() OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')))
);
CREATE POLICY "alerts_insert" ON public.alerts FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);
CREATE POLICY "alerts_update" ON public.alerts FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.sessions s WHERE s.id = session_id AND s.teacher_id = auth.uid())
);

-- reports: teacher sees own, admin sees all
CREATE POLICY "reports_select" ON public.reports FOR SELECT USING (
  teacher_id = auth.uid()
  OR EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin')
);
CREATE POLICY "reports_insert" ON public.reports FOR INSERT WITH CHECK (teacher_id = auth.uid());
CREATE POLICY "reports_update" ON public.reports FOR UPDATE USING (teacher_id = auth.uid());

-- 9. SERVICE ROLE BYPASS (for Python backend)
-- ============================================================
-- The service_role key bypasses RLS automatically in Supabase.
-- No additional policies needed for backend operations.

-- 10. REALTIME PUBLICATION
-- ============================================================
DROP PUBLICATION IF EXISTS supabase_realtime;
CREATE PUBLICATION supabase_realtime FOR TABLE
  public.profiles,
  public.classes,
  public.students,
  public.sessions,
  public.attendance,
  public.emotion_logs,
  public.engagement_scores,
  public.phone_detections,
  public.alerts,
  public.reports;

-- 11. STORAGE BUCKETS
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES
  ('student-photos', 'student-photos', true),
  ('report-pdfs',    'report-pdfs',    false)
ON CONFLICT (id) DO NOTHING;

-- student-photos: public read, authenticated upload
CREATE POLICY "student_photos_public_read" ON storage.objects
  FOR SELECT USING (bucket_id = 'student-photos');
CREATE POLICY "student_photos_auth_upload" ON storage.objects
  FOR INSERT WITH CHECK (bucket_id = 'student-photos' AND auth.role() = 'authenticated');
CREATE POLICY "student_photos_auth_update" ON storage.objects
  FOR UPDATE USING (bucket_id = 'student-photos' AND auth.role() = 'authenticated');
CREATE POLICY "student_photos_auth_delete" ON storage.objects
  FOR DELETE USING (bucket_id = 'student-photos' AND auth.role() = 'authenticated');

-- report-pdfs: owner read
CREATE POLICY "report_pdfs_owner_read" ON storage.objects
  FOR SELECT USING (bucket_id = 'report-pdfs' AND auth.role() = 'authenticated');
CREATE POLICY "report_pdfs_auth_upload" ON storage.objects
  FOR INSERT WITH CHECK (bucket_id = 'report-pdfs' AND auth.role() = 'authenticated');

-- 12. MIGRATIONS
-- ============================================================
ALTER TABLE public.students
  ADD COLUMN IF NOT EXISTS usn text UNIQUE,
  ADD COLUMN IF NOT EXISTS phone_number text,
  ADD COLUMN IF NOT EXISTS semester text,
  ADD COLUMN IF NOT EXISTS department text,
  ADD COLUMN IF NOT EXISTS gender text,
  ADD COLUMN IF NOT EXISTS photo_url text,
  ADD COLUMN IF NOT EXISTS is_active boolean DEFAULT true,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

ALTER TABLE public.students
  DROP COLUMN IF EXISTS enrollment_date,
  DROP COLUMN IF EXISTS student_code,
  DROP COLUMN IF EXISTS class_id,
  DROP COLUMN IF EXISTS face_encoding;

CREATE TABLE IF NOT EXISTS public.sessions (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  teacher_id uuid,
  title text DEFAULT 'Class Session',
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz,
  total_students int DEFAULT 0,
  avg_engagement_score float DEFAULT 0,
  status text DEFAULT 'active',
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.attendance (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid,
  student_id uuid,
  detected_at timestamptz DEFAULT now(),
  recognition_confidence float DEFAULT 0,
  status text DEFAULT 'present',
  marked_by text DEFAULT 'ai'
);

CREATE TABLE IF NOT EXISTS public.emotion_logs (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid,
  student_id uuid,
  emotion text NOT NULL,
  confidence float DEFAULT 0,
  timestamp timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.engagement_scores (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid,
  student_id uuid,
  score float DEFAULT 0,
  attention_level float DEFAULT 0,
  emotion_score float DEFAULT 0,
  posture_score float DEFAULT 0,
  timestamp timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.phone_detections (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid,
  student_id uuid,
  detected_at timestamptz DEFAULT now(),
  confidence float DEFAULT 0,
  bbox jsonb
);

CREATE TABLE IF NOT EXISTS public.alerts (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid,
  student_id uuid,
  type text NOT NULL,
  message text,
  severity text DEFAULT 'medium',
  is_resolved boolean DEFAULT false,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.emotion_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.engagement_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.phone_detections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Auth users manage sessions" ON public.sessions FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth users manage attendance" ON public.attendance FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth users manage emotion_logs" ON public.emotion_logs FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth users manage engagement_scores" ON public.engagement_scores FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth users manage phone_detections" ON public.phone_detections FOR ALL TO authenticated USING (true) WITH CHECK (true);
CREATE POLICY "Auth users manage alerts" ON public.alerts FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- SCHEMA COMPLETE
-- ============================================================
