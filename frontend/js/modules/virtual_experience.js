/**
 * VirtualExperience - 虚拟打金体验模块
 * 
 * 提供沉浸式的金箔锻打交互体验，包含：
 * - 3种难度模式（beginner/intermediate/master）
 * - 7步交互式教程
 * - 10项成就系统
 * - 力反馈曲线与力度显示
 * - Web Audio API 音效合成
 * - 触觉反馈（振动）
 * - 实时厚度热力图渲染
 * - 连击与评分系统
 * - 退火工艺处理
 * - 佛像贴金完成流程
 * 
 * @module virtual_experience
 */

class VirtualExperience {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.currentMode = 'beginner';
        this.currentAlloy = 'pure_gold_24k';
        this.targetThickness = 0.5;
        this.totalScore = 0;
        this.tutorialStep = 0;
        this.tutorialEnabled = true;
        this.achievements = [];
        this.unlockedAchievements = [];
        this.hammerPosition = { x: 0, y: 0 };
        this.hammerForce = 500;
        this.thicknessData = null;
        this.animationFrame = null;
        this.audioContext = null;
        this.init();
    }

    async init() {
        this.setupAudio();
        this.setupEventListeners();
        this.setupCanvasInteraction();
        this.renderAchievements();
        this.startRenderLoop();
        await this.loadStatus();
    }

    setupAudio() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
        } catch (e) {
            console.log('Web Audio API not supported');
        }
    }

    playSound(frequency, duration, quality = 0.5) {
        if (!this.audioContext) return;

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        oscillator.type = quality > 0.7 ? 'triangle' : 'sawtooth';
        oscillator.frequency.setValueAtTime(frequency, this.audioContext.currentTime);

        gainNode.gain.setValueAtTime(0.3 * quality + 0.1, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration / 1000);

        oscillator.start();
        oscillator.stop(this.audioContext.currentTime + duration / 1000);
    }

    triggerHapticFeedback(forceCurve, intensity) {
        if (!navigator.vibrate) return;
        
        const pattern = forceCurve.map(v => Math.round(v * intensity * 100));
        navigator.vibrate(pattern);
    }

    setupEventListeners() {
        document.getElementById('exp-mode')?.addEventListener('change', (e) => {
            this.handleModeChange(e.target.value);
        });

        document.getElementById('exp-alloy')?.addEventListener('change', (e) => {
            this.currentAlloy = e.target.value;
        });

        document.getElementById('btn-exp-reset')?.addEventListener('click', () => this.resetExperience());
        document.getElementById('btn-exp-strike')?.addEventListener('click', (e) => this.handleHammerStrike(e));
        document.getElementById('btn-exp-anneal')?.addEventListener('click', () => this.performAnneal());
        document.getElementById('btn-exp-gilding')?.addEventListener('click', () => this.completeAndGilding());

        document.getElementById('tutorial-prev')?.addEventListener('click', () => {
            if (this.tutorialStep > 0) {
                this.tutorialStep--;
                this.showTutorialStep(this.tutorialStep);
            }
        });
        document.getElementById('tutorial-next')?.addEventListener('click', () => {
            this.tutorialStep++;
            if (this.tutorialStep >= 7) {
                this.tutorialEnabled = false;
                document.getElementById('tutorial-banner').style.display = 'none';
                showToast('info', '教程完成', '可以自由探索了！');
            } else {
                this.showTutorialStep(this.tutorialStep);
            }
        });
        document.getElementById('tutorial-skip')?.addEventListener('click', () => {
            this.tutorialEnabled = false;
            document.getElementById('tutorial-banner').style.display = 'none';
            showToast('info', '教程已跳过', '可以自由探索了！');
        });

        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
                if (activeTab === 'experience') {
                    this.handleHammerStrike(e);
                }
            }
        });
    }

    setupCanvasInteraction() {
        const canvas = document.getElementById('exp-strike-canvas');
        if (canvas) {
            canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
            canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
            canvas.addEventListener('mouseup', () => this.handleMouseUp());
            canvas.addEventListener('touchstart', (e) => {
                e.preventDefault();
                const touch = e.touches[0];
                this.handleMouseMove({ clientX: touch.clientX, clientY: touch.clientY });
                this.handleMouseDown({ clientX: touch.clientX, clientY: touch.clientY });
            });
            canvas.addEventListener('touchend', () => this.handleMouseUp());
        }
    }

    startExperience() {
        this.totalScore = 0;
        this.tutorialStep = 0;
        this.thicknessData = null;
        this.unlockedAchievements = [];
        this.hammerPosition = { x: 0, y: 0 };
        this.hammerForce = 500;
        this.tutorialEnabled = true;

        document.getElementById('exp-score').textContent = '0';
        document.getElementById('exp-combo').textContent = '0';
        document.getElementById('exp-strikes').textContent = '0';
        document.getElementById('tutorial-banner').style.display = 'block';
        
        this.showTutorialStep(0);
        this.updateForceDisplay(this.hammerForce);
        this.loadStatus();
    }

    handleMouseMove(e) {
        const canvas = document.getElementById('exp-strike-canvas');
        if (!canvas) return;

        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        this.hammerPosition = {
            x: (x / rect.width - 0.5) * 150,
            y: (y / rect.height - 0.5) * 150
        };
    }

    handleMouseDown(e) {
        this.isCharging = true;
        this.chargeStart = Date.now();
    }

    handleMouseUp() {
        if (this.isCharging) {
            this.handleHammerStrike(e);
        }
        this.isCharging = false;
        this.chargeStart = 0;
    }

    async handleHammerStrike(e) {
        try {
            const forceCurve = [0.1, 0.3, 0.6, 1.0, 0.8, 0.4, 0.1];
            this.triggerHapticFeedback(forceCurve, 0.8);

            const result = await this.apiClient.virtualExperienceStrike(
                this.hammerForce,
                this.hammerPosition.x,
                this.hammerPosition.y,
                15,
                this.currentMode
            );

            if (result.state?.thickness_distribution?.data) {
                this.thicknessData = result.state.thickness_distribution.data;
                this.checkNearTearWarning(this.thicknessData);
            }

            if (result.feedback) {
                this.playSound(
                    result.feedback.sound_frequency_hz,
                    result.feedback.sound_duration_ms,
                    result.feedback.quality_score
                );

                this.renderStrikeFeedback(result.feedback);
            }

            if (result.score) {
                this.totalScore += result.score.total_score;
                this.updateScoreDisplay(result);
                this.showComboEffect(result.score.consecutive_good_strikes);
            }

            if (result.new_achievements && result.new_achievements.length > 0) {
                this.updateAchievements(result.new_achievements);
            }

            this.updateStats(result.stats);

        } catch (e) {
            showToast('error', '锤击失败', e.message);
        }
    }

    renderStrikeFeedback(feedback) {
        const messageEl = document.getElementById('feedback-message');
        if (!messageEl) return;

        messageEl.textContent = feedback.message;
        messageEl.className = 'feedback-message';

        if (feedback.visual_effect === 'excellent') {
            messageEl.classList.add('feedback-excellent');
        } else if (feedback.visual_effect === 'good') {
            messageEl.classList.add('feedback-good');
        } else if (feedback.visual_effect === 'warning') {
            messageEl.classList.add('feedback-warning');
        } else if (feedback.visual_effect === 'danger') {
            messageEl.classList.add('feedback-danger');
        } else {
            messageEl.classList.add('feedback-normal');
        }

        if (feedback.vibration_intensity > 0.5 && navigator.vibrate) {
            navigator.vibrate(feedback.sound_duration_ms);
        }
    }

    updateStats(stats) {
        document.getElementById('exp-strikes').textContent = stats.total_strikes;
    }

    updateAchievements(achievements) {
        achievements.forEach(ach => {
            const popup = document.createElement('div');
            popup.className = 'achievement-popup';
            popup.innerHTML = `
                <div class="achievement-popup-icon">${ach.icon}</div>
                <div class="achievement-popup-info">
                    <h5>🎉 成就解锁！</h5>
                    <p><strong>${ach.name}</strong> - ${ach.desc}</p>
                    <p style="color: var(--accent-gold);">+${ach.points} 分</p>
                </div>
            `;

            document.body.appendChild(popup);

            setTimeout(() => {
                popup.style.animation = 'achievementSlideIn 0.5s ease reverse';
                setTimeout(() => popup.remove(), 500);
            }, 3000);

            this.unlockedAchievements.push(ach.id);
        });
        this.renderAchievements();
    }

    showTutorialStep(step) {
        const tutorials = [
            { title: '认识工具', text: '这是您的锻锤，可以通过鼠标或触控操作控制锤击力度和位置' },
            { title: '第一次锤击', text: '点击金箔中央，尝试一次轻锤。观察厚度变化' },
            { title: '理解厚度', text: '蓝色区域较薄，红色区域较厚。我们需要让金箔均匀变薄' },
            { title: '厚处打重锤', text: '应该在较厚的地方（红色）使用更大的力度' },
            { title: '退火处理', text: '当金箔变硬时（加工硬化），需要进行退火处理恢复塑性' },
            { title: '小心破裂', text: '避免在同一位置连续重锤，否则金箔会破裂！' },
            { title: '开始您的创作', text: '目标：将500μm厚的金片锻打到0.5μm，均匀度90%以上。祝您成功！' },
        ];

        if (step >= 0 && step < tutorials.length) {
            const t = tutorials[step];
            document.getElementById('tutorial-step').textContent = `${step + 1}/${tutorials.length}`;
            document.getElementById('tutorial-title').textContent = t.title;
            document.getElementById('tutorial-text').textContent = t.text;
        }
    }

    updateScoreDisplay(result) {
        document.getElementById('exp-score').textContent = Math.round(this.totalScore);
        document.getElementById('exp-combo').textContent = result.score.consecutive_good_strikes;
    }

    showComboEffect(combo) {
        if (combo >= 3) {
            const comboEl = document.getElementById('exp-combo');
            comboEl.style.animation = 'pulse 0.3s ease';
            setTimeout(() => comboEl.style.animation = '', 300);
        }
    }

    handleModeChange(mode) {
        this.currentMode = mode;
        this.updateForceRange();
    }

    updateForceRange() {
        const forceRanges = {
            beginner: [200, 800],
            intermediate: [300, 1500],
            master: [500, 3000],
        };
        const range = forceRanges[this.currentMode] || forceRanges.beginner;
        this.hammerForce = (range[0] + range[1]) / 2;
    }

    calculateForceFromCharge(progress) {
        const forceRanges = {
            beginner: [200, 800],
            intermediate: [300, 1500],
            master: [500, 3000],
        };
        const range = forceRanges[this.currentMode] || forceRanges.beginner;
        return range[0] + progress * (range[1] - range[0]);
    }

    checkNearTearWarning(thickness) {
        const minThickness = Math.min(...thickness.flat());
        if (minThickness < 0.3) {
            showToast('warning', '⚠️ 接近破裂', '金箔过薄，请减小力度或更换位置');
        }
    }

    updateForceDisplay(force) {
        const forceLabel = document.getElementById('exp-force-label');
        const forceBar = document.getElementById('force-bar');
        const forceMarker = document.getElementById('force-marker');

        if (forceLabel) forceLabel.textContent = Math.round(force);

        const forceRanges = {
            beginner: [200, 800],
            intermediate: [300, 1500],
            master: [500, 3000],
        };
        const range = forceRanges[this.currentMode] || forceRanges.beginner;
        const progress = (force - range[0]) / (range[1] - range[0]);

        if (forceBar) forceBar.style.width = `${progress * 100}%`;
        if (forceMarker) forceMarker.style.left = `${progress * 100}%`;
    }

    startRenderLoop() {
        const render = () => {
            this.renderExperienceCanvas();
            this.updateForceDisplay(this.hammerForce);
            this.animationFrame = requestAnimationFrame(render);
        };
        render();
    }

    renderExperienceCanvas() {
        const canvas = document.getElementById('exp-strike-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        ctx.clearRect(0, 0, width, height);

        if (this.thicknessData) {
            const gridSize = this.thicknessData.length;
            const cellW = width / gridSize;
            const cellH = height / gridSize;

            const minT = Math.min(...this.thicknessData.flat());
            const maxT = Math.max(...this.thicknessData.flat());
            const range = maxT - minT || 1;

            for (let i = 0; i < gridSize; i++) {
                for (let j = 0; j < gridSize; j++) {
                    const norm = (this.thicknessData[i][j] - minT) / range;
                    const r = Math.floor(68 * (1 - norm) + 253 * norm);
                    const g = Math.floor(1 * (1 - norm) + 231 * norm);
                    const b = Math.floor(84 * (1 - norm) + 37 * norm);
                    ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
                    ctx.fillRect(j * cellW, i * cellH, cellW + 1, cellH + 1);
                }
            }
        } else {
            ctx.fillStyle = '#d4af37';
            ctx.fillRect(0, 0, width, height);
        }

        const centerX = width / 2;
        const centerY = height / 2;
        const hammerX = centerX + (this.hammerPosition.x / 150) * (width / 2);
        const hammerY = centerY + (this.hammerPosition.y / 150) * (height / 2);

        ctx.save();
        ctx.translate(hammerX, hammerY);

        if (this.isCharging) {
            const chargeTime = Date.now() - this.chargeStart;
            const chargeProgress = Math.min(1, chargeTime / 1000);
            const bobOffset = -30 * chargeProgress;

            this.hammerForce = this.calculateForceFromCharge(chargeProgress);

            ctx.fillStyle = 'rgba(212, 175, 55, 0.3)';
            ctx.beginPath();
            ctx.arc(0, 0, 30 + chargeProgress * 20, 0, Math.PI * 2);
            ctx.fill();

            this.drawHammer(ctx, bobOffset);
        } else {
            this.drawHammer(ctx, 0);
        }

        ctx.restore();

        ctx.strokeStyle = 'rgba(212, 175, 55, 0.5)';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(hammerX, 0);
        ctx.lineTo(hammerX, height);
        ctx.moveTo(0, hammerY);
        ctx.lineTo(width, hammerY);
        ctx.stroke();
        ctx.setLineDash([]);
    }

    drawHammer(ctx, bobOffset) {
        ctx.fillStyle = '#6e7681';
        ctx.fillRect(-8, -60 + bobOffset, 16, 50);

        ctx.fillStyle = '#30363d';
        ctx.beginPath();
        ctx.roundRect(-20, -80 + bobOffset, 40, 25, 5);
        ctx.fill();

        ctx.fillStyle = '#d4af37';
        ctx.beginPath();
        ctx.arc(0, -68 + bobOffset, 8, 0, Math.PI * 2);
        ctx.fill();
    }

    async loadStatus() {
        try {
            const status = await this.apiClient.getVirtualExperienceStatus();
            this.achievements = status.all_achievements || [];
            this.unlockedAchievements = status.achievements_unlocked || [];
            this.renderAchievements();

            if (status.stats) {
                document.getElementById('exp-strikes').textContent = status.stats.total_strikes;
            }
        } catch (e) {
            console.error('加载状态失败:', e);
        }
    }

    renderAchievements() {
        const container = document.getElementById('achievements-grid');
        if (!container || !this.achievements.length) return;

        container.innerHTML = this.achievements.map(ach => {
            const isUnlocked = this.unlockedAchievements.includes(ach.id);
            return `
                <div class="achievement-item ${isUnlocked ? 'unlocked' : 'locked'}" title="${ach.desc}">
                    <div class="achievement-icon">${ach.icon}</div>
                    <div class="achievement-info">
                        <div class="achievement-name">${ach.name}</div>
                        <div class="achievement-desc">${ach.desc}</div>
                    </div>
                    <div class="achievement-points">+${ach.points}</div>
                </div>
            `;
        }).join('');
    }

    async resetExperience() {
        try {
            const result = await this.apiClient.resetVirtualExperience(this.currentMode, this.currentAlloy);
            this.totalScore = 0;
            this.tutorialStep = 0;
            this.thicknessData = null;
            this.unlockedAchievements = [];

            document.getElementById('exp-score').textContent = '0';
            document.getElementById('exp-combo').textContent = '0';
            document.getElementById('exp-strikes').textContent = '0';

            if (this.tutorialEnabled) {
                document.getElementById('tutorial-banner').style.display = 'block';
                this.showTutorialStep(0);
            }

            showToast('success', '已重置', '开始新的打金体验吧！');
        } catch (e) {
            showToast('error', '重置失败', e.message);
        }
    }

    async performAnneal() {
        try {
            await this.apiClient.anneal(450, 10);
            showToast('success', '退火完成', '金箔塑性已恢复');
            this.renderStrikeFeedback({
                message: '🔥 退火完成！金箔硬度降低，可以继续锻打了',
                visual_effect: 'good',
                quality_score: 0.8,
            });
        } catch (e) {
            showToast('error', '退火失败', e.message);
        }
    }

    async completeAndGilding() {
        try {
            const result = await this.apiClient.simulateBuddhaGilding(
                'meditation',
                'gold_leaf_size',
                0.7,
                true
            );

            showToast('success', '贴金完成', `质量评分: ${result.metrics.quality_score.toFixed(1)}分`);

            const newAch = { id: 'buddha_gilder', name: '贴金高手', icon: '🏵️', points: 250, desc: '完成一次佛像贴金' };
            if (!this.unlockedAchievements.includes(newAch.id)) {
                this.updateAchievements([newAch]);
            }

            document.querySelector('[data-tab="buddha"]')?.click();

        } catch (e) {
            showToast('error', '贴金失败', e.message);
        }
    }
}

function showToast(type, title, message = '') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <div class="toast-title">${title}</div>
        ${message ? `<div class="toast-message">${message}</div>` : ''}
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(400px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

export default VirtualExperience;
