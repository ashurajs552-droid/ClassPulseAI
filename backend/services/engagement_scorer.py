"""
ClassPulse AI — Engagement Scoring Service

Computes per-student engagement scores using a weighted formula:
  score = (0.4 × attention) + (0.3 × emotion_pos) + (0.2 × posture) + (0.1 × presence)

Attention is derived from MediaPipe head pose estimation.
Emotion positivity is mapped from the detected emotion class.
Posture is estimated from shoulder landmark angles.
Scores are calculated every 2 seconds and pushed to Supabase every 10 seconds.
"""

from __future__ import annotations

import logging
import math
import time
from collections import defaultdict
from typing import Optional

import numpy as np

from config import settings
from models.schemas import EmotionLabel, EngagementScore, BoundingBox, FaceLandmarks

logger = logging.getLogger(__name__)

# Emotion → positivity mapping
EMOTION_POSITIVITY: dict[str, float] = {
    "attentive": 1.0,
    "engaged": 0.9,
    "confused": 0.5,
    "distracted": 0.3,
    "sleepy": 0.1,
}


class EngagementScorerService:
    """Weighted engagement scorer with head-pose attention estimation."""

    def __init__(self) -> None:
        self._w_attention: float = settings.weight_attention
        self._w_emotion: float = settings.weight_emotion
        self._w_posture: float = settings.weight_posture
        self._w_presence: float = settings.weight_presence

        self._calc_interval: float = settings.engagement_calc_interval
        self._push_interval: float = settings.engagement_push_interval

        # Per-track last-calculated timestamp
        self._last_calc: dict[int, float] = defaultdict(float)
        self._last_push: float = 0.0

        # Buffer of scores waiting to be pushed to Supabase
        self._push_buffer: list[EngagementScore] = []

        self._loaded = False

    # ── Lifecycle ────────────────────────────────────────────

    def load(self) -> None:
        """Mark service as ready (no heavy model to load)."""
        self._loaded = True
        logger.info(
            "Engagement scorer ready — weights: attn=%.1f emo=%.1f post=%.1f pres=%.1f",
            self._w_attention, self._w_emotion, self._w_posture, self._w_presence,
        )

    def unload(self) -> None:
        self._last_calc.clear()
        self._push_buffer.clear()
        self._loaded = False
        logger.info("Engagement scorer unloaded.")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Scoring ──────────────────────────────────────────────

    def calculate(
        self,
        track_id: int,
        student_id: Optional[str],
        emotion: Optional[str],
        landmarks: Optional[FaceLandmarks],
        bbox: Optional[BoundingBox],
        is_present: bool = True,
    ) -> Optional[EngagementScore]:
        """
        Calculate engagement for one tracked person.

        Returns an EngagementScore if the interval has elapsed since
        last calculation for this track, otherwise None.
        """
        if not self._loaded:
            return None

        now = time.time()
        if now - self._last_calc[track_id] < self._calc_interval:
            return None
        self._last_calc[track_id] = now

        attention = self._estimate_attention(landmarks)
        emotion_pos = EMOTION_POSITIVITY.get(emotion or "distracted", 0.3)
        posture = self._estimate_posture(landmarks, bbox)
        presence = 1.0 if is_present else 0.0

        raw_score = (
            self._w_attention * attention
            + self._w_emotion * emotion_pos
            + self._w_posture * posture
            + self._w_presence * presence
        )
        score = round(min(100.0, max(0.0, raw_score * 100)), 2)

        result = EngagementScore(
            student_id=student_id,
            track_id=track_id,
            score=score,
            attention=round(attention, 4),
            emotion_positive=round(emotion_pos, 4),
            posture=round(posture, 4),
            presence=presence,
        )

        self._push_buffer.append(result)
        return result

    def calculate_batch(
        self,
        track_ids: list[int],
        student_ids: list[Optional[str]],
        emotions: list[Optional[str]],
        landmarks_list: list[Optional[FaceLandmarks]],
        bboxes: list[Optional[BoundingBox]],
    ) -> list[EngagementScore]:
        """Calculate engagement for multiple tracked persons at once."""
        results: list[EngagementScore] = []
        for tid, sid, emo, lm, bb in zip(
            track_ids, student_ids, emotions, landmarks_list, bboxes
        ):
            result = self.calculate(tid, sid, emo, lm, bb)
            if result:
                results.append(result)
        return results

    # ── Push buffer ──────────────────────────────────────────

    def get_pending_scores(self) -> list[EngagementScore]:
        """
        Return scores that should be pushed to Supabase.
        Only returns scores if push_interval has elapsed.
        Clears the buffer after return.
        """
        now = time.time()
        if now - self._last_push < self._push_interval:
            return []

        self._last_push = now
        pending = self._push_buffer.copy()
        self._push_buffer.clear()
        return pending

    def get_class_average(self) -> float:
        """Average engagement across all buffered scores."""
        if not self._push_buffer:
            return 0.0
        return round(
            sum(s.score for s in self._push_buffer) / len(self._push_buffer), 2
        )

    # ── Attention estimation (head pose) ─────────────────────

    @staticmethod
    def _estimate_attention(landmarks: Optional[FaceLandmarks]) -> float:
        """
        Estimate attention level from facial landmarks using head pose proxy.

        Uses the relative positions of eyes and nose to approximate
        yaw and pitch:
        - Looking straight → attention ≈ 1.0
        - Looking away → attention drops
        """
        if landmarks is None:
            return 0.5

        try:
            le = landmarks.left_eye
            re = landmarks.right_eye
            nose = landmarks.nose_tip

            if le == (0, 0) or re == (0, 0) or nose == (0, 0):
                return 0.5

            # Eye midpoint
            eye_cx = (le[0] + re[0]) / 2
            eye_cy = (le[1] + re[1]) / 2

            # Yaw proxy: horizontal offset of nose from eye midpoint
            eye_dist = abs(le[0] - re[0])
            if eye_dist < 1e-5:
                return 0.5
            yaw_offset = abs(nose[0] - eye_cx) / eye_dist
            yaw_score = max(0.0, 1.0 - yaw_offset * 3.0)

            # Pitch proxy: vertical offset of nose below eyes
            pitch_offset = (nose[1] - eye_cy) / eye_dist
            # Normal range is ~0.4–0.8; outside means looking up/down
            if 0.3 <= pitch_offset <= 1.0:
                pitch_score = 1.0
            else:
                pitch_score = max(0.0, 1.0 - abs(pitch_offset - 0.6) * 2.0)

            attention = 0.6 * yaw_score + 0.4 * pitch_score
            return max(0.0, min(1.0, attention))

        except Exception:
            return 0.5

    # ── Posture estimation ───────────────────────────────────

    @staticmethod
    def _estimate_posture(
        landmarks: Optional[FaceLandmarks],
        bbox: Optional[BoundingBox],
    ) -> float:
        """
        Estimate posture quality from face bounding box aspect ratio
        and vertical position.

        - Upright face → taller bbox, centred → 1.0
        - Slumped/leaning → wider/lower bbox → lower score
        """
        if bbox is None:
            return 0.5

        try:
            aspect = bbox.h / max(bbox.w, 1e-5)

            # Normal upright face aspect ratio ≈ 1.2–1.6
            if 1.1 <= aspect <= 1.8:
                aspect_score = 1.0
            elif aspect > 1.8:
                aspect_score = max(0.3, 1.0 - (aspect - 1.8) * 0.5)
            else:
                aspect_score = max(0.3, 1.0 - (1.1 - aspect) * 1.5)

            # Vertical position: very low on screen → possibly slumped
            vert_centre = bbox.y + bbox.h / 2
            if vert_centre > 0.85:
                vert_score = 0.4
            elif vert_centre < 0.15:
                vert_score = 0.6
            else:
                vert_score = 1.0

            posture = 0.7 * aspect_score + 0.3 * vert_score
            return max(0.0, min(1.0, posture))

        except Exception:
            return 0.5
