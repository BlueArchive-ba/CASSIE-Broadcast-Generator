        var enableBell = false;
        var enableSpecialBell = false;
        var enableNumberReading = false;
        var verboseMode = false;
        var presets = {};
        var selectedPresets = [];

        function i18nApi() {
            return window.CASSIE_I18N || null;
        }

        function i18n(key, fallback, vars) {
            var api = i18nApi();
            if (api && api.tf) return api.tf(key, fallback, vars);
            var text = fallback === undefined ? key : fallback;
            if (vars && typeof text === 'string') {
                text = text.replace(/\{(\w+)\}/g, function(match, name) {
                    return Object.prototype.hasOwnProperty.call(vars, name)
                        ? String(vars[name]) : match;
                });
            }
            return text;
        }

        function apiFetch(url, options) {
            var api = i18nApi();
            var opts = options || {};
            if (api && api.apiHeaders) {
                opts.headers = api.apiHeaders(opts.headers || {});
            }
            return fetch(api && api.apiQuery ? api.apiQuery(url) : url, opts);
        }

        var enableBellCheckbox = document.getElementById('enableBell');
        var enableSpecialBellCheckbox = document.getElementById('enableSpecialBell');
        var enableNumberReadingCheckbox = document.getElementById('enableNumberReading');
        var verboseModeCheckbox = document.getElementById('verboseMode');
        var broadcastInput = document.getElementById('broadcastInput');
        var playBtn = document.getElementById('playBtn');
        var exportBtn = document.getElementById('exportBtn');
        var spellCheckBtn = document.getElementById('spellCheckBtn');
        var clearTerminalBtn = document.getElementById('clearTerminal');
        var terminalContent = document.getElementById('terminalContent');
        var statusText = document.getElementById('statusText');
        var volumeFill = document.getElementById('volumeFill');
        var monitorAudioBtn = document.getElementById('monitorAudioBtn');
        var presetBtn = document.getElementById('presetBtn');
        var presetModal = document.getElementById('presetModal');
        var closeModal = document.getElementById('closeModal');
        var presetList = document.getElementById('presetList');
        var presetName = document.getElementById('presetName');
        var presetContent = document.getElementById('presetContent');
        var savePreset = document.getElementById('savePreset');
        var importPreset = document.getElementById('importPreset');
        var playSelectedBtn = document.getElementById('playSelectedBtn');
        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'preset-checkbox';

var advancedBtn = document.getElementById('advancedBtn');
var advancedModal = document.getElementById('advancedModal');
var closeAdvanced = document.getElementById('closeAdvanced');

var bellLeadTimeInput = document.getElementById('bellLeadTime');
var bellExtraDurationInput = document.getElementById('bellExtraDuration');
var specialBellStartInput = document.getElementById('specialBellStart');
var specialBellEndInput = document.getElementById('specialBellEnd');

var effectToggle = document.getElementById('broadcastEffectToggle');
var lowCutFreq = document.getElementById('lowCutFreq');
var lowCutFreqValue = document.getElementById('lowCutFreqValue');
var highCutFreq = document.getElementById('highCutFreq');
var highCutFreqValue = document.getElementById('highCutFreqValue');
var midBoostGain = document.getElementById('midBoostGain');
var midBoostGainValue = document.getElementById('midBoostGainValue');
var overdriveGain = document.getElementById('overdriveGain');
var overdriveGainValue = document.getElementById('overdriveGainValue');
var clipThreshold = document.getElementById('clipThreshold');
var clipThresholdValue = document.getElementById('clipThresholdValue');
var compressorThreshold = document.getElementById('compressorThreshold');
var compressorThresholdValue = document.getElementById('compressorThresholdValue');
var compressorRatio = document.getElementById('compressorRatio');
var compressorRatioValue = document.getElementById('compressorRatioValue');
var reverbPreDelay = document.getElementById('reverbPreDelay');
var reverbPreDelayValue = document.getElementById('reverbPreDelayValue');
var reverbRoomSize = document.getElementById('reverbRoomSize');
var reverbRoomSizeValue = document.getElementById('reverbRoomSizeValue');
var reverbDecayTime = document.getElementById('reverbDecayTime');
var reverbDecayTimeValue = document.getElementById('reverbDecayTimeValue');
var reverbDamping = document.getElementById('reverbDamping');
var reverbDampingValue = document.getElementById('reverbDampingValue');
var reverbDiffusion = document.getElementById('reverbDiffusion');
var reverbDiffusionValue = document.getElementById('reverbDiffusionValue');
var reverbTailBrightness = document.getElementById('reverbTailBrightness');
var reverbTailBrightnessValue = document.getElementById('reverbTailBrightnessValue');
var reverbWet = document.getElementById('reverbWet');
var reverbWetValue = document.getElementById('reverbWetValue');
var trebleStretch = document.getElementById('trebleStretch');
var trebleStretchValue = document.getElementById('trebleStretchValue');
var trebleTailGain = document.getElementById('trebleTailGain');
var trebleTailGainValue = document.getElementById('trebleTailGainValue');
var noiseVolume = document.getElementById('noiseVolume');
var noiseVolumeValue = document.getElementById('noiseVolumeValue');
var effectControls = document.getElementById('effectControls');

var spatialModeSelect = document.getElementById('spatialMode');
var spatialModeHint = document.getElementById('spatialModeHint');
var spatialQuality = document.getElementById('spatialQuality');
var spatialQualityValue = document.getElementById('spatialQualityValue');
var spatialQualitySummary = document.getElementById('spatialQualitySummary');

var saveAdvancedBtn = document.getElementById('saveAdvanced');
var resetAdvancedBtn = document.getElementById('resetAdvanced');

var SPATIAL_QUALITY_LEVELS = [
    { level: 0, nameKey: 'quality.0.name', name: '原始',
      summaryKey: 'quality.0.summary', summary: '不削减，与历史版本完全一致' },
    { level: 1, nameKey: 'quality.1.name', name: '轻度',
      summaryKey: 'quality.1.summary', summary: '块长翻倍、拖尾略收短；几乎听不出差别' },
    { level: 2, nameKey: 'quality.2.name', name: '中度',
      summaryKey: 'quality.2.summary', summary: '块长再翻倍、拖尾明显收短；拖尾变得短促' },
    { level: 3, nameKey: 'quality.3.name', name: '最大加速',
      summaryKey: 'quality.3.summary', summary: '块长拉满、拖尾最短；只保留紧贴单词的回声' },
    { level: 4, nameKey: 'quality.4.name', name: '激进',
      summaryKey: 'quality.4.summary', summary: '拖尾再收一半；混响变成一层薄薄的尾音' },
    { level: 5, nameKey: 'quality.5.name', name: '极限',
      summaryKey: 'quality.5.summary', summary: '拖尾约 1/3 秒；只能听出"刚说完还有一点回响"' },
    { level: 6, nameKey: 'quality.6.name', name: '单声道混响',
      summaryKey: 'quality.6.summary', summary: '极限档基础上把立体声混响合成单声道，再快近一倍' }
];

var SPATIAL_MODE_HINTS = {
    word: { key: 'mode.word', text: '逐词：每个单词各自加一次混响，拖尾逐词叠加，最贴近原版听感。耗时随词数线性增长。' },
    sentence: { key: 'mode.sentence', text: '整句：先把整句话拼好，再整体做一次后处理。拖尾只算一次，长广播明显更快；代价是逐词的音高/效果差异会被统一。' }
};

function on(element, event, handler, options) {
    if (!element) {
        console.warn('[CASSIE] 跳过绑定：页面中找不到对应元素', event, handler && handler.name);
        return false;
    }
    element.addEventListener(event, handler, options);
    return true;
}

function textOf(element, value) {
    if (element) element.textContent = value;
}

function syncRangeFill(slider) {
    if (!slider || slider.type !== 'range') return;
    if (!slider.style || typeof slider.style.setProperty !== 'function') return;
    var min = parseFloat(slider.min);
    var max = parseFloat(slider.max);
    var value = parseFloat(slider.value);
    if (!isFinite(min)) min = 0;
    if (!isFinite(max) || max === min) max = min + 1;
    if (!isFinite(value)) value = min;
    var ratio = Math.min(1, Math.max(0, (value - min) / (max - min)));
    slider.style.setProperty('--fill', (ratio * 100).toFixed(2) + '%');
}

function syncAllRangeFills() {
    if (!document.querySelectorAll) return;
    var all = document.querySelectorAll('input[type="range"]');
    for (var i = 0; i < all.length; i += 1) {
        syncRangeFill(all[i]);
    }
}

function resolveQualityEntry(entry) {
    if (!entry) return { name: '', summary: '' };
    return {
        name: entry.nameKey ? i18n(entry.nameKey, entry.name) : entry.name,
        summary: entry.summaryKey ? i18n(entry.summaryKey, entry.summary) : entry.summary
    };
}

function syncSpatialControls() {
    if (spatialQuality) {
        var level = Number(spatialQuality.value) || 0;
        var entry = resolveQualityEntry(SPATIAL_QUALITY_LEVELS[level] || SPATIAL_QUALITY_LEVELS[0]);
        textOf(spatialQualityValue, entry.name);
        textOf(spatialQualitySummary, entry.summary);
        spatialQuality.setAttribute('aria-valuetext',
            i18n('quality.aria', '{name}：{summary}', { name: entry.name, summary: entry.summary }));
    }
    if (spatialModeSelect) {
        var hint = SPATIAL_MODE_HINTS[spatialModeSelect.value];
        textOf(spatialModeHint, hint ? i18n(hint.key, hint.text) : '');
    }
}

function syncSliders() {
    syncSpatialControls();
    textOf(lowCutFreqValue, lowCutFreq.value);
    textOf(highCutFreqValue, highCutFreq.value);
    textOf(midBoostGainValue, Number(midBoostGain.value).toFixed(1));
    textOf(overdriveGainValue, Number(overdriveGain.value).toFixed(1));
    textOf(clipThresholdValue, Number(clipThreshold.value).toFixed(2));
    textOf(compressorThresholdValue, Number(compressorThreshold.value).toFixed(1));
    textOf(compressorRatioValue, Number(compressorRatio.value).toFixed(1));
    textOf(reverbPreDelayValue, reverbPreDelay.value);
    textOf(reverbRoomSizeValue, Number(reverbRoomSize.value).toFixed(2));
    textOf(reverbDecayTimeValue, Number(reverbDecayTime.value).toFixed(1));
    textOf(reverbDampingValue, reverbDamping.value);
    textOf(reverbDiffusionValue, Number(reverbDiffusion.value).toFixed(2));
    textOf(reverbTailBrightnessValue, Number(reverbTailBrightness.value).toFixed(2));
    textOf(reverbWetValue, Number(reverbWet.value).toFixed(2));
    textOf(trebleStretchValue, trebleStretch.value);
    textOf(trebleTailGainValue, trebleTailGain.value);
    textOf(noiseVolumeValue, Number(noiseVolume.value).toFixed(1));
}

var advancedSliders = [
    lowCutFreq, highCutFreq, midBoostGain, overdriveGain, clipThreshold,
    compressorThreshold, compressorRatio, reverbPreDelay, reverbRoomSize,
    reverbDecayTime, reverbDamping, reverbDiffusion, reverbTailBrightness,
    reverbWet, trebleStretch, trebleTailGain, noiseVolume,
    spatialQuality
].filter(Boolean);

if (advancedSliders.length < 18) {
    console.warn('[CASSIE] 高级设置里只找到 ' + advancedSliders.length +
                 '/18 个滑块，页面可能不是最新版本，请强制刷新（Ctrl+F5）');
}

advancedSliders.forEach(function(slider) {
    on(slider, 'input', syncSliders);
});

on(spatialModeSelect, 'change', syncSpatialControls);
syncSpatialControls();

document.addEventListener('input', function(e) {
    var target = e.target;
    if (target && target.type === 'range') syncRangeFill(target);
}, true);

function updateEffectControls() {
    var enabled = effectToggle.checked;
    var inputs = effectControls.querySelectorAll('input, select');
    inputs.forEach(function(input) {
        input.disabled = !enabled;
    });
    effectControls.classList.toggle('is-disabled', !enabled);
    effectControls.style.opacity = enabled ? '1' : '0.4';
    effectControls.style.pointerEvents = enabled ? 'auto' : 'none';
}

function settingValue(data, key, fallback) {
    return data[key] === undefined || data[key] === null ? fallback : data[key];
}

function numberValue(value, fallback) {
    var parsed = parseFloat(value);
    return isFinite(parsed) ? parsed : fallback;
}

function showWarningModal(message) {

    var overlay = document.createElement('div');
    overlay.className = 'warning-overlay';
    var modal = document.createElement('div');
    modal.className = 'warning-modal';
    var content = document.createElement('div');
    content.className = 'warning-content';
    var text = document.createElement('p');
    text.textContent = message;
    var button = document.createElement('button');
    button.textContent = i18n('msg.gotIt', '知道了');
    button.className = 'warning-btn';
    button.addEventListener('click', function() {
        document.body.removeChild(overlay);
    });
    content.appendChild(text);
    content.appendChild(button);
    modal.appendChild(content);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) {
            document.body.removeChild(overlay);
        }
    });
}

on(effectToggle, 'change', function() {
    updateEffectControls();
    if (this.checked) {
        showWarningModal(i18n('warn.experimental', '此功能是还未正式完成的试验性功能，效果可能无法达到要求'));
    }
});

var ADVANCED_DEFAULTS = {
    bell_lead_time: 3.0,
    bell_extra_duration: 3.0,
    special_bell_start: 'bell_start.wav',
    special_bell_end: 'bell_end.wav',
    broadcast_effect_enabled: false,
    low_cut_freq: 0,
    high_cut_freq: 0,
    mid_boost_gain: 2.0,
    overdrive_gain: 0.0,
    clip_threshold: 0.0,
    compressor_threshold: -12.0,
    compressor_ratio: 6.0,
    reverb_pre_delay: 18.0,
    reverb_room_size: 1.0,
    reverb_decay_time: 5.5,
    reverb_damping: 4000.0,
    reverb_diffusion: 0.72,
    reverb_tail_brightness: 0.55,
    reverb_wet: 0.35,
    treble_stretch: 800.0,
    treble_tail_gain: -28.0,
    noise_volume: -35.0,
    spatial_quality: 0,
    spatial_mode: 'word'
};

function applyAdvancedSettings(data) {
    var source = data || {};
    if (source.reverb_pre_delay === undefined && source.reverb_delay !== undefined) {
        source.reverb_pre_delay = source.reverb_delay;
    }
    if (source.reverb_decay_time === undefined && source.reverb_decay !== undefined) {
        source.reverb_decay_time = Math.max(0.2, Number(source.reverb_decay) / 1000);
    }
    if (source.reverb_damping === undefined && source.reverb_lowpass !== undefined) {
        source.reverb_damping = source.reverb_lowpass;
    }

    bellLeadTimeInput.value = settingValue(source, 'bell_lead_time', ADVANCED_DEFAULTS.bell_lead_time);
    bellExtraDurationInput.value = settingValue(source, 'bell_extra_duration', ADVANCED_DEFAULTS.bell_extra_duration);
    specialBellStartInput.value = settingValue(source, 'special_bell_start', ADVANCED_DEFAULTS.special_bell_start);
    specialBellEndInput.value = settingValue(source, 'special_bell_end', ADVANCED_DEFAULTS.special_bell_end);
    effectToggle.checked = !!settingValue(source, 'broadcast_effect_enabled', ADVANCED_DEFAULTS.broadcast_effect_enabled);
    lowCutFreq.value = settingValue(source, 'low_cut_freq', ADVANCED_DEFAULTS.low_cut_freq);
    highCutFreq.value = settingValue(source, 'high_cut_freq', ADVANCED_DEFAULTS.high_cut_freq);
    midBoostGain.value = settingValue(source, 'mid_boost_gain', ADVANCED_DEFAULTS.mid_boost_gain);
    overdriveGain.value = settingValue(source, 'overdrive_gain', ADVANCED_DEFAULTS.overdrive_gain);
    clipThreshold.value = settingValue(source, 'clip_threshold', ADVANCED_DEFAULTS.clip_threshold);
    compressorThreshold.value = settingValue(source, 'compressor_threshold', ADVANCED_DEFAULTS.compressor_threshold);
    compressorRatio.value = settingValue(source, 'compressor_ratio', ADVANCED_DEFAULTS.compressor_ratio);
    reverbPreDelay.value = settingValue(source, 'reverb_pre_delay', ADVANCED_DEFAULTS.reverb_pre_delay);
    reverbRoomSize.value = settingValue(source, 'reverb_room_size', ADVANCED_DEFAULTS.reverb_room_size);
    reverbDecayTime.value = settingValue(source, 'reverb_decay_time', ADVANCED_DEFAULTS.reverb_decay_time);
    reverbDamping.value = settingValue(source, 'reverb_damping', ADVANCED_DEFAULTS.reverb_damping);
    reverbDiffusion.value = settingValue(source, 'reverb_diffusion', ADVANCED_DEFAULTS.reverb_diffusion);
    reverbTailBrightness.value = settingValue(source, 'reverb_tail_brightness', ADVANCED_DEFAULTS.reverb_tail_brightness);
    reverbWet.value = settingValue(source, 'reverb_wet', ADVANCED_DEFAULTS.reverb_wet);
    trebleStretch.value = settingValue(source, 'treble_stretch', ADVANCED_DEFAULTS.treble_stretch);
    trebleTailGain.value = settingValue(source, 'treble_tail_gain', ADVANCED_DEFAULTS.treble_tail_gain);
    noiseVolume.value = settingValue(source, 'noise_volume', ADVANCED_DEFAULTS.noise_volume);
    spatialQuality.value = settingValue(source, 'spatial_quality', ADVANCED_DEFAULTS.spatial_quality);
    if (spatialModeSelect) {
        var mode = settingValue(source, 'spatial_mode', ADVANCED_DEFAULTS.spatial_mode);
        spatialModeSelect.value = (mode === 'sentence') ? 'sentence' : 'word';
    }

    syncSliders();
    updateEffectControls();
    syncAllRangeFills();
}

var qualityLevelsFromServer = false;

function adoptServerQualityLevels(levels) {
    if (!Array.isArray(levels) || !levels.length) return;
    SPATIAL_QUALITY_LEVELS = levels.map(function(item) {
        return {
            level: Number(item.level) || 0,
            name: item.name || String(item.level),
            summary: item.summary || ''
        };
    });
    qualityLevelsFromServer = true;
    if (spatialQuality) {
        spatialQuality.max = String(SPATIAL_QUALITY_LEVELS.length - 1);
    }
    syncSpatialControls();
}

function refreshQualityLevels() {
    if (!qualityLevelsFromServer) {
        syncSpatialControls();
        return;
    }
    apiFetch('/get_advanced_settings')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            adoptServerQualityLevels(data && data.spatial_quality_levels);
        })
        .catch(function() { syncSpatialControls(); });
}

function openAdvancedModal() {
    apiFetch('/get_advanced_settings')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            adoptServerQualityLevels(data && data.spatial_quality_levels);
            applyAdvancedSettings(data);
            advancedModal.classList.add('show');
        })
        .catch(function() {
            applyAdvancedSettings(null);
            advancedModal.classList.add('show');
        });
}

on(advancedBtn, 'click', function() {
    // 上一次保存还在路上时先别读服务端，否则会把刚改的值覆盖回旧的
    if (advancedSaving) {
        pendingAdvancedAction = 'open';
        return;
    }
    openAdvancedModal();
});

on(resetAdvancedBtn, 'click', function() {
    applyAdvancedSettings(ADVANCED_DEFAULTS);
    addTerminalLine(i18n('msg.advancedReset', '已恢复高级设置默认值，点击“保存设置”生效'), 'normal');
});

function collectAdvancedSettings() {
    return {
        bell_lead_time: numberValue(bellLeadTimeInput.value, ADVANCED_DEFAULTS.bell_lead_time),
        bell_extra_duration: numberValue(bellExtraDurationInput.value, ADVANCED_DEFAULTS.bell_extra_duration),
        special_bell_start: specialBellStartInput.value,
        special_bell_end: specialBellEndInput.value,
        broadcast_effect_enabled: effectToggle.checked,
        low_cut_freq: numberValue(lowCutFreq.value, ADVANCED_DEFAULTS.low_cut_freq),
        high_cut_freq: numberValue(highCutFreq.value, ADVANCED_DEFAULTS.high_cut_freq),
        mid_boost_gain: numberValue(midBoostGain.value, ADVANCED_DEFAULTS.mid_boost_gain),
        overdrive_gain: numberValue(overdriveGain.value, ADVANCED_DEFAULTS.overdrive_gain),
        clip_threshold: numberValue(clipThreshold.value, ADVANCED_DEFAULTS.clip_threshold),
        compressor_threshold: numberValue(compressorThreshold.value, ADVANCED_DEFAULTS.compressor_threshold),
        compressor_ratio: numberValue(compressorRatio.value, ADVANCED_DEFAULTS.compressor_ratio),
        reverb_pre_delay: numberValue(reverbPreDelay.value, ADVANCED_DEFAULTS.reverb_pre_delay),
        reverb_room_size: numberValue(reverbRoomSize.value, ADVANCED_DEFAULTS.reverb_room_size),
        reverb_decay_time: numberValue(reverbDecayTime.value, ADVANCED_DEFAULTS.reverb_decay_time),
        reverb_damping: numberValue(reverbDamping.value, ADVANCED_DEFAULTS.reverb_damping),
        reverb_diffusion: numberValue(reverbDiffusion.value, ADVANCED_DEFAULTS.reverb_diffusion),
        reverb_tail_brightness: numberValue(reverbTailBrightness.value, ADVANCED_DEFAULTS.reverb_tail_brightness),
        reverb_wet: numberValue(reverbWet.value, ADVANCED_DEFAULTS.reverb_wet),
        treble_stretch: numberValue(trebleStretch.value, ADVANCED_DEFAULTS.treble_stretch),
        treble_tail_gain: numberValue(trebleTailGain.value, ADVANCED_DEFAULTS.treble_tail_gain),
        noise_volume: numberValue(noiseVolume.value, ADVANCED_DEFAULTS.noise_volume),
    spatial_quality: Number(spatialQuality.value) || 0,
    spatial_mode: spatialModeSelect && spatialModeSelect.value === 'sentence' ? 'sentence' : 'word',
        noise_type: 'pink'
    };
}

var advancedSaving = false;
var pendingAdvancedAction = null;

function hideAdvancedModal() {
    advancedModal.classList.remove('show');
}

function saveAdvancedSettings(closeAfterSave) {
    if (advancedSaving) {
        if (closeAfterSave) pendingAdvancedAction = 'close';
        return;
    }
    advancedSaving = true;
    if (saveAdvancedBtn) saveAdvancedBtn.disabled = true;

    var payload;
    try {
        payload = collectAdvancedSettings();
    } catch (error) {
        advancedSaving = false;
        if (saveAdvancedBtn) saveAdvancedBtn.disabled = false;
        addTerminalLine(i18n('msg.saveFailedValues',
            '保存失败（无法读取面板数值）: {error}', { error: error }), 'error');
        if (closeAfterSave) hideAdvancedModal();
        return;
    }

    apiFetch('/save_advanced_settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(function(res) {
        return res.json().catch(function() {
            throw new Error(i18n('msg.badJson',
                '服务端返回的不是 JSON（HTTP {status}）', { status: res.status }));
        });
    })
    .then(function(data) {
        if (data && data.success) {
            addTerminalLine(i18n('msg.advancedSaved', '高级设置已保存'), 'normal');
        } else {
            addTerminalLine(i18n('msg.saveFailed', '保存失败: {error}', {
                error: (data && data.message) || i18n('common.unknownReason', '未知原因')
            }), 'error');
        }
    })
    .catch(function(err) {
        addTerminalLine(i18n('msg.saveFailed', '保存失败: {error}', { error: err }), 'error');
    })
    .then(function() {
        advancedSaving = false;
        if (saveAdvancedBtn) saveAdvancedBtn.disabled = false;
        if (closeAfterSave) hideAdvancedModal();
        var queued = pendingAdvancedAction;
        pendingAdvancedAction = null;
        if (queued === 'close') {
            hideAdvancedModal();
        } else if (queued === 'open') {
            openAdvancedModal();
        }
    });
}

on(saveAdvancedBtn, 'click', function() {
    saveAdvancedSettings(true);
});

on(closeAdvanced, 'click', function() {
    saveAdvancedSettings(true);
});

on(advancedModal, 'click', function(e) {
    if (e.target === advancedModal) {
        saveAdvancedSettings(true);
    }
});

document.addEventListener('keydown', function(e) {
    var key = e.key || e.keyCode;
    if (key !== 'Escape' && key !== 'Esc' && key !== 27) return;
    if (!advancedModal || !advancedModal.classList.contains('show')) return;
    if (e.preventDefault) e.preventDefault();
    saveAdvancedSettings(true);
});

        on(enableBellCheckbox, 'change', function() {
            enableBell = this.checked;
            enableSpecialBellCheckbox.disabled = !enableBell;
            if (!enableBell) enableSpecialBellCheckbox.checked = false;
        });
        on(enableSpecialBellCheckbox, 'change', function() { enableSpecialBell = this.checked; });
        on(enableNumberReadingCheckbox, 'change', function() { enableNumberReading = this.checked; });
        on(verboseModeCheckbox, 'change', function() { verboseMode = this.checked; });

        function addTerminalLine(text, type, key) {
            var line = document.createElement('div');
            line.className = 'terminal-line ' + type;
            line.textContent = text;
            if (key) line.setAttribute('data-i18n', key);
            terminalContent.appendChild(line);
            line.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function addTerminalLineWithHighlight(text, notFoundWords) {
            var line = document.createElement('div');
            line.className = 'terminal-line spellcheck';
            var words = text.split(' ');
            var html = '';
            for (var i = 0; i < words.length; i++) {
                var word = words[i];
                // 用户输入，进 innerHTML 前必须转义
                var safe = word.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                if (notFoundWords.indexOf(word) !== -1) {
                    html += '<span class="not-found-word">' + safe + '</span> ';
                } else {
                    html += safe + ' ';
                }
            }
            line.innerHTML = html;
            terminalContent.appendChild(line);
            line.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }

        function clearTerminal() {
            terminalContent.innerHTML = '';
            addTerminalLine(i18n('msg.ready', '就绪。请输入广播内容。'), 'normal', 'msg.ready');
        }
        on(clearTerminalBtn, 'click', clearTerminal);

        on(spellCheckBtn, 'click', function() {
            var text = broadcastInput.value.trim();
            if (!text) {
                addTerminalLine(i18n('msg.needInput', '请输入广播内容'), 'error');
                return;
            }
            apiFetch('/check_spelling_display', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: text })
            }).then(function(res) { return res.json(); }).then(function(data) {
                addTerminalLineWithHighlight(data.text, data.not_found);
            });
        });

        var currentEventSource = null;

        function loadPresets() {
            apiFetch('/get_presets').then(function(res) { return res.json(); }).then(function(data) {
                presets = data;
                renderPresetList();
            });
        }

        function renderPresetList() {
    presetList.innerHTML = '';
    var names = Object.keys(presets);
    if (names.length === 0) {
        var empty = document.createElement('div');
        empty.className = 'preset-empty';
        empty.textContent = i18n('preset.empty', '暂无预设');
        presetList.appendChild(empty);
        return;
    }
    for (var i = 0; i < names.length; i++) {
        var name = names[i];
        var content = presets[name];

        var row = document.createElement('div');
        row.className = 'preset-item';

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'preset-checkbox';
        checkbox.setAttribute('data-name', name);
        checkbox.addEventListener('change', function(e) {
            var n = e.target.getAttribute('data-name');
            if (e.target.checked) {
                if (selectedPresets.indexOf(n) === -1) selectedPresets.push(n);
            } else {
                var idx = selectedPresets.indexOf(n);
                if (idx !== -1) selectedPresets.splice(idx, 1);
            }
        });
        row.appendChild(checkbox);

        var nameEl = document.createElement('span');
        nameEl.className = 'preset-name';
        nameEl.textContent = name;
        nameEl.addEventListener('click', (function(n) {
            return function() {
                broadcastInput.value = presets[n];
                presetModal.classList.remove('show');
            };
        })(name));
        row.appendChild(nameEl);

        var preview = document.createElement('span');
        preview.className = 'preset-preview';
        preview.textContent = content.length > 50 ? content.substring(0, 50) + '...' : content;
        row.appendChild(preview);

        var deleteBtn = document.createElement('button');
        deleteBtn.type = 'button';
        deleteBtn.className = 'preset-delete';
        deleteBtn.textContent = '×';
        deleteBtn.title = i18n('preset.delete', '删除');
        deleteBtn.setAttribute('aria-label', i18n('preset.delete', '删除'));
        deleteBtn.setAttribute('data-name', name);
        deleteBtn.addEventListener('click', (function(n) {
            return function(e) {
                e.stopPropagation();
                apiFetch('/delete_preset', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name: n })
                }).then(function() { loadPresets(); });
            };
        })(name));
        row.appendChild(deleteBtn);

        presetList.appendChild(row);
    }
}

        on(presetBtn, 'click', function() {
            selectedPresets = [];
            loadPresets();
            presetModal.classList.add('show');
        });
        on(closeModal, 'click', function() { presetModal.classList.remove('show'); });
        on(presetModal, 'click', function(e) {
            if (e.target === presetModal) presetModal.classList.remove('show');
        });

        on(savePreset, 'click', function() {
            var name = presetName.value.trim();
            var content = presetContent.value.trim();
            if (!name || !content) return;
            apiFetch('/save_preset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: name, content: content })
            }).then(function() {
                presetName.value = '';
                presetContent.value = '';
                loadPresets();
            });
        });

        on(importPreset, 'click', function() {
            var input = document.createElement('input');
            input.type = 'file';
            input.accept = '.json';
            input.onchange = function(e) {
                var file = e.target.files[0];
                var reader = new FileReader();
                reader.onload = function(ev) {
                    apiFetch('/import_presets', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: ev.target.result
                    }).then(function() { loadPresets(); });
                };
                reader.readAsText(file);
            };
            input.click();
        });

        on(playSelectedBtn, 'click', function() {
            if (selectedPresets.length === 0) {
                addTerminalLine(i18n('msg.presetNeedOne', '请至少选择一个预设'), 'error');
                return;
            }
            var combined = [];
            for (var i = 0; i < selectedPresets.length; i++) {
                combined.push(presets[selectedPresets[i]]);
            }
            var text = combined.join(' . ');
            broadcastInput.value = text;
            presetModal.classList.remove('show');
            playBroadcast();
        });

var selectedDeviceId = 'default';
var selectedDeviceLabel = '默认设备';
var modalOpened = false;

function setStatus(key, fallback) {
    if (!statusText) return;
    statusText.setAttribute('data-i18n', key);
    statusText.textContent = i18n(key, fallback);
}

function setMonitorLabel(active) {
    if (!monitorAudioBtn) return;
    var key = active ? 'btn.monitorStop' : 'btn.monitor';
    monitorAudioBtn.setAttribute('data-i18n', key);
    monitorAudioBtn.textContent = i18n(key, active ? '停止监听' : '监听系统音频');
    monitorAudioBtn.classList.toggle('is-active', !!active);
}

function buildDeviceRow(label, deviceId, options) {
    var opts = options || {};
    var row = document.createElement('div');
    row.className = 'device-item';

    var radio = document.createElement('input');
    radio.type = 'radio';
    radio.name = 'device';
    radio.value = deviceId;
    radio.checked = !!opts.checked;
    row.appendChild(radio);

    var name = document.createElement('span');
    name.className = 'device-label';
    name.textContent = label;
    row.appendChild(name);

    if (opts.tag) {
        var tag = document.createElement('span');
        tag.className = 'device-tag';
        tag.textContent = opts.tag;
        row.appendChild(tag);
    }
    if (opts.note) {
        var note = document.createElement('span');
        note.className = 'device-note';
        note.textContent = opts.note;
        row.appendChild(note);
    }
    return row;
}

function getAudioDevices() {
    var devices = [];
    if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
        return navigator.mediaDevices.enumerateDevices()
            .then(function(deviceInfos) {
                for (var i = 0; i < deviceInfos.length; i++) {
                    var device = deviceInfos[i];
                    if (device.kind === 'audioinput') {
                        devices.push({
                            label: device.label || i18n('device.unknown', '未知设备 {index}', { index: i + 1 }),
                            deviceId: device.deviceId,
                            groupId: device.groupId
                        });
                    }
                }
                if (devices.length === 0) {
                    devices.push({
                        label: i18n('device.defaultInput', '默认输入设备'),
                        deviceId: 'default'
                    });
                }
                return devices;
            });
    } else {
        return Promise.resolve([{
            label: i18n('device.default', '默认设备'),
            deviceId: 'default'
        }]);
    }
}

function closeDeviceModal() {
    var modal = document.getElementById('deviceModal');
    modal.style.display = 'none';
    modalOpened = false;
}

function requestExport(deviceName) {
    var text = broadcastInput.value.trim();
    if (!text) {
        addTerminalLine(i18n('msg.needText', '请输入广播内容'), 'error');
        return;
    }
    setStatus('status.exporting', '导出中');
    beginExportProgress();

    var payload = JSON.stringify({
        text: text,
        device: deviceName || '',
        enable_bell: enableBell,
        enable_special_bell: enableSpecialBell,
        enable_number_reading: enableNumberReading,
        pitch: parseFloat(pitchSlider.value),
        speed: parseInt(speedSlider.value, 10)
    });

    fetch('/export_progress', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload
    }).then(function(response) {
        if (!response.body) {
            return downloadExport(payload).then(finishExportProgress, finishExportProgress);
        }
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var state = { carry: '' };
        var finished = false;

        function pump() {
            return reader.read().then(function(result) {
                if (result.done) {
                    if (!finished) {
                        finishExportProgress();
                        addTerminalLine(i18n('msg.exportFailedShort', '导出失败'), 'error');
                        setStatus('status.idle', '等待播放');
                    }
                    return;
                }
                var events = consumeSseText(state, decoder.decode(result.value, { stream: true }));
                for (var i = 0; i < events.length; i++) {
                    var event = events[i];
                    if (event.type === 'progress') {
                        showExportProgress(event.percent, event.stage, event.done, event.total);
                    } else if (event.type === 'done') {
                        finished = true;
                        if (event.success) {
                            showExportProgress(100, 'export', 1, 1);
                            downloadExport(payload).then(finishExportProgress, finishExportProgress);
                        } else {
                            finishExportProgress();
                            addTerminalLine(i18n('msg.exportFailed', '导出失败: {error}',
                                                 { error: event.message || '' }), 'error');
                            setStatus('status.idle', '等待播放');
                        }
                        return;
                    }
                }
                return pump();
            });
        }
        return pump();
    }).catch(function(err) {
        finishExportProgress();
        addTerminalLine(i18n('msg.exportFailed', '导出失败: {error}', { error: err.message }), 'error');
        setStatus('status.idle', '等待播放');
    });
}

function downloadExport(payload) {
    return fetch('/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload
    }).then(function(res) {
        var contentType = res.headers.get('Content-Type') || '';
        if (contentType.indexOf('audio/wav') === 0) {
            return res.blob();
        }
        return res.json().then(function(data) {
            throw new Error(data.message || i18n('msg.exportFailedShort', '导出失败'));
        });
    }).then(function(blob) {
        var url = URL.createObjectURL(blob);
        var link = document.createElement('a');
        link.href = url;
        link.download = 'broadcast.wav';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        addTerminalLine(i18n('msg.exportOk', '导出成功: broadcast.wav'), 'normal');
        setStatus('status.idle', '等待播放');
    });
}

var exportProgressStartedAt = 0;
var exportProgressTarget = 0;
var exportProgressShown = 0;
var exportProgressFrame = 0;
var exportProgressLastFrameAt = 0;
// 补间时长要 >= finishExportProgress 里的等待，否则会先复位、再补完
var EXPORT_PROGRESS_FILL_MS = 450;
var EXPORT_PROGRESS_MIN_VISIBLE_MS = 500;

var CASSIE_PROGRESS_SPANS = {
    parse: [0, 8],
    reverb: [8, 72],
    export: [72, 80],
    play: [80, 100]
};

var playProgress = { active: false, startedAt: 0, durationMs: 0 };
var estimateProgress = { active: false, startedAt: 0, durationMs: 0 };

function renderExportProgress(percent, stage, done, total) {
    var box = document.getElementById('exportProgress');
    if (!box) return;
    box.setAttribute('aria-valuenow', String(Math.round(percent)));
    var bar = document.getElementById('exportProgressFill');
    if (bar) bar.style.width = Math.max(0, Math.min(100, percent)) + '%';
    var label = document.getElementById('exportProgressText');
    if (label) {
        var stageNames = {
            parse: i18n('progress.parse', '解析文本'),
            reverb: i18n('progress.reverb', '应用空间效果'),
            export: i18n('progress.export', '混音写盘'),
            play: i18n('progress.play', '播放中')
        };
        var shownStage = stage;
        if (percent < CASSIE_PROGRESS_SPANS.reverb[0]) {
            shownStage = 'parse';
        } else if (percent < CASSIE_PROGRESS_SPANS.export[0]) {
            shownStage = 'reverb';
        } else if (percent < CASSIE_PROGRESS_SPANS.play[0]) {
            shownStage = 'export';
        } else {
            shownStage = 'play';
        }
        var name = stageNames[shownStage] || i18n('progress.working', '处理中');
        var detail = (shownStage === stage && total ? ' (' + done + '/' + total + ')' : '');
        label.textContent = name + detail + ' — ' + Math.round(percent) + '%';
    }
}

var exportProgressStage = 'parse';
var exportProgressDone = 0;
var exportProgressTotal = 0;

function animateExportProgress() {
    exportProgressFrame = 0;
    var now = Date.now();
    var elapsed = now - exportProgressLastFrameAt;
    exportProgressLastFrameAt = now;
    if (elapsed <= 0) elapsed = 16;
    if (elapsed > 100) elapsed = 100;

    if (estimateProgress.active && estimateProgress.durationMs > 0) {
        var spent = Date.now() - estimateProgress.startedAt;
        var done = Math.max(0, Math.min(1, spent / estimateProgress.durationMs));
        var rspan = CASSIE_PROGRESS_SPANS.reverb;
        var fromEstimate = rspan[0] + (rspan[1] - rspan[0]) * done;
        if (fromEstimate > exportProgressTarget) exportProgressTarget = fromEstimate;
    }

    if (playProgress.active && playProgress.durationMs > 0) {
        var played = Date.now() - playProgress.startedAt;
        var ratio = Math.max(0, Math.min(1, played / playProgress.durationMs));
        var span = CASSIE_PROGRESS_SPANS.play;
        var fromPlay = span[0] + (span[1] - span[0]) * ratio;
        if (fromPlay > exportProgressTarget) exportProgressTarget = fromPlay;
        if (ratio < 1) {
            renderExportProgress(exportProgressShown, exportProgressStage,
                                 exportProgressDone, exportProgressTotal);
            exportProgressFrame = 0;
            scheduleExportProgressFrame();
            return;
        }
    } else if (estimateProgress.active) {
        renderExportProgress(exportProgressShown, exportProgressStage,
                             exportProgressDone, exportProgressTotal);
        exportProgressFrame = 0;
        scheduleExportProgressFrame();
        return;
    }

    if (exportProgressShown < exportProgressTarget) {
        var step = (100 / EXPORT_PROGRESS_FILL_MS) * elapsed;
        exportProgressShown = Math.min(exportProgressTarget,
                                       exportProgressShown + step);
        renderExportProgress(exportProgressShown, exportProgressStage,
                             exportProgressDone, exportProgressTotal);
    }
    if (exportProgressShown < exportProgressTarget) {
        scheduleExportProgressFrame();
    }
}

function scheduleExportProgressFrame() {
    if (exportProgressFrame) return;
    var raf = (typeof window !== 'undefined' && window.requestAnimationFrame)
        ? window.requestAnimationFrame
        : function (fn) { return setTimeout(fn, 16); };
    exportProgressFrame = raf(animateExportProgress);
}

function showExportProgress(percent, stage, done, total) {
    var box = document.getElementById('exportProgress');
    if (!box) return;
    box.hidden = false;
    var value = Math.max(0, Math.min(100, Number(percent) || 0));
    if (value > exportProgressTarget) exportProgressTarget = value;
    if (stage) exportProgressStage = stage;
    if (done !== undefined) exportProgressDone = done || 0;
    if (total !== undefined) exportProgressTotal = total || 0;
    scheduleExportProgressFrame();
}

function beginExportProgress() {
    exportProgressStartedAt = Date.now();
    exportProgressTarget = 5;
    exportProgressShown = 0;
    exportProgressStage = 'parse';
    exportProgressDone = 0;
    exportProgressTotal = 0;
    playProgress.active = false;
    renderExportProgress(0, exportProgressStage, 0, 0);
    scheduleExportProgressFrame();
}

function beginPlaybackProgress() {
    beginExportProgress();
}

function onPlaybackProgress(event) {
    var stage = event.stage || 'reverb';
    if (event.estimated) {
        var estimate = Number(event.estimate_ms) || 0;
        if (estimate > 0) {
            estimateProgress.active = true;
            estimateProgress.startedAt = Date.now();
            estimateProgress.durationMs = estimate;
        }
    } else if (stage === 'reverb') {
        estimateProgress.active = false;
    }
    if (stage === 'play' && event.is_playback) {
        var duration = Number(event.duration_ms) || 0;
        estimateProgress.active = false;
        if (duration > 0) {
            playProgress.active = true;
            playProgress.durationMs = duration;
            var startedAt = Number(event.started_at) || 0;
            var elapsed = Number(event.elapsed_ms) || 0;
            playProgress.startedAt = startedAt
                ? startedAt + elapsed
                : Date.now() - elapsed;
        }
    }
    showExportProgress(event.percent, stage, event.done, event.total);
}

function finishExportProgress() {
    var settle = EXPORT_PROGRESS_FILL_MS + 60;
    var wait = settle - (Date.now() - exportProgressStartedAt);
    var reset = function () {
        exportProgressTarget = 0;
        exportProgressShown = 0;
        var bar = document.getElementById('exportProgressFill');
        if (bar) bar.style.width = '0%';
        var box = document.getElementById('exportProgress');
        if (box) box.setAttribute('aria-valuenow', '0');
        var label = document.getElementById('exportProgressText');
        if (label) {
            label.textContent = i18n('progress.idle', '就绪');
        }
    };
    if (wait > 0) {
        setTimeout(reset, wait);
    } else {
        reset();
    }
}

function openDeviceModal(callback) {
    if (modalOpened) return;
    modalOpened = true;

    var modal = document.getElementById('deviceModal');
    var deviceList = document.getElementById('deviceList');
    var closeBtn = document.getElementById('closeDeviceModal');
    var cancelBtn = document.getElementById('cancelDeviceSelect');
    var confirmBtn = document.getElementById('confirmDeviceSelect');

    selectedDeviceId = 'default';
    selectedDeviceLabel = i18n('device.default', '默认设备');

    var newConfirmBtn = confirmBtn.cloneNode(true);
    var newCloseBtn = closeBtn.cloneNode(true);
    var newCancelBtn = cancelBtn.cloneNode(true);
    confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
    closeBtn.parentNode.replaceChild(newCloseBtn, closeBtn);
    cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

    var finalConfirmBtn = document.getElementById('confirmDeviceSelect');
    var finalCloseBtn = document.getElementById('closeDeviceModal');
    var finalCancelBtn = document.getElementById('cancelDeviceSelect');

    deviceList.innerHTML = '';
    var loading = document.createElement('div');
    loading.className = 'device-loading';
    loading.textContent = i18n('device.loading', '正在加载设备...');
    deviceList.appendChild(loading);
    modal.style.display = 'flex';

    getAudioDevices().then(function(devices) {
        deviceList.innerHTML = '';

        var defaultRow = buildDeviceRow(
            i18n('device.default', '默认设备'), 'default',
            { checked: true, note: i18n('device.systemDefault', '系统默认') });
        defaultRow.addEventListener('click', function(e) {
            var radio = this.querySelector('input[type="radio"]');
            radio.checked = true;
            selectedDeviceId = 'default';
            selectedDeviceLabel = i18n('device.default', '默认设备');
            e.stopPropagation();
        });
        deviceList.appendChild(defaultRow);

        for (var i = 0; i < devices.length; i++) {
            var label = devices[i].label;
            var lowered = label.toLowerCase();
            var isLoopback = lowered.indexOf('stereo mix') >= 0 ||
                            lowered.indexOf('立体声混音') >= 0 ||
                            lowered.indexOf('blackhole') >= 0 ||
                            lowered.indexOf('loopback') >= 0;
            var row = buildDeviceRow(label, devices[i].deviceId, {
                tag: isLoopback ? i18n('device.loopbackTag', '内录推荐') : ''
            });
            row.addEventListener('click', function(e) {
                var radio = this.querySelector('input[type="radio"]');
                radio.checked = true;
                selectedDeviceId = radio.value;
                selectedDeviceLabel = this.querySelector('.device-label').textContent.trim();
                e.stopPropagation();
            });
            deviceList.appendChild(row);
        }
    }).catch(function() {
        deviceList.innerHTML = '';
        var failed = document.createElement('div');
        failed.className = 'device-error';
        failed.textContent = i18n('device.loadFailed', '无法获取设备列表，请手动输入设备名称');
        deviceList.appendChild(failed);

        var input = document.createElement('input');
        input.type = 'text';
        input.placeholder = i18n('device.manualPlaceholder', '请输入设备名称（如 Stereo Mix）');
        input.className = 'device-manual';
        input.addEventListener('input', function() {
            selectedDeviceLabel = this.value;
            selectedDeviceId = this.value;
        });
        deviceList.appendChild(input);
    });

    on(finalCloseBtn, 'click', closeDeviceModal);
    on(finalCancelBtn, 'click', closeDeviceModal);
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeDeviceModal();
        }
    });

    on(finalConfirmBtn, 'click', function() {
        closeDeviceModal();
        requestExport(selectedDeviceLabel || '');
    });
}

on(exportBtn, 'click', function() {
    var text = broadcastInput.value.trim();
    if (!text) {
        addTerminalLine(i18n('msg.needInput', '请输入广播内容'), 'error');
        return;
    }
    requestExport('');
});
var pitchSlider = document.getElementById('pitchSlider');
var speedSlider = document.getElementById('speedSlider');
var pitchValue = document.getElementById('pitchValue');
var speedValue = document.getElementById('speedValue');

on(pitchSlider, 'input', function() {
    var val = parseFloat(this.value).toFixed(2);
    pitchValue.textContent = val;
    syncRangeFill(this);
});

on(speedSlider, 'input', function() {
    var val = parseInt(this.value, 10);
    speedValue.textContent = val;
    var color = 'var(--accent-cyan)';
    if (val === -10) {
        color = 'var(--text)';
    } else if (val < -10) {
        color = 'var(--warn)';
    } else if (val < 0) {
        color = 'var(--accent-cyan)';
    } else if (val > 0) {
        color = 'var(--err)';
    } else {
        color = 'var(--accent-cyan)';
    }
    speedValue.style.color = color;
});
speedSlider.dispatchEvent(new Event('input'));

function consumeSseText(state, text) {
    var events = [];
    state.carry = (state.carry || '') + text;
    var lines = state.carry.split('\n');
    state.carry = lines.pop();
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].replace(/\r$/, '');
        if (line.indexOf('data: ') !== 0) {
            continue;
        }
        try {
            events.push(JSON.parse(line.substring(6)));
        } catch (error) {
            events.push({
                type: 'error',
                text: i18n('msg.sseParseFailed', '日志解析失败: {payload}', { payload: line.substring(6) })
            });
        }
    }
    return events;
}

function playBroadcast() {
    var text = broadcastInput.value.trim();
    if (!text) {
        addTerminalLine(i18n('msg.needInput', '请输入广播内容'), 'error');
        return;
    }
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }
    setStatus('status.playing', '播放中');
    if (verboseMode) {
        terminalContent.innerHTML = '';
    }
    beginPlaybackProgress();
    var pitch = parseFloat(pitchSlider.value);
    var speed = parseInt(speedSlider.value, 10);
    apiFetch('/play', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            text: text,
            enable_bell: enableBell,
            enable_special_bell: enableSpecialBell,
            enable_number_reading: enableNumberReading,
            verbose_mode: verboseMode,
            pitch: pitch,
            speed: speed
        })
    }).then(function(response) {
        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var state = { carry: '' };
        var ended = false;
        function finishPlayback() {
            if (ended) return;
            ended = true;
            playProgress.active = false;
            showExportProgress(100, 'play', 1, 1);
            finishExportProgress();
            setStatus('status.idle', '等待播放');
        }
        function readStream() {
            reader.read().then(function(result) {
                if (result.done) {
                    finishPlayback();
                    return;
                }
                var events = consumeSseText(
                    state, decoder.decode(result.value, { stream: true }));
                for (var i = 0; i < events.length; i++) {
                    var data = events[i];
                    if (data.type === 'progress') {
                        onPlaybackProgress(data);
                        continue;
                    }
                    if (data.type === 'end') {
                        finishPlayback();
                        return;
                    }
                    addTerminalLine(data.text, data.type);
                }
                readStream();
            });
        }
        readStream();
    }).catch(function(err) {
        playProgress.active = false;
        finishExportProgress();
        addTerminalLine(i18n('msg.playFailed', '播放失败: {error}', { error: err }), 'error');
        setStatus('status.idle', '等待播放');
    });
}
on(playBtn, 'click', playBroadcast);

        var systemAudioStream = null;
        var volumeAnimation = null;
        var audioContext = null;

        function stopAudioMonitor() {
            if (volumeAnimation) {
                cancelAnimationFrame(volumeAnimation);
                volumeAnimation = null;
            }
            if (systemAudioStream) {
                systemAudioStream.getTracks().forEach(function(track) { track.stop(); });
                systemAudioStream = null;
            }
            if (audioContext) {
                audioContext.close();
                audioContext = null;
            }
            volumeFill.style.width = '0%';
        }

        function startAudioMonitor() {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
                addTerminalLine(i18n('msg.noAudioMonitorSupport', '当前浏览器不支持系统音频监听'), 'error');
                return;
            }
            stopAudioMonitor();
            navigator.mediaDevices.getDisplayMedia({ video: true, audio: true }).then(function(stream) {
                systemAudioStream = stream;
                stream.getVideoTracks().forEach(function(track) { track.stop(); });
                if (stream.getAudioTracks().length === 0) {
                    stopAudioMonitor();
                    addTerminalLine(i18n('msg.noSystemAudioShared', '未共享系统音频，请在共享窗口中勾选音频'), 'error');
                    return;
                }
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                var source = audioContext.createMediaStreamSource(stream);
                var analyser = audioContext.createAnalyser();
                analyser.fftSize = 1024;
                source.connect(analyser);
                var dataArray = new Uint8Array(analyser.fftSize);
                var displayed = 0;
                function getVolume() {
                    analyser.getByteTimeDomainData(dataArray);
                    var sum = 0;
                    for (var i = 0; i < dataArray.length; i++) {
                        var sample = (dataArray[i] - 128) / 128;
                        sum += sample * sample;
                    }
                    var rms = Math.sqrt(sum / dataArray.length);
                    var target = Math.min(100, Math.max(0, rms * 260));
                    displayed += (target - displayed) * (target > displayed ? 0.45 : 0.2);
                    volumeFill.style.width = displayed.toFixed(1) + '%';
                    volumeAnimation = requestAnimationFrame(getVolume);
                }
                getVolume();
                stream.getTracks().forEach(function(track) {
                    track.addEventListener('ended', function() {
                        stopAudioMonitor();
                        setMonitorLabel(false);
                    }, { once: true });
                });
                setMonitorLabel(true);
            }).catch(function(error) {
                if (error.name !== 'AbortError' && error.name !== 'NotAllowedError') {
                    addTerminalLine(i18n('msg.audioMonitorFailed',
                        '系统音频监听失败: {error}', { error: error.message }), 'error');
                }
            });
        }

        on(monitorAudioBtn, 'click', function() {
            if (systemAudioStream) {
                stopAudioMonitor();
                setMonitorLabel(false);
            } else {
                startAudioMonitor();
            }
        });

        window.addEventListener('cassie:langchange', function() {
            refreshQualityLevels();
            if (presetModal && presetModal.classList.contains('show') &&
                Object.keys(presets).length) {
                renderPresetList();
            }
        });

        syncAllRangeFills();

        window.addEventListener('DOMContentLoaded', startAudioMonitor);