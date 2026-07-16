/**
 * Music Downloader — 前端交互逻辑
 */

// ========================================
// DOM 元素
// ========================================
const els = {
    urlInput: document.getElementById('urlInput'),
    parseBtn: document.getElementById('parseBtn'),
    resultSection: document.getElementById('resultSection'),
    coverImg: document.getElementById('coverImg'),
    infoTitle: document.getElementById('infoTitle'),
    infoSub: document.getElementById('infoSub'),
    infoDuration: document.getElementById('infoDuration'),
    infoPlatform: document.getElementById('infoPlatform'),
    formatOptions: document.getElementById('formatOptions'),
    downloadBtn: document.getElementById('downloadBtn'),
    progressSection: document.getElementById('progressSection'),
    progressTitle: document.getElementById('progressTitle'),
    progressStatus: document.getElementById('progressStatus'),
    progressBar: document.getElementById('progressBar'),
    progressPercent: document.getElementById('progressPercent'),
    progressSpeed: document.getElementById('progressSpeed'),
    progressEta: document.getElementById('progressEta'),
    downloadDone: document.getElementById('downloadDone'),
    openFolderBtn: document.getElementById('openFolderBtn'),
    newTaskBtn: document.getElementById('newTaskBtn'),
    errorToast: document.getElementById('errorToast'),
    historySection: document.getElementById('historySection'),
    historyList: document.getElementById('historyList'),
};

// ========================================
// 状态
// ========================================
let currentResult = null;
let selectedFormat = null;
let currentTaskId = null;
let progressEventSource = null;

// ========================================
// 初始化
// ========================================
function init() {
    // 输入框变化时启用/禁用解析按钮
    els.urlInput.addEventListener('input', () => {
        els.parseBtn.disabled = !els.urlInput.value.trim();
    });

    // 回车键解析
    els.urlInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && els.urlInput.value.trim()) {
            parseUrl();
        }
    });

    // 解析按钮
    els.parseBtn.addEventListener('click', parseUrl);

    // 下载按钮
    els.downloadBtn.addEventListener('click', startDownload);

    // 打开文件夹
    els.openFolderBtn.addEventListener('click', () => {
        if (currentTaskId) {
            fetch(`/api/download/${currentTaskId}/status`)
                .then(r => r.json())
                .then(data => {
                    if (data.output_path) {
                        // 触发打开文件夹请求
                        fetch('/api/open-folder', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ path: data.output_path }),
                        }).catch(() => {});
                    }
                });
        }
    });

    // 新任务
    els.newTaskBtn.addEventListener('click', resetUI);

    // 加载历史
    loadHistory();

    // 粘贴事件
    document.addEventListener('paste', (e) => {
        const text = e.clipboardData?.getData('text');
        if (text && (text.includes('bilibili.com') || text.includes('music.163.com') || text.includes('y.qq.com') || text.includes('b23.tv') || text.includes('163cn.tv'))) {
            els.urlInput.value = text;
            els.parseBtn.disabled = false;
            parseUrl();
        }
    });
}

// ========================================
// 解析链接
// ========================================
async function parseUrl() {
    const url = els.urlInput.value.trim();
    if (!url) return;

    showParsing();

    try {
        const resp = await fetch('/api/parse', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url }),
        });
        const data = await resp.json();

        if (!data.success) {
            showError(data.error);
            resetParsing();
            return;
        }

        currentResult = data;
        showResult(data);
    } catch (err) {
        showError('解析失败，请检查链接或重试');
        resetParsing();
    }
}

// ========================================
// UI 更新
// ========================================
function showParsing() {
    els.parseBtn.disabled = true;
    els.parseBtn.querySelector('.btn-text').classList.add('hidden');
    els.parseBtn.querySelector('.btn-spinner').classList.remove('hidden');
    els.resultSection.classList.add('hidden');
    els.progressSection.classList.add('hidden');
    hideError();
}

function resetParsing() {
    els.parseBtn.disabled = !els.urlInput.value.trim();
    els.parseBtn.querySelector('.btn-text').classList.remove('hidden');
    els.parseBtn.querySelector('.btn-spinner').classList.add('hidden');
}

function showResult(data) {
    resetParsing();
    els.resultSection.classList.remove('hidden');
    els.progressSection.classList.add('hidden');

    // 信息
    els.infoTitle.textContent = data.title || '未知';

    if (data.media_type === 'audio') {
        els.infoSub.textContent = data.artist || '';
    } else {
        els.infoSub.textContent = data.uploader ? `UP主: ${data.uploader}` : '';
    }

    // 时长
    if (data.duration > 0) {
        const mins = Math.floor(data.duration / 60);
        const secs = data.duration % 60;
        els.infoDuration.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
    } else {
        els.infoDuration.textContent = '';
    }
    els.infoDuration.classList.toggle('hidden', !data.duration);

    // 平台标签
    const platformNames = { bilibili: 'B站', netease: '网易云', qqmusic: 'QQ音乐' };
    els.infoPlatform.textContent = platformNames[data.platform] || data.platform;

    // 封面
    if (data.cover_url) {
        els.coverImg.src = data.cover_url;
        els.coverImg.style.display = '';
    } else {
        els.coverImg.style.display = 'none';
    }

    // 格式选项
    renderFormats(data.available_formats);
}

function renderFormats(formats) {
    els.formatOptions.innerHTML = '';
    selectedFormat = null;

    formats.forEach((fmt, index) => {
        const option = document.createElement('div');
        option.className = 'format-option';
        option.innerHTML = `
            <div class="format-option-radio"></div>
            <span class="format-option-text">${fmt.label}</span>
            ${fmt.note ? `<span class="format-option-note">${fmt.note}</span>` : ''}
            ${fmt.size_mb ? `<span class="format-option-note">~${fmt.size_mb}MB</span>` : ''}
        `;
        option.addEventListener('click', () => selectFormat(index, fmt));
        els.formatOptions.appendChild(option);
    });

    // 默认选中第一个
    if (formats.length > 0) {
        selectFormat(0, formats[0]);
    }
}

function selectFormat(index, fmt) {
    const options = els.formatOptions.querySelectorAll('.format-option');
    options.forEach((opt, i) => {
        opt.classList.toggle('selected', i === index);
    });
    selectedFormat = fmt;
}

// ========================================
// 下载
// ========================================
async function startDownload() {
    if (!currentResult || !selectedFormat) return;

    els.resultSection.classList.add('hidden');
    els.progressSection.classList.remove('hidden');
    els.downloadDone.classList.add('hidden');
    els.progressTitle.textContent = currentResult.title;
    els.progressStatus.textContent = '准备中...';
    els.progressBar.style.width = '0%';
    els.progressPercent.textContent = '0%';
    els.progressSpeed.textContent = '';
    els.progressEta.textContent = '';

    // 关闭旧的 SSE 连接
    if (progressEventSource) {
        progressEventSource.close();
    }

    try {
        const resp = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                url: currentResult.raw_url || els.urlInput.value.trim(),
                format_id: selectedFormat.id,
                title: currentResult.title,
                platform: currentResult.platform,
                ext: selectedFormat.ext || 'mp3',
            }),
        });
        const data = await resp.json();

        if (!data.success) {
            showError('启动下载失败');
            return;
        }

        currentTaskId = data.task_id;
        listenProgress(currentTaskId);
    } catch (err) {
        showError('启动下载失败');
    }
}

function listenProgress(taskId) {
    progressEventSource = new EventSource(`/api/download/${taskId}/progress`);

    progressEventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            updateProgress(data);

            if (data.status === 'done' || data.status === 'error') {
                progressEventSource.close();
                if (data.status === 'done') {
                    showDone();
                } else {
                    showError(data.error || '下载失败');
                }
                loadHistory();
            }
        } catch (e) {
            // ignore parse errors
        }
    };

    progressEventSource.onerror = () => {
        // SSE 断连，切换到轮询
        progressEventSource.close();
        pollProgress(taskId);
    };
}

async function pollProgress(taskId) {
    const poll = async () => {
        try {
            const resp = await fetch(`/api/download/${taskId}/status`);
            const data = await resp.json();
            updateProgress(data);

            if (data.status === 'done') {
                showDone();
                loadHistory();
                return;
            }
            if (data.status === 'error') {
                showError(data.error || '下载失败');
                loadHistory();
                return;
            }
            setTimeout(poll, 1000);
        } catch (e) {
            setTimeout(poll, 2000);
        }
    };
    poll();
}

function updateProgress(data) {
    if (data.status === 'downloading' || data.status === 'processing') {
        const pct = data.progress || 0;
        els.progressBar.style.width = `${pct}%`;
        els.progressPercent.textContent = `${pct}%`;
        els.progressSpeed.textContent = data.speed || '';
        els.progressEta.textContent = data.eta ? `剩余 ${data.eta}` : '';

        if (data.status === 'processing') {
            els.progressStatus.textContent = '处理中...';
        } else {
            els.progressStatus.textContent = '下载中...';
        }
    }
}

function showDone() {
    els.progressStatus.textContent = '完成';
    els.downloadDone.classList.remove('hidden');
    els.progressBar.style.width = '100%';
    els.progressPercent.textContent = '100%';
}

// ========================================
// 下载历史
// ========================================
async function loadHistory() {
    try {
        const resp = await fetch('/api/history');
        const tasks = await resp.json();

        if (tasks.length === 0) {
            els.historyList.innerHTML = '<p class="empty-hint">还没有下载记录</p>';
            return;
        }

        els.historyList.innerHTML = tasks.slice(0, 20).map(task => {
            const platformIcons = { bilibili: '📺', netease: '🎵', qqmusic: '🎶' };
            const icon = platformIcons[task.platform] || '📁';

            const isDone = task.status === 'done';
            const btnHtml = isDone
                ? `<button class="btn btn-secondary btn-sm" onclick="openFile('${task.task_id}')">打开</button>`
                : `<span style="color:var(--text-muted);font-size:0.75rem">${task.status === 'error' ? '失败' : '进行中'}</span>`;

            return `
                <div class="history-item">
                    <div class="history-icon">${icon}</div>
                    <div class="history-info">
                        <div class="history-title">${escapeHtml(task.title)}</div>
                        <div class="history-meta">${task.ext?.toUpperCase()} · ${task.platform}</div>
                    </div>
                    <div class="history-actions">${btnHtml}</div>
                </div>
            `;
        }).join('');
    } catch (e) {
        // ignore
    }
}

async function openFile(taskId) {
    try {
        const resp = await fetch(`/api/download/${taskId}/status`);
        const data = await resp.json();
        if (data.output_path) {
            // 尝试触发下载/打开
            window.open(`/api/download/${taskId}/file`, '_blank');
        }
    } catch (e) {
        // ignore
    }
}

// ========================================
// 工具函数
// ========================================
function showError(msg) {
    els.errorToast.textContent = msg;
    els.errorToast.classList.remove('hidden');
    setTimeout(() => {
        els.errorToast.classList.add('hidden');
    }, 4000);
}

function hideError() {
    els.errorToast.classList.add('hidden');
}

function resetUI() {
    currentResult = null;
    selectedFormat = null;
    currentTaskId = null;
    if (progressEventSource) {
        progressEventSource.close();
        progressEventSource = null;
    }
    els.resultSection.classList.add('hidden');
    els.progressSection.classList.add('hidden');
    els.urlInput.value = '';
    els.urlInput.focus();
    els.parseBtn.disabled = true;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ========================================
// 启动
// ========================================
document.addEventListener('DOMContentLoaded', init);
