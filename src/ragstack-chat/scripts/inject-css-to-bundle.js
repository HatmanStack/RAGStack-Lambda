#!/usr/bin/env node

/**
 * Post-build script to inject CSS into the IIFE bundle
 *
 * Vite doesn't automatically inject CSS in library mode IIFE builds.
 * This script reads the generated CSS and JS files, then prepends
 * CSS injection code to the JS bundle.
 *
 * Run after vite build: node scripts/inject-css-to-bundle.js
 */

const fs = require('fs');
const path = require('path');

const DIST_DIR = path.join(__dirname, '../dist');
const JS_FILE = path.join(DIST_DIR, 'wc.js');
const CSS_FILE = path.join(DIST_DIR, 'style.css');

function main() {
  console.log('💉 Injecting CSS into IIFE bundle...');

  // Check if files exist
  if (!fs.existsSync(JS_FILE)) {
    console.error('❌ Error: dist/wc.js not found. Run build first.');
    process.exit(1);
  }

  if (!fs.existsSync(CSS_FILE)) {
    console.log('ℹ CSS file not found (styles may be inlined by bundler). Skipping CSS injection.');
    return;
  }

  // Read CSS content
  const cssContent = fs.readFileSync(CSS_FILE, 'utf-8');
  console.log(`✓ Read ${cssContent.length} bytes of CSS`);

  // Read JS content
  const jsContent = fs.readFileSync(JS_FILE, 'utf-8');
  console.log(`✓ Read ${jsContent.length} bytes of JS`);

  // Create CSS injection code
  // This IIFE creates a <style> element and appends it to <head>
  const cssInjection = `(function(){try{var s=document.createElement('style');s.setAttribute('data-ragstack-chat','');s.textContent=${JSON.stringify(cssContent)};document.head.appendChild(s);}catch(e){console.error('[RagStackChat] CSS injection failed:',e);}})();`;

  // Prepend CSS injection to JS bundle
  const newJsContent = cssInjection + jsContent;
  fs.writeFileSync(JS_FILE, newJsContent, 'utf-8');

  console.log(`✅ CSS injected into wc.js (${newJsContent.length} bytes)`);

  // Optionally delete the CSS file since it's now embedded
  // fs.unlinkSync(CSS_FILE);
  // console.log('✓ Removed standalone style.css');
}

main();
