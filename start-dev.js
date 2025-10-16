#!/usr/bin/env node

const { spawn } = require('child_process');
const path = require('path');

console.log('🚀 Starting biid Development Server...');
console.log('📂 Project:', path.basename(process.cwd()));

// Next.js development server options
const args = [
  'dev',
  '-p', '3035',           // Fixed port
  '--hostname', '0.0.0.0' // Allow external connections
];

// Spawn Next.js development server
const child = spawn('npx', ['next', ...args], {
  stdio: 'inherit',
  shell: true,
  env: {
    ...process.env,
    NODE_OPTIONS: '--max_old_space_size=4096', // Increase memory limit
    NEXT_TELEMETRY_DISABLED: '1',              // Disable telemetry
    FORCE_COLOR: '1'                           // Enable colors
  }
});

// Handle process termination
process.on('SIGINT', () => {
  console.log('\n⏹️  Shutting down development server...');
  child.kill('SIGINT');
  process.exit(0);
});

process.on('SIGTERM', () => {
  child.kill('SIGTERM');
  process.exit(0);
});

child.on('close', (code) => {
  console.log(`\n✅ Development server exited with code ${code}`);
  process.exit(code);
});

child.on('error', (error) => {
  console.error('❌ Failed to start development server:', error);
  process.exit(1);
});