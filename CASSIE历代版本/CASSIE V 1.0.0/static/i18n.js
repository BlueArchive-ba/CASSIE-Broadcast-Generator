/* C.A.S.S.I.E. — 中英切换引擎（i18n core） */
(function (root) {
    'use strict';

    var STORE_KEY = 'cassie.lang';
    var SUPPORTED = ['zh', 'en'];
    var DEFAULT_LANG = 'zh';
    var HTML_LANG = { zh: 'zh-CN', en: 'en' };

        var dictionary = { zh: {}, en: {} };
    var current = DEFAULT_LANG;
    var mounted = false;
    var toggleEl = null;

    function normalize(value) {
        if (!value) return null;
        var text = String(value).toLowerCase();
        if (text.indexOf('zh') === 0 || text === 'cn' || text === 'chinese') return 'zh';
        if (text.indexOf('en') === 0) return 'en';
        return null;
    }

        function readUrlLang() {
        var search = root.location && root.location.search;
        if (!search) return null;
        var match = /[?&]lang=([^&#]+)/.exec(search);
        return match ? normalize(decodeURIComponent(match[1])) : null;
    }

    function readStored() {
        try {
            return normalize(root.localStorage && root.localStorage.getItem(STORE_KEY));
        } catch (error) {
                        return null;
        }
    }

    function writeStored(lang) {
        try {
            if (root.localStorage) root.localStorage.setItem(STORE_KEY, lang);
        } catch (error) {
                    }
    }

    function detect() {
        var stored = readStored();
        if (stored) return stored;
        var nav = root.navigator || {};
        var langs = nav.languages && nav.languages.length ? nav.languages : [nav.language];
        for (var i = 0; i < langs.length; i += 1) {
            var found = normalize(langs[i]);
            if (found) return found;
        }
        return DEFAULT_LANG;
    }

    function lookup(lang, key) {
        var table = dictionary[lang];
        if (table && Object.prototype.hasOwnProperty.call(table, key)) return table[key];
        return undefined;
    }

    function interpolate(text, vars) {
        if (!vars || typeof text !== 'string') return text;
        return text.replace(/\{(\w+)\}/g, function (match, name) {
            return Object.prototype.hasOwnProperty.call(vars, name) ? String(vars[name]) : match;
        });
    }

        function t(key, vars) {
        var text = lookup(current, key);
        if (text === undefined) text = lookup(DEFAULT_LANG, key);
        if (text === undefined) text = key;
        return interpolate(text, vars);
    }

        function tf(key, fallback, vars) {
        var text = lookup(current, key);
        if (text === undefined) text = lookup(DEFAULT_LANG, key);
        if (text === undefined) text = fallback;
        return interpolate(text, vars);
    }

    function has(key) {
        return lookup(current, key) !== undefined || lookup(DEFAULT_LANG, key) !== undefined;
    }

    var BINDINGS = [
        ['data-i18n', function (el, text) { el.textContent = text; }],
        ['data-i18n-html', function (el, text) { el.innerHTML = text; }],
        ['data-i18n-placeholder', function (el, text) { el.setAttribute('placeholder', text); }],
        ['data-i18n-title', function (el, text) { el.setAttribute('title', text); }],
        ['data-i18n-aria', function (el, text) { el.setAttribute('aria-label', text); }]
    ];

    var SELECTOR = '[data-i18n],[data-i18n-html],[data-i18n-placeholder],[data-i18n-title],[data-i18n-aria]';

    function apply(scope) {
        var host = scope || root.document;
        if (!host || !host.querySelectorAll) return;
        var nodes = host.querySelectorAll(SELECTOR);
        for (var i = 0; i < nodes.length; i += 1) {
            var el = nodes[i];
            for (var b = 0; b < BINDINGS.length; b += 1) {
                var key = el.getAttribute(BINDINGS[b][0]);
                if (key) BINDINGS[b][1](el, t(key));
            }
        }
    }

    function syncToggle() {
        if (!toggleEl) return;
        var options = toggleEl.querySelectorAll('.lang-toggle__option');
        for (var i = 0; i < options.length; i += 1) {
            var option = options[i];
            var isActive = option.getAttribute('data-lang') === current;
            option.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        }
        toggleEl.setAttribute('title', current === 'zh' ? 'Switch to English' : '切换到中文');
    }

        function flashSwitch() {
        var el = root.document && root.document.documentElement;
        if (!el || !el.classList || !root.setTimeout) return;
        el.classList.add('i18n-switching');
        root.setTimeout(function () {
            el.classList.remove('i18n-switching');
        }, 170);
    }

    function setLang(lang, options) {
        var next = normalize(lang) || DEFAULT_LANG;
        var changed = next !== current;
        current = next;

        writeStored(current);
        if (root.document && root.document.documentElement) {
            root.document.documentElement.setAttribute('lang', HTML_LANG[current] || current);
            root.document.documentElement.setAttribute('data-lang', current);
        }
        if (changed) flashSwitch();
        apply();
        syncToggle();

        if (changed && !(options && options.silent) && root.dispatchEvent) {
            var detail = { lang: current };
            var event;
            try {
                event = new root.CustomEvent('cassie:langchange', { detail: detail });
            } catch (error) {
                                event = root.document.createEvent('Event');
                event.initEvent('cassie:langchange', false, false);
                event.detail = detail;
            }
            root.dispatchEvent(event);
        }
        return current;
    }

    function buildToggle() {
        var host = root.document.querySelector('[data-lang-toggle]');
        var box = root.document.createElement('div');
        box.className = 'lang-toggle' + (host ? '' : ' lang-toggle--floating');
        box.setAttribute('role', 'group');
        box.setAttribute('aria-label', 'Language / 语言');

        var labels = [['zh', '中文'], ['en', 'EN']];
        for (var i = 0; i < labels.length; i += 1) {
            var button = root.document.createElement('button');
            button.type = 'button';
            button.className = 'lang-toggle__option';
            button.setAttribute('data-lang', labels[i][0]);
            button.setAttribute('aria-pressed', 'false');
            button.textContent = labels[i][1];
            button.addEventListener('click', (function (code) {
                return function (event) {
                    if (event && event.preventDefault) event.preventDefault();
                    setLang(code);
                };
            })(labels[i][0]));
            box.appendChild(button);
        }

        if (host) {
            host.appendChild(box);
        } else if (root.document.body) {
            root.document.body.appendChild(box);
        }
        toggleEl = box;
        return box;
    }

    function register(dict) {
        if (!dict) return api;
        SUPPORTED.forEach(function (lang) {
            var table = dict[lang];
            if (!table) return;
            for (var key in table) {
                if (Object.prototype.hasOwnProperty.call(table, key)) {
                    dictionary[lang][key] = table[key];
                }
            }
        });
        apply();
        return api;
    }

    function extend(dict) {
        return register(dict);
    }

        function apiQuery(url) {
        var sep = url.indexOf('?') >= 0 ? '&' : '?';
        return url + sep + 'lang=' + current;
    }

    function apiHeaders(extra) {
        var headers = extra ? Object.assign({}, extra) : {};
        headers['X-Cassie-Lang'] = current;
        return headers;
    }

    function init() {
        // ?lang= 是显式要求，优先级最高，并且记下来；
        // 而「按浏览器语言猜出来」的结果不写盘——那不算用户的决定，
        // 否则用户换了系统语言、界面却还停在旧语言上。
        var forced = readUrlLang();
        current = forced || detect();
        if (forced) writeStored(forced);
        if (root.document && root.document.documentElement) {
            root.document.documentElement.setAttribute('lang', HTML_LANG[current] || current);
            root.document.documentElement.setAttribute('data-lang', current);
        }
        apply();
        if (!mounted) {
            mounted = true;
            buildToggle();
            syncToggle();
        }
    }

    var api = {
        register: register,
        extend: extend,
        t: t,
        tf: tf,
        has: has,
        apply: apply,
        setLang: setLang,
        init: init,
        apiQuery: apiQuery,
        apiHeaders: apiHeaders,
        get lang() { return current; },
        supported: SUPPORTED.slice()
    };

    root.CASSIE_I18N = api;
        if (!root.t) root.t = t;
    if (!root.tf) root.tf = tf;

    if (root.document && root.document.readyState === 'loading') {
        root.document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(typeof window !== 'undefined' ? window : this);
