/**
 * Tests for config injection script.
 */
const { describe, it, beforeEach, afterEach } = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

describe('inject-amplify-config', () => {
  const testOutputsPath = path.join(__dirname, '../../../amplify_outputs.json');
  const generatedConfigPath = path.join(__dirname, '../src/amplify-config.generated.ts');

  beforeEach(() => {
    // Clean up before each test
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  afterEach(() => {
    // Clean up after tests
    if (fs.existsSync(testOutputsPath)) {
      fs.unlinkSync(testOutputsPath);
    }
    if (fs.existsSync(generatedConfigPath)) {
      fs.unlinkSync(generatedConfigPath);
    }
  });

  it('should generate config file when amplify_outputs.json exists', () => {
    // Create mock amplify_outputs.json
    const mockOutputs = {
      data: { url: 'https://test.appsync-api.us-east-1.amazonaws.com/graphql' },
      auth: { aws_region: 'us-east-1' }
    };
    fs.writeFileSync(testOutputsPath, JSON.stringify(mockOutputs, null, 2));

    // Run script
    execSync('node scripts/inject-amplify-config.js', {
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit'
    });

    // Verify generated file
    assert.ok(fs.existsSync(generatedConfigPath), 'Config file should be generated');

    const content = fs.readFileSync(generatedConfigPath, 'utf-8');
    assert.ok(content.includes('AMPLIFY_OUTPUTS'), 'Should export AMPLIFY_OUTPUTS');
    assert.ok(content.includes('test.appsync-api'), 'Should include API URL');
  });

  it('should fail if amplify_outputs.json missing', () => {
    assert.throws(() => {
      execSync('node scripts/inject-amplify-config.js', {
        cwd: path.join(__dirname, '..'),
        stdio: 'pipe'
      });
    }, 'Should throw error when amplify_outputs.json missing');
  });

  it('should generate valid TypeScript with correct structure', () => {
    // Create mock amplify_outputs.json
    const mockOutputs = {
      data: { url: 'https://test.appsync-api.us-east-1.amazonaws.com/graphql' },
      auth: {
        aws_region: 'us-east-1',
        user_pool_id: 'us-east-1_TEST',
        user_pool_client_id: 'test-client-id'
      }
    };
    fs.writeFileSync(testOutputsPath, JSON.stringify(mockOutputs, null, 2));

    // Run script
    execSync('node scripts/inject-amplify-config.js', {
      cwd: path.join(__dirname, '..'),
      stdio: 'inherit'
    });

    // Verify generated file structure
    const content = fs.readFileSync(generatedConfigPath, 'utf-8');
    assert.ok(content.includes('export const AMPLIFY_OUTPUTS'), 'Should export constant');
    assert.ok(content.includes('as const'), 'Should have as const assertion');
    assert.ok(content.includes('Auto-generated'), 'Should have auto-generated comment');
    assert.ok(content.includes('DO NOT EDIT MANUALLY'), 'Should have warning comment');
  });
});
