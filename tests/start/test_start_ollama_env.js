#!/usr/bin/env node
/**
 * start.js must not convert an unset OLLAMA_MODEL into a persisted 14B pin.
 */
const assert = require('assert');
const path = require('path');

const start = require(path.join(__dirname, '..', '..', 'start.js'));

assert.strictEqual(start.explicitOllamaModel({}), '');
assert.strictEqual(start.explicitOllamaModel({ OLLAMA_MODEL: '   ' }), '');
assert.strictEqual(
  start.explicitOllamaModel({ OLLAMA_MODEL: 'qwen2.5:14b-instruct' }),
  'qwen2.5:14b-instruct'
);
assert.strictEqual(
  start.explicitOllamaModel({}, { OLLAMA_MODEL: 'custom:7b' }),
  'custom:7b'
);
assert.strictEqual(
  start.explicitOllamaModel({ OLLAMA_MODEL: 'file:14b' }, { OLLAMA_MODEL: 'shell:7b' }),
  'shell:7b'
);
assert.strictEqual(start.ollamaModelIsExplicit({}), false);
assert.strictEqual(start.ollamaModelIsExplicit({ OLLAMA_MODEL: 'x' }), true);

const { updates } = start.ollamaHostUpdates({});
assert.ok(!Object.prototype.hasOwnProperty.call(updates, 'OLLAMA_MODEL'));
assert.ok(updates.OLLAMA_HOST || updates.OLLAMA_BASE_URL);

const { updates: none } = start.ollamaHostUpdates({
  OLLAMA_HOST: 'http://127.0.0.1:11434',
  OLLAMA_BASE_URL: 'http://127.0.0.1:11434',
});
assert.deepStrictEqual(none, {});

console.log('test_start_ollama_env.js ok');
