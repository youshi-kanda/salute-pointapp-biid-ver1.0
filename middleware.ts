import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 開発環境では制限を最小限に
  if (process.env.NODE_ENV === 'development') {
    return NextResponse.next();
  }

  // 基本的なセキュリティヘッダーのみ
  const response = NextResponse.next();
  
  // 最低限のセキュリティヘッダー
  response.headers.set('X-Frame-Options', 'SAMEORIGIN');
  response.headers.set('X-Content-Type-Options', 'nosniff');
  
  return response;
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|public).*)',
  ],
};