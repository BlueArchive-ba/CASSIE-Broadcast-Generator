/* C.A.S.S.I.E. — 词汇检测工具（tools/word_search）中英词表 */
(function (root) {
    'use strict';

    var i18n = root.CASSIE_I18N;
    if (!i18n) return;
    var doc = root.document;

    i18n.register({
        zh: {
            'ws.title': 'C.A.S.S.I.E. 词汇检测工具',
            'ws.subtitle': '检测广播内容中每个单词的可播放性',
            'ws.backHome': '返回主页',
            'ws.backHomeTitle': '返回 C.A.S.S.I.E. 主控制台',

            'ws.inputLabel': '输入广播内容',
            'ws.inputPlaceholder': '输入广播内容，全小写，标点符号左右加空格...',

            'ws.btn.check': '检测',
            'ws.btn.clear': '清空',
            'ws.btn.special': '特殊文件列表',

            'ws.resultLabel': '检测结果',
            'ws.resultWaiting': '等待检测...',
            'ws.resultEmpty': '请输入内容',
            'ws.resultNeedInput': '请输入广播内容',

            'ws.specialLabel': '特殊音频文件',
            'ws.specialHint': '点击「特殊文件列表」查看',
            'ws.specialNone': '没有找到特殊音频文件',

            'ws.status.ready': '就绪',
            'ws.status.checking': '检测中',
            'ws.status.done': '检测完成',
            'ws.status.cleared': '已清空',
            'ws.count.words': '词汇总数：',
            'ws.count.loaded': '已加载：',

            /* 汇总与计数（{count} / {total} / {found} / {missing} 由 JS 填充） */
            'ws.summary.total': '总计 {count} 个段',
            'ws.summary.found': '找到 {count} 个',
            'ws.summary.missing': '缺失 {count} 个',
            'ws.summary.specialTotal': '共 {count} 个特殊文件',

            'ws.match.punctuation': '{word}（标点）',
            'ws.match.mtf': 'mtf → mobile task force',
            'ws.match.glitch': '{word}（故障音效）',
            'ws.match.phrase': '{word} → {target}',
            'ws.match.phraseMissing': '{word}（短语未找到）',
            'ws.match.nato': '{word} → {target}',
            'ws.match.letter': '{word} → {target}',
            'ws.match.tEd': '{word} → {target} + t-ed',
            'ws.match.tEdSplit': '{word} → {target} + t + ed',
            'ws.match.ed': '{word} → {target} + -ed',
            'ws.match.ish': '{word} → {target} + -ish',
            'ws.match.like': '{word} → {target} + -like',
            'ws.match.prefix': '{word} → {prefix} + {target}',
            'ws.match.unknown': '未知',

            'ws.aria.status': '检测状态',
            'ws.aria.counts': '词汇统计',
            'ws.aria.results': '检测结果列表',
            'ws.aria.special': '特殊音频文件列表'
        },
        en: {
            'ws.title': 'C.A.S.S.I.E. Word Checker',
            'ws.subtitle': 'Checks every word in a broadcast for playable audio',
            'ws.backHome': 'Back to home',
            'ws.backHomeTitle': 'Back to the C.A.S.S.I.E. console',

            'ws.inputLabel': 'Broadcast text',
            'ws.inputPlaceholder': 'Paste the broadcast text: all lowercase, spaces around punctuation...',

            'ws.btn.check': 'Check',
            'ws.btn.clear': 'Clear',
            'ws.btn.special': 'Special files',

            'ws.resultLabel': 'Check results',
            'ws.resultWaiting': 'Waiting for a check...',
            'ws.resultEmpty': 'Enter some text first',
            'ws.resultNeedInput': 'Enter the broadcast text first',

            'ws.specialLabel': 'Special audio files',
            'ws.specialHint': 'Click “Special files” to list them',
            'ws.specialNone': 'No special audio files found',

            'ws.status.ready': 'Ready',
            'ws.status.checking': 'Checking',
            'ws.status.done': 'Check complete',
            'ws.status.cleared': 'Cleared',
            'ws.count.words': 'Words: ',
            'ws.count.loaded': 'Loaded: ',

            /* Summary & counts ({count} / {total} / {found} / {missing} filled by JS) */
            'ws.summary.total': '{count} segments in total',
            'ws.summary.found': '{count} found',
            'ws.summary.missing': '{count} missing',
            'ws.summary.specialTotal': '{count} special files in total',

            /* Per-word resolution: how the entry was matched */
            'ws.match.punctuation': '{word} (punctuation)',
            'ws.match.mtf': 'mtf → mobile task force',
            'ws.match.glitch': '{word} (glitch sound)',
            'ws.match.phrase': '{word} → {target}',
            'ws.match.phraseMissing': '{word} (phrase not found)',
            'ws.match.nato': '{word} → {target}',
            'ws.match.letter': '{word} → {target}',
            'ws.match.tEd': '{word} → {target} + t-ed',
            'ws.match.tEdSplit': '{word} → {target} + t + ed',
            'ws.match.ed': '{word} → {target} + -ed',
            'ws.match.ish': '{word} → {target} + -ish',
            'ws.match.like': '{word} → {target} + -like',
            'ws.match.prefix': '{word} → {prefix} + {target}',
            'ws.match.unknown': 'unknown',

            'ws.aria.status': 'Check status',
            'ws.aria.counts': 'Word counts',
            'ws.aria.results': 'Check result list',
            'ws.aria.special': 'Special audio file list'
        }
    });

    var t = function (key, vars) { return i18n.t(key, vars); };

    function setText(id, text) {
        var el = doc.getElementById(id);
        if (el) el.textContent = text;
    }

    function displayFor(result) {
        if (!result) return t('ws.match.unknown');
        var type = result.type;
        var text = result.display || '';

        /* 命中的词条本身是英文，直接取基准词；display 里可能带「 → 拆分」后缀 */
        var word = text.split(' → ')[0];
        var target = text.indexOf(' → ') >= 0 ? text.slice(text.indexOf(' → ') + 3) : '';

        switch (type) {
            case 'exact':
                return word;
            case 'punctuation':
                return t('ws.match.punctuation', { word: word });
            case 'mtf':
                return t('ws.match.mtf');
            case 'glitch':
                return t('ws.match.glitch', { word: word });
            case 'phrase':
                return t('ws.match.phrase', { word: word, target: target });
            case 'phrase_missing':
                return t('ws.match.phraseMissing', { word: word });
            case 'nato':
                return t('ws.match.nato', { word: word, target: target });
            case 'letter':
                return t('ws.match.letter', { word: word, target: target });
            case 't_ed':
                return t('ws.match.tEd', { word: word, target: target });
            case 't_ed_split':
                return t('ws.match.tEdSplit', { word: word, target: target });
            case 'ed':
                return t('ws.match.ed', { word: word, target: target });
            case 'ish':
                return t('ws.match.ish', { word: word, target: target });
            case 'like':
                return t('ws.match.like', { word: word, target: target });
            case 'prefix': {
                var plus = target.split(' + ');
                return t('ws.match.prefix', { word: word, prefix: plus[0] || '', target: plus[1] || '' });
            }
            default:
                return text;
        }
    }

    function syncResults() {
        var output = doc.getElementById('outputBox');
        if (!output) return;
        if (output.getAttribute('data-state') === 'waiting') {
            setText('outputBox', '');
            output.textContent = t('ws.resultWaiting');
            return;
        }

        var count = parseInt(output.getAttribute('data-total'), 10) || 0;
        if (!count) {
            output.textContent = t('ws.resultEmpty');
            return;
        }

        var results = root.__cassieWordSearch && root.__cassieWordSearch.lastResults;
        if (!results || !results.length) {
            output.textContent = t('ws.resultEmpty');
            return;
        }

        var found = parseInt(output.getAttribute('data-found'), 10) || 0;
        var missing = parseInt(output.getAttribute('data-missing'), 10) || 0;

        var separator = i18n.lang === 'zh' ? '，' : ', ';
        var fragment = doc.createDocumentFragment();
        results.forEach(function (result) {
            var span = doc.createElement('span');
            span.className = colorClassFor(result);
            span.textContent = displayFor(result) + ' ';
            fragment.appendChild(span);
        });

        var summary = doc.createElement('div');
        summary.className = 'result-summary';
        [['ws.summary.total', count, 'summary-total'],
         ['ws.summary.found', found, 'summary-found'],
         ['ws.summary.missing', missing, 'summary-missing']].forEach(function (item, index) {
            if (index > 0) summary.appendChild(doc.createTextNode(separator));
            var label = doc.createElement('span');
            label.textContent = t(item[0], { count: item[1] });
            label.className = 'result-summary__' + item[2];
            summary.appendChild(label);
        });

        output.textContent = '';
        output.appendChild(fragment);
        output.appendChild(summary);
        output.setAttribute('data-total', String(count));
    }

    function colorClassFor(result) {
        if (!result) return 'word-error';
        if (result.found) {
            if (result.type === 'exact') return 'word-found';
            if (result.type === 'nato' || result.type === 'letter' || result.type === 'phrase') return 'word-split';
            if (['t_ed', 't_ed_split', 'ed', 'ish', 'like', 'prefix'].indexOf(result.type) >= 0) return 'word-split';
            if (['punctuation', 'mtf', 'glitch'].indexOf(result.type) >= 0) return 'word-warning';
            return 'word-found';
        }
        return 'word-error';
    }

    function syncStatus() {
        var status = doc.getElementById('statusText');
        if (status && !status.getAttribute('data-i18n')) {
            status.textContent = t('ws.status.' + (status.getAttribute('data-state') || 'ready'));
        }
        var special = doc.getElementById('specialOutput');
        if (special && special.getAttribute('data-state') === 'files') {
            var total = special.getAttribute('data-count');
            var line = special.querySelector('.special-total');
            if (line) line.textContent = t('ws.summary.specialTotal', { count: total });
        }
    }

    function syncPage() {
        if (!doc || !doc.body) return;
        syncResults();
        syncStatus();
    }

    root.addEventListener('cassie:langchange', function () {
        syncPage();
    });

    /* 用 setTimeout 排在 i18n.js 的 init 之后，保证读到最终语言 */
    function boot() {
        root.setTimeout(syncPage, 0);
    }

    if (doc) {
        if (doc.readyState === 'loading') {
            doc.addEventListener('DOMContentLoaded', boot);
        } else {
            boot();
        }
    }
})(typeof window !== 'undefined' ? window : this);
