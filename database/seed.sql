-- ============================================================
-- ClassPulse AI — Seed Data
-- Run AFTER schema.sql
-- ============================================================

-- NOTE: In production, the teacher profile is auto-created via the
-- on_auth_user_created trigger when a user signs up through Supabase Auth.
-- This seed creates demo data for development/testing.

-- 1. Create a demo teacher profile
-- (You must first create this user via Supabase Auth or use the dashboard)
-- For seeding, we'll use a fixed UUID. Replace with actual auth.users id.
DO $$
DECLARE
  v_teacher_id UUID := 'a1b2c3d4-e5f6-7890-abcd-ef1234567890';
  v_class_id   UUID := 'c1a2s3s4-e5f6-7890-abcd-ef1234567890';
  v_session_id UUID := 's1e2s3s4-e5f6-7890-abcd-ef1234567890';
BEGIN

  -- Insert teacher profile (skip if auth user doesn't exist in dev)
  INSERT INTO public.profiles (id, full_name, role, school_name)
  VALUES (v_teacher_id, 'Dr. Sarah Mitchell', 'teacher', 'Westfield Academy')
  ON CONFLICT (id) DO NOTHING;

  -- Insert class
  INSERT INTO public.classes (id, name, teacher_id, room_number, schedule, capacity)
  VALUES (
    v_class_id,
    'Computer Science 101',
    v_teacher_id,
    'Room 204',
    '{"monday": "09:00-10:30", "wednesday": "09:00-10:30", "friday": "14:00-15:30"}'::JSONB,
    60
  ) ON CONFLICT (id) DO NOTHING;

  -- Insert 10 students
  INSERT INTO public.students (id, student_code, full_name, class_id, enrollment_date, is_active)
  VALUES
    (gen_random_uuid(), 'STU-001', 'Aanya Sharma',     v_class_id, '2025-08-15', true),
    (gen_random_uuid(), 'STU-002', 'James Chen',        v_class_id, '2025-08-15', true),
    (gen_random_uuid(), 'STU-003', 'Priya Patel',       v_class_id, '2025-08-15', true),
    (gen_random_uuid(), 'STU-004', 'Marcus Johnson',    v_class_id, '2025-08-15', true),
    (gen_random_uuid(), 'STU-005', 'Fatima Al-Hassan',  v_class_id, '2025-08-16', true),
    (gen_random_uuid(), 'STU-006', 'Liam O''Brien',     v_class_id, '2025-08-16', true),
    (gen_random_uuid(), 'STU-007', 'Yuki Tanaka',       v_class_id, '2025-08-16', true),
    (gen_random_uuid(), 'STU-008', 'Sofia Rodriguez',   v_class_id, '2025-08-17', true),
    (gen_random_uuid(), 'STU-009', 'David Kim',         v_class_id, '2025-08-17', true),
    (gen_random_uuid(), 'STU-010', 'Emma Williams',     v_class_id, '2025-08-17', true)
  ON CONFLICT (student_code) DO NOTHING;

  -- Insert a sample session
  INSERT INTO public.sessions (id, class_id, teacher_id, started_at, ended_at, total_students, avg_engagement_score, status)
  VALUES (
    v_session_id,
    v_class_id,
    v_teacher_id,
    now() - interval '2 hours',
    now() - interval '30 minutes',
    10,
    78.5,
    'completed'
  ) ON CONFLICT (id) DO NOTHING;

  -- Insert sample attendance for all students
  INSERT INTO public.attendance (session_id, student_id, detected_at, recognition_confidence, status, marked_by)
  SELECT
    v_session_id,
    s.id,
    v_session_id::text::timestamptz + (random() * interval '5 minutes'),
    0.85 + random() * 0.14,
    CASE WHEN random() > 0.1 THEN 'present'::attendance_status ELSE 'late'::attendance_status END,
    'ai'::attendance_marker
  FROM public.students s
  WHERE s.class_id = v_class_id
  ON CONFLICT (session_id, student_id) DO NOTHING;

  -- Insert sample emotion logs
  INSERT INTO public.emotion_logs (session_id, student_id, emotion, confidence, timestamp)
  SELECT
    v_session_id,
    s.id,
    (ARRAY['attentive', 'engaged', 'distracted', 'confused', 'sleepy']::emotion_type[])[floor(random() * 5 + 1)],
    0.7 + random() * 0.29,
    now() - interval '1 hour' + (random() * interval '1 hour')
  FROM public.students s
  WHERE s.class_id = v_class_id;

  -- Insert sample engagement scores
  INSERT INTO public.engagement_scores (session_id, student_id, score, attention_level, posture_score, emotion_score, timestamp)
  SELECT
    v_session_id,
    s.id,
    50 + random() * 50,
    0.5 + random() * 0.5,
    0.4 + random() * 0.6,
    0.5 + random() * 0.5,
    now() - interval '1 hour' + (random() * interval '1 hour')
  FROM public.students s
  WHERE s.class_id = v_class_id;

  -- Insert sample alerts
  INSERT INTO public.alerts (session_id, type, message, severity, is_resolved)
  VALUES
    (v_session_id, 'phone_detected', 'Phone detected in seat area B3', 'medium', false),
    (v_session_id, 'low_engagement', 'Class engagement dropped below 40%', 'high', true),
    (v_session_id, 'mass_sleeping', '3 students detected sleeping simultaneously', 'critical', false);

END $$;
