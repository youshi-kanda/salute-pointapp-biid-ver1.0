/** @type {import('next').NextConfig} */
const nextConfig = {
  // Cloudflare Pages用の静的出力
  output: 'export',
  
  reactStrictMode: false,
  swcMinify: true,
  poweredByHeader: false,
  
  // 画像最適化無効化（静的出力との互換性）
  images: {
    unoptimized: true,
  },
  
  // 基本的なリダイレクトのみ
  async redirects() {
    return [
      {
        source: '/',
        destination: '/terminal-simple',
        permanent: false,
      },
    ];
  },

  // モック時は開発用リライトを無効化
  async rewrites() {
    return [];
  }
}

module.exports = nextConfig