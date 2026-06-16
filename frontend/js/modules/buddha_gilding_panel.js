/**
 * BuddhaGildingPanel - 佛像贴金仿真面板模块
 *
 * 提供佛像贴金工艺的数字化仿真与可视化分析，包含：
 * - 4种佛像类型（禅定印、说法印、施无畏印、观音像）
 * - 3种胶粘剂（金箔胶、骨胶、植物胶）
 * - 表面粗糙度可视化渲染
 * - 光照反射效果仿真
 * - 多维度指标评估（覆盖率、褶皱、破裂、材料利用率等）
 * - 6种热力图可视化（高度场、曲率、覆盖率、褶皱、光照、破裂）
 * - 难度评估与工艺建议
 * - 技能等级参数调节
 *
 * 依赖：
 * - apiClient: API 客户端实例，用于调用后端接口
 * - showToast: 全局提示函数（外部定义或本文件提供）
 *
 * @module buddha_gilding_panel
 */

class BuddhaGildingPanel {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        const skillSlider = document.getElementById('buddha-skill-slider');
        const skillLabel = document.getElementById('buddha-skill-label');
        if (skillSlider && skillLabel) {
            skillSlider.addEventListener('input', (e) => {
                skillLabel.textContent = e.target.value;
            });
        }

        const simulateBtn = document.getElementById('btn-simulate-gilding');
        if (simulateBtn) {
            simulateBtn.addEventListener('click', () => this.simulateGilding());
        }
    }

    async simulateGilding() {
        const buddhaType = document.getElementById('buddha-type').value;
        const adhesive = document.getElementById('buddha-adhesive').value;
        const skillLevel = parseFloat(document.getElementById('buddha-skill-slider').value);
        const useCurrentFoil = document.getElementById('buddha-use-current-foil').checked;

        try {
            const result = await this.apiClient.simulateBuddhaGilding(
                buddhaType, adhesive, skillLevel, useCurrentFoil
            );
            this.renderResult(result);
            this.renderVisualizations(result);
        } catch (e) {
            showToast('error', '仿真失败', e.message);
        }
    }

    renderResult(result) {
        const container = document.getElementById('buddha-result');
        if (!container) return;

        const metrics = result.metrics;

        container.innerHTML = `
            <h4>🏵️ 贴金仿真结果 - ${result.buddha_name}</h4>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
                <div class="metric-card">
                    <div class="metric-label">平均覆盖率</div>
                    <div class="metric-value">${metrics.average_coverage_pct.toFixed(1)}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">褶皱面积</div>
                    <div class="metric-value">${metrics.wrinkle_area_pct.toFixed(1)}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">破裂数量</div>
                    <div class="metric-value">${metrics.tear_count} 处</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">材料利用率</div>
                    <div class="metric-value">${metrics.material_efficiency_pct.toFixed(1)}%</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">预计金箔用量</div>
                    <div class="metric-value">${metrics.estimated_foil_sheets} 张</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">耐久性</div>
                    <div class="metric-value">${metrics.durability_years} 年</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">干燥时间</div>
                    <div class="metric-value">${metrics.estimated_drying_time_hours} h</div>
                </div>
                <div class="metric-card">
                    <div class="metric-label">质量评分</div>
                    <div class="metric-value score-badge ${
                        metrics.quality_score > 80 ? 'score-excellent' :
                        metrics.quality_score > 60 ? 'score-good' : 'score-poor'
                    }">${metrics.quality_score.toFixed(1)}</div>
                </div>
            </div>
            <div class="recommendation-box">
                <strong>💡 工艺建议：</strong>${result.difficulty_assessment.tips.join(' ')}
            </div>
            <div style="margin-top: 12px; padding: 12px; background: rgba(13, 17, 23, 0.5); border-radius: 8px;">
                <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 8px;">
                    <strong>胶粘剂：</strong>${result.adhesive.name}
                </div>
                <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 8px;">
                    <strong>表面效果：</strong>${result.lighting_simulation.luster_description}
                </div>
                <div style="color: var(--text-secondary); font-size: 13px;">
                    <strong>推荐技能等级：</strong>
                    <span class="score-badge ${
                        result.difficulty_assessment.recommended_skill_level === 'beginner' ? 'score-excellent' :
                        result.difficulty_assessment.recommended_skill_level === 'intermediate' ? 'score-good' : 'score-poor'
                    }">${result.difficulty_assessment.recommended_skill_level === 'beginner' ? '初学者' :
                       result.difficulty_assessment.recommended_skill_level === 'intermediate' ? '进阶' : '大师'}</span>
                </div>
            </div>
        `;
    }

    renderVisualizations(result) {
        this.renderHeatmap('buddha-height-canvas', result.height_field_preview, 'viridis');
        this.renderHeatmap('buddha-curvature-canvas', this.curvatureToNumeric(result.curvature_map_preview), 'jet');
        this.renderHeatmap('buddha-coverage-canvas', result.coverage_map, 'viridis');
        this.renderHeatmap('buddha-wrinkle-canvas', result.wrinkle_map, 'hot');
        this.renderHeatmap('buddha-lighting-canvas', result.lighting_simulation.total_reflection, 'gold');
        this.renderHeatmap('buddha-tear-canvas', result.tear_map, 'red');
    }

    curvatureToNumeric(curvatureMap) {
        const mapping = { 'flat_surface': 0, 'gentle_curve': 0.33, 'sharp_curve': 0.66, 'complex_3d': 1 };
        return curvatureMap.map(row => row.map(cell => mapping[cell] || 0));
    }

    renderHeatmap(canvasId, data, colormap) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;
        const gridSize = data.length;
        const cellW = width / gridSize;
        const cellH = height / gridSize;

        ctx.clearRect(0, 0, width, height);

        for (let i = 0; i < gridSize; i++) {
            for (let j = 0; j < gridSize; j++) {
                const val = data[i][j];
                const color = this.getValueColor(val, colormap);
                ctx.fillStyle = color;
                ctx.fillRect(j * cellW, i * cellH, cellW + 1, cellH + 1);
            }
        }
    }

    getValueColor(value, colormap) {
        const v = Math.max(0, Math.min(1, value));

        if (colormap === 'viridis') {
            const r = Math.floor(68 * (1 - v) + 253 * v);
            const g = Math.floor(1 * (1 - v) + 231 * v);
            const b = Math.floor(84 * (1 - v) + 37 * v);
            return `rgb(${r}, ${g}, ${b})`;
        } else if (colormap === 'jet') {
            let r, g, b;
            if (v < 0.25) { r = 0; g = Math.floor(v * 4 * 255); b = 255; }
            else if (v < 0.5) { r = 0; g = 255; b = Math.floor((0.5 - v) * 4 * 255); }
            else if (v < 0.75) { r = Math.floor((v - 0.5) * 4 * 255); g = 255; b = 0; }
            else { r = 255; g = Math.floor((1 - v) * 4 * 255); b = 0; }
            return `rgb(${r}, ${g}, ${b})`;
        } else if (colormap === 'hot') {
            const r = Math.floor(255 * Math.min(1, v * 2));
            const g = Math.floor(255 * Math.max(0, (v - 0.33) * 1.5));
            const b = Math.floor(255 * Math.max(0, (v - 0.66) * 3));
            return `rgb(${r}, ${g}, ${b})`;
        } else if (colormap === 'gold') {
            const r = Math.floor(139 * (1 - v) + 255 * v);
            const g = Math.floor(115 * (1 - v) + 215 * v);
            const b = Math.floor(55 * (1 - v) + 0 * v);
            return `rgb(${r}, ${g}, ${b})`;
        } else if (colormap === 'red') {
            const alpha = value ? 0.8 : 0.2;
            return value ? `rgba(248, 81, 73, ${alpha})` : `rgba(13, 17, 23, 0.5)`;
        }
        return `rgb(${v * 255}, ${v * 255}, ${v * 255})`;
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

export default BuddhaGildingPanel;
