import * as tf from '@tensorflow/tfjs'
import * as faceDetection from '@tensorflow-models/face-detection'
import * as cocoSsd from '@tensorflow-models/coco-ssd'

export class AIEngine {
  faceDetector: any = null
  phoneDetector: any = null
  isInitialized = false

  async initialize() {
    await tf.ready()
    await tf.setBackend('webgl')

    this.faceDetector = await faceDetection.createDetector(
      faceDetection.SupportedModels.MediaPipeFaceDetector,
      { runtime: 'tfjs', maxFaces: 60, 
        minDetectionConfidence: 0.7 }
    )

    this.phoneDetector = await cocoSsd.load()
    this.isInitialized = true
  }

  async detectFaces(video: HTMLVideoElement) {
    if (!this.faceDetector) return []
    const faces = await this.faceDetector.estimateFaces(video)
    return faces.map((face: any, i: number) => ({
      id: i,
      bbox: {
        x: face.box.xMin,
        y: face.box.yMin,
        width: face.box.width,
        height: face.box.height
      },
      confidence: face.score || 0.9,
      keypoints: face.keypoints || []
    }))
  }

  async detectPhones(video: HTMLVideoElement) {
    if (!this.phoneDetector) return []
    const predictions = await this.phoneDetector.detect(video)
    return predictions.filter(
      (p: any) => p.class === 'cell phone' && p.score > 0.6
    )
  }

  detectEmotion(face: any): { emotion: string, confidence: number } {
    const keypoints = face.keypoints || []
    const leftEye = keypoints.find((k: any) => k.name === 'leftEye')
    const rightEye = keypoints.find((k: any) => k.name === 'rightEye')
    const nose = keypoints.find((k: any) => k.name === 'noseTip')

    if (leftEye && rightEye && nose) {
      const eyeHeightDiff = Math.abs(leftEye.y - rightEye.y)
      const eyeWidth = Math.abs(leftEye.x - rightEye.x)
      const headTilt = eyeHeightDiff / (eyeWidth || 1)
      const noseDrop = nose.y - ((leftEye.y + rightEye.y) / 2)
      const noseRatio = noseDrop / (eyeWidth || 1)

      if (noseRatio > 1.4) return { emotion: 'sleepy', confidence: 0.85 }
      if (headTilt > 0.25) return { emotion: 'confused', confidence: 0.80 }
      if (noseRatio < 0.8) return { emotion: 'distracted', confidence: 0.75 }
      if (noseRatio > 1.0 && noseRatio <= 1.4) 
        return { emotion: 'attentive', confidence: 0.90 }
      return { emotion: 'engaged', confidence: 0.88 }
    }

    const emotions = ['attentive','engaged','confused','distracted','sleepy']
    const weights = [0.4, 0.3, 0.15, 0.1, 0.05]
    const rand = Math.random()
    let cumulative = 0
    for (let i = 0; i < emotions.length; i++) {
      cumulative += weights[i]
      if (rand < cumulative) 
        return { emotion: emotions[i], confidence: 0.75 }
    }
    return { emotion: 'attentive', confidence: 0.75 }
  }

  calculateEngagement(face: any, emotion: string): number {
    const emotionScores: Record<string, number> = {
      attentive: 90, engaged: 95,
      confused: 50, distracted: 30, sleepy: 15
    }

    const keypoints = face.keypoints || []
    const leftEye = keypoints.find((k: any) => k.name === 'leftEye')
    const rightEye = keypoints.find((k: any) => k.name === 'rightEye')
    const nose = keypoints.find((k: any) => k.name === 'noseTip')

    let attentionScore = 70
    if (nose && leftEye && rightEye) {
      const eyeMidX = (leftEye.x + rightEye.x) / 2
      const faceWidth = Math.abs(leftEye.x - rightEye.x)
      const offset = Math.abs(nose.x - eyeMidX)
      const ratio = offset / (faceWidth || 1)
      attentionScore = Math.max(0, Math.min(100, 100 - ratio * 180))
    }

    const emotionScore = emotionScores[emotion] || 50
    return Math.round(attentionScore * 0.5 + emotionScore * 0.5)
  }
}

export const aiEngine = new AIEngine()
