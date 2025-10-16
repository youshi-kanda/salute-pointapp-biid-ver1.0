// TTS完全無効化（no-op実装）
export async function speak(_text: string): Promise<void> { 
  return; 
}

export function stopSpeak(): void { 
  return; 
}

export function isTTSEnabled(): boolean { 
  return false; 
}

// VoiceFeedback互換クラス（no-op）
export class VoiceFeedback {
  private static instance: VoiceFeedback;

  static getInstance(): VoiceFeedback {
    if (!VoiceFeedback.instance) {
      VoiceFeedback.instance = new VoiceFeedback();
    }
    return VoiceFeedback.instance;
  }

  setEnabled(_enabled: boolean): void { return; }
  setVolume(_volume: number): void { return; }
  setRate(_rate: number): void { return; }
  speak(_text: string, _priority?: 'high' | 'medium' | 'low'): void { return; }
  safeSpeak(_text: string, _priority?: 'high' | 'medium' | 'low'): void { return; }
  stop(): void { return; }
  announceAmount(_amount: number): void { return; }
  announcePaymentStart(): void { return; }
  announcePaymentComplete(): void { return; }
  announceError(_error: string): void { return; }
  announceStep(_step: string): void { return; }
}