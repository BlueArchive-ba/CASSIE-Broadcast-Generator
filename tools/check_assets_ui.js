// 验证「素材缺失」提示：有素材时隐藏，没素材时显示并写入期望路径。
//
// 不用 console 输出——app.js 自己会重定义 console，会吞掉这里的日志。
// 结果写到 tools/_assets_result.txt。
const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const OUT = path.join(__dirname, '_assets_result.txt');
const lines = [];
function say(text) { lines.push(text); }

const html = fs.readFileSync(path.join(ROOT, 'cassie_play.html'), 'utf8');
const source = fs.readFileSync(path.join(ROOT, 'static', 'app.js'), 'utf8');
const styleCss = fs.readFileSync(path.join(ROOT, 'static', 'style.css'), 'utf8');

const ids = [...html.matchAll(/id="([^"]+)"/g)].map((m) => m[1]);
const byId = {};
function makeEl(id) {
  const el = {
    id, style: {}, textContent: '', innerHTML: '', hidden: true, value: '',
    checked: false, disabled: false, children: [], classSet: {},
    addEventListener() {}, removeEventListener() {}, dispatchEvent() { return true; },
    setAttribute(k, v) { this['attr_' + k] = String(v); },
    getAttribute(k) { return this['attr_' + k]; },
    removeAttribute() {}, appendChild(c) { return c; }, removeChild() {},
    cloneNode() { return makeEl(id); }, replaceChild() {},
    querySelector() { return null; }, querySelectorAll() { return []; },
    focus() {}, blur() {}, click() {}, scrollIntoView() {}, closest() { return null; },
    getBoundingClientRect() { return { width: 0, height: 0 }; },
    insertAdjacentHTML() {}, contains() { return false; }
  };
  el.classList = {
    add(c) { el.classSet[c] = true; }, remove(c) { delete el.classSet[c]; },
    toggle(c, on) {
      if (on === undefined ? !el.classSet[c] : on) el.classSet[c] = true;
      else delete el.classSet[c];
    },
    contains: (c) => !!el.classSet[c]
  };
  return el;
}
for (const id of ids) byId[id] = makeEl(id);
byId['assetsWarning'].hidden = true;

const doc = {
  getElementById: (id) => byId[id] || null,
  querySelector: () => null, querySelectorAll: () => [],
  addEventListener() {}, createElement: (t) => makeEl('c-' + t),
  body: makeEl('body'), documentElement: makeEl('html'), head: makeEl('head'),
  readyState: 'complete', hidden: false
};

const noop = function () {};
const fakeConsole = { log: noop, warn: noop, error: noop, info: noop, debug: noop };

const win = {
  document: doc, addEventListener: noop, removeEventListener: noop,
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  location: { search: '', href: 'http://localhost/' },
  localStorage: { getItem: () => null, setItem: noop },
  navigator: { languages: ['zh'], language: 'zh' },
  setTimeout, clearTimeout, requestAnimationFrame: (f) => setTimeout(f, 0),
  console: fakeConsole
};

globalThis.window = win;
globalThis.document = doc;
globalThis.navigator = win.navigator;
globalThis.localStorage = win.localStorage;
globalThis.console = fakeConsole;
globalThis.Audio = function () { return { play: noop, pause: noop, addEventListener: noop }; };
globalThis.AudioContext = function () { return { createAnalyser: () => ({}), close: noop }; };
globalThis.setInterval = () => 0;
globalThis.clearInterval = noop;
globalThis.requestAnimationFrame = (f) => setTimeout(f, 0);
globalThis.EventSource = function () { return { addEventListener: noop, close: noop }; };
globalThis.sessionStorage = { getItem: () => null, setItem: noop };
globalThis.XMLHttpRequest = function () { return { open: noop, send: noop, addEventListener: noop }; };
globalThis.URL = { createObjectURL: () => 'blob:x', revokeObjectURL: noop };
globalThis.Blob = function () { return {}; };

let healthPayload = { data: { library: { word_files: 0, words_dir: 'X:/cassie/words' } } };
globalThis.fetch = function () {
  return Promise.resolve({ ok: true, json: () => Promise.resolve(healthPayload) });
};

let failed = 0;
function check(label, ok, detail) {
  say('  ' + (ok ? 'OK   ' : 'FAIL ') + label + (detail ? '  (' + detail + ')' : ''));
  if (!ok) failed += 1;
}

say('=== 素材缺失提示 ===');
check('页面含提示容器', ids.includes('assetsWarning'));
check('页面含路径占位', ids.includes('assetsWarningPath'));
check('提示默认隐藏（HTML 带 hidden）', /id="assetsWarning"[^>]*hidden/.test(html));
check('CSS 有 .assets-warning 规则', /\.assets-warning\s*\{/.test(styleCss));
check('CSS 有 [hidden] 显式规则', /\.assets-warning\[hidden\]/.test(styleCss));
check('app.js 有 checkAssets 函数', /function checkAssets/.test(source));
check('调用 /api/v1/health', /apiFetch\('\/api\/v1\/health'\)/.test(source));
check('有素材时隐藏', /library\.word_files > 0[\s\S]{0,80}box\.hidden = true/.test(source));
check('缺素材时显示', /box\.hidden = false/.test(source));
check('写入期望路径', /assetsWarningPath[\s\S]{0,90}textContent = library\.words_dir/.test(source));
check('页面已加载 style.css', /style\.css/.test(html));

let checkAssets = null;
try {
  new Function(source + '\n;globalThis.__checkAssets = checkAssets;')();
  checkAssets = globalThis.__checkAssets;
} catch (error) {
  check('app.js 能无错执行', false, error.message);
}
check('能取出 checkAssets', typeof checkAssets === 'function');

(async function () {
  if (typeof checkAssets === 'function') {
    byId['assetsWarning'].hidden = true;
    healthPayload = { data: { library: { word_files: 0, words_dir: 'X:/cassie/words' } } };
    await checkAssets();
    await new Promise((r) => setTimeout(r, 40));
    check('缺素材时提示可见', byId['assetsWarning'].hidden === false,
          'hidden=' + byId['assetsWarning'].hidden);
    check('路径已写入', byId['assetsWarningPath'].textContent === 'X:/cassie/words',
          String(byId['assetsWarningPath'].textContent));

    byId['assetsWarning'].hidden = false;
    healthPayload = { data: { library: { word_files: 988, words_dir: 'X:/cassie/words' } } };
    await checkAssets();
    await new Promise((r) => setTimeout(r, 40));
    check('有素材时提示隐藏', byId['assetsWarning'].hidden === true,
          'hidden=' + byId['assetsWarning'].hidden);
  }

  say('');
  say('结果: ' + (failed === 0 ? '全部通过' : failed + ' 项失败'));
  fs.writeFileSync(OUT, lines.join('\n') + '\n', 'utf8');
})();
