// 安全なナビゲーション（同一URLハード遷移エラー回避）
export function safeNavigate(targetPath: string, useReplace: boolean = true): boolean {
  if (typeof window === 'undefined') return false;
  
  // 現在のパスと同じ場合は何もしない（Invariantエラー回避）
  if (window.location.pathname === targetPath) {
    console.log(`🚫 Same URL navigation skipped: ${targetPath}`);
    return false;
  }
  
  // Next.js routerが利用可能な場合
  if (typeof window !== 'undefined' && (window as any).__NEXT_ROUTER_PRESENT) {
    const router = (window as any).__NEXT_ROUTER;
    if (router) {
      if (useReplace) {
        router.replace(targetPath, undefined, { shallow: true });
      } else {
        router.push(targetPath);
      }
      return true;
    }
  }
  
  // フォールバック: 直接遷移
  try {
    window.location.assign(targetPath);
    return true;
  } catch (error) {
    console.warn('Navigation fallback failed:', error);
    return false;
  }
}

// 決済完了後のホーム遷移（使用例）
export function navigateToHome(): boolean {
  return safeNavigate('/', true);
}

// 決済キャンセル後の戻り遷移（使用例）
export function navigateToTerminal(): boolean {
  return safeNavigate('/terminal-simple', true);
}