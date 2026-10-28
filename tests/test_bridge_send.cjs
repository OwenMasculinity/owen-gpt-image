const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../chatgpt-web-bridge/extension/background.js'), 'utf8');
const inputFunction = source.slice(source.indexOf('async function doCdpInput('), source.indexOf('async function reloadTabFresh('));

async function submit({ enterWorks = false, buttonAvailable = true, countChanges = true } = {}) {
  let accepted = false;
  const calls = [];
  const context = vm.createContext({
    FOCUS_COMPOSER_JS: 'focus', READ_COMPOSER_JS: 'draft',
    COUNT_USER_TURNS_JS: 'count', SEND_BUTTON_POINT_JS: 'button',
    setTimeout: callback => callback(),
    cdpAttach: async () => {},
    cdpEvaluate: async (_tab, expression) => {
      if (expression === 'focus') return 'ok';
      if (expression === 'draft') return accepted ? '' : 'original prompt';
      if (expression === 'count') return accepted && countChanges ? 6 : 5;
      if (expression === 'button') return buttonAvailable ? { x: 100, y: 200 } : null;
      throw new Error(expression);
    },
    cdp: async (_tab, method, params) => {
      calls.push({ method, ...params });
      if (method === 'Input.dispatchKeyEvent' && params.type === 'keyUp' && enterWorks) accepted = true;
      if (method === 'Input.dispatchMouseEvent' && params.type === 'mouseReleased') accepted = true;
    },
  });
  vm.runInContext(inputFunction + '\nglobalThis.submit = doCdpInput;', context);
  return { result: await context.submit(1, { enter: true }), calls };
}

test('ignored Enter falls back to one real mouse click', async () => {
  const { result, calls } = await submit();
  assert.equal(result.sent, true);
  assert.equal(calls.filter(call => call.method === 'Input.dispatchMouseEvent').length, 2);
});

test('accepted Enter never clicks the send button again', async () => {
  const { result, calls } = await submit({ enterWorks: true });
  assert.equal(result.sent, true);
  assert.equal(calls.filter(call => call.method === 'Input.dispatchMouseEvent').length, 0);
});

test('virtualized message count does not trigger a duplicate submission', async () => {
  const { result, calls } = await submit({ enterWorks: true, countChanges: false });
  assert.equal(result.sent, true);
  assert.equal(calls.filter(call => call.method === 'Input.dispatchMouseEvent').length, 0);
});

test('missing send button is reported as an unconfirmed submission', async () => {
  const { result } = await submit({ buttonAvailable: false });
  assert.equal(result.sent, false);
});
