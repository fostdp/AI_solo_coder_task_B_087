/**
 * AlloyPanel - 合金配比面板模块
 * 
 * 功能特性：
 * - 加载和展示合金列表
 * - 合金选择与切换
 * - 多种合金性能对比
 * - 雷达图可视化展示
 * - 温度参数调节
 * 
 * 依赖：
 * - apiClient: API 客户端实例，用于调用后端接口
 * - showToast: 全局提示函数（外部定义）
 */

class AlloyPanel {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.alloys = [];
        this.currentAlloy = null;
        this.tutorialStep = 0;
        this.init();
    }

    async init() {
        await this.loadAlloys();
        this.setupEventListeners();
    }

    async loadAlloys() {
        try {
            const data = await this.apiClient.getAllAlloys();
            this.alloys = data.alloys;
            this.currentAlloy = data.current_alloy_key;
            this.renderAlloyList();
            this.renderCompareSelect();
        } catch (e) {
            console.error('加载合金列表失败:', e);
        }
    }

    renderAlloyList() {
        const container = document.getElementById('alloy-list');
        if (!container) return;

        container.innerHTML = this.alloys.map(alloy => {
            const rgb = alloy.color_rgb;
            const colorStyle = `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
            const isActive = alloy.key === this.currentAlloy ? 'active' : '';

            return `
                <div class="alloy-card ${isActive}" data-alloy="${alloy.key}">
                    <div class="alloy-header">
                        <div class="alloy-color-preview" style="background: ${colorStyle};"></div>
                        <div>
                            <div class="alloy-name">${alloy.name}</div>
                        </div>
                    </div>
                    <div class="alloy-composition">
                        ${alloy.composition.gold_pct.toFixed(2)}% 金
                        ${alloy.composition.copper_pct > 0 ? ' + ' + alloy.composition.copper_pct.toFixed(2) + '% 铜' : ''}
                        ${alloy.composition.silver_pct > 0 ? ' + ' + alloy.composition.silver_pct.toFixed(2) + '% 银' : ''}
                    </div>
                    <div class="alloy-metrics">
                        <div class="alloy-metric">
                            <span class="alloy-metric-label">延展性</span>
                            <span class="alloy-metric-value">${(alloy.malleability_factor * 100).toFixed(0)}%</span>
                        </div>
                        <div class="alloy-metric">
                            <span class="alloy-metric-label">硬度 HV</span>
                            <span class="alloy-metric-value">${alloy.hardness_vickers}</span>
                        </div>
                    </div>
                    <div class="alloy-description">${alloy.description}</div>
                    <div class="alloy-tags">
                        ${alloy.typical_uses.map(use => `<span class="alloy-tag">${use}</span>`).join('')}
                    </div>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.alloy-card').forEach(card => {
            card.addEventListener('click', () => this.selectAlloy(card.dataset.alloy));
        });
    }

    renderCompareSelect() {
        const container = document.getElementById('alloy-compare-select');
        if (!container) return;

        container.innerHTML = this.alloys.map(alloy => `
            <label>
                <input type="checkbox" value="${alloy.key}" ${['pure_gold_24k', 'gold_copper_22k', 'gold_silver_22k'].includes(alloy.key) ? 'checked' : ''}>
                <span>${alloy.name}</span>
            </label>
        `).join('');
    }

    async selectAlloy(key) {
        try {
            const result = await this.apiClient.selectAlloy(key);
            this.currentAlloy = key;
            this.renderAlloyList();
            showToast('success', '合金已切换', `当前使用: ${result.alloy.name}`);
        } catch (e) {
            showToast('error', '切换失败', e.message);
        }
    }

    async compareAlloys() {
        const checkboxes = document.querySelectorAll('#alloy-compare-select input:checked');
        const keys = Array.from(checkboxes).map(cb => cb.value);
        const temp = parseFloat(document.getElementById('alloy-temp-slider').value);

        if (keys.length < 2) {
            showToast('warning', '请选择至少两种合金进行对比');
            return;
        }

        try {
            const result = await this.apiClient.compareAlloys(keys, temp);
            this.renderCompareResult(result);
            this.drawRadarChart(result);
        } catch (e) {
            showToast('error', '对比失败', e.message);
        }
    }

    renderCompareResult(result) {
        const container = document.getElementById('alloy-compare-result');
        if (!container) return;

        const rows = [
            { key: '金含量%', prop: 'composition.gold_pct', suffix: '%' },
            { key: '延展性系数', prop: 'ductility_metrics.malleability_factor', suffix: '', isPct: true },
            { key: '最大延伸率', prop: 'ductility_metrics.max_elongation_pct', suffix: '%' },
            { key: '硬度 HV', prop: 'ductility_metrics.hardness_vickers', suffix: '' },
            { key: '杨氏模量 GPa', prop: 'material_properties.youngs_modulus_gpa', suffix: '' },
            { key: '屈服强度 MPa', prop: 'material_properties.yield_strength_mpa', suffix: '' },
            { key: '密度 kg/m³', prop: 'material_properties.density_kgm3', suffix: '' },
            { key: '再结晶温度 °C', prop: 'material_properties.recrystallization_temp_c', suffix: '' },
            { key: '熔点 °C', prop: 'material_properties.melting_point_c', suffix: '' },
        ];

        container.innerHTML = `
            <h4>📊 性能对比结果</h4>
            <div class="recommendation-box">${result.recommendation.summary}</div>
            <table class="compare-table">
                <thead>
                    <tr>
                        <th>性能指标</th>
                        ${result.alloys.map(a => `<th>${a.name}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${rows.map(row => `
                        <tr>
                            <td>${row.key}</td>
                            ${result.alloys.map(a => {
                                const val = this.getNestedValue(a, row.prop);
                                const displayVal = row.isPct ? (val * 100).toFixed(1) : (typeof val === 'number' ? val.toFixed(2) : val);
                                return `<td>${displayVal}${row.suffix}</td>`;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--border-color);">
                <div style="color: var(--text-secondary); font-size: 13px; margin-bottom: 8px;">
                    <strong>💡 工艺建议：</strong>
                </div>
                <div style="color: var(--text-primary); font-size: 13px; line-height: 1.8;">
                    • 延展性最佳：<span style="color: var(--accent-gold); font-weight: 600;">${result.recommendation.best_ductility}</span><br>
                    • 硬度最高：<span style="color: var(--accent-gold); font-weight: 600;">${result.recommendation.best_hardness}</span><br>
                    • 性价比最高：<span style="color: var(--accent-gold); font-weight: 600;">${result.recommendation.best_cost_effective}</span>
                </div>
            </div>
        `;
    }

    drawRadarChart(result) {
        const canvas = document.getElementById('alloy-radar-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 40;
        const labels = result.radar_chart.labels;
        const numAxes = labels.length;
        const angleStep = (Math.PI * 2) / numAxes;

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 1; i <= 5; i++) {
            const r = (radius / 5) * i;
            ctx.beginPath();
            ctx.strokeStyle = 'rgba(139, 148, 158, 0.3)';
            ctx.lineWidth = 1;
            for (let j = 0; j < numAxes; j++) {
                const angle = j * angleStep - Math.PI / 2;
                const x = centerX + r * Math.cos(angle);
                const y = centerY + r * Math.sin(angle);
                if (j === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.stroke();
        }

        for (let i = 0; i < numAxes; i++) {
            const angle = i * angleStep - Math.PI / 2;
            const x = centerX + radius * Math.cos(angle);
            const y = centerY + radius * Math.sin(angle);
            ctx.beginPath();
            ctx.moveTo(centerX, centerY);
            ctx.lineTo(x, y);
            ctx.strokeStyle = 'rgba(139, 148, 158, 0.5)';
            ctx.stroke();

            const labelX = centerX + (radius + 25) * Math.cos(angle);
            const labelY = centerY + (radius + 25) * Math.sin(angle);
            ctx.fillStyle = 'var(--text-secondary)';
            ctx.font = '12px "Microsoft YaHei", sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(labels[i], labelX, labelY);
        }

        const colors = [
            'rgba(212, 175, 55, 0.4)',
            'rgba(88, 166, 255, 0.4)',
            'rgba(163, 113, 247, 0.4)',
            'rgba(63, 185, 80, 0.4)',
            'rgba(248, 81, 73, 0.4)',
        ];

        result.radar_chart.datasets.forEach((dataset, idx) => {
            const data = dataset.data;
            ctx.beginPath();
            for (let i = 0; i < numAxes; i++) {
                const angle = i * angleStep - Math.PI / 2;
                const value = data[i] / 100;
                const r = radius * value;
                const x = centerX + r * Math.cos(angle);
                const y = centerY + r * Math.sin(angle);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            }
            ctx.closePath();
            ctx.fillStyle = colors[idx % colors.length];
            ctx.fill();
            ctx.strokeStyle = colors[idx % colors.length].replace('0.4', '1');
            ctx.lineWidth = 2;
            ctx.stroke();
        });

        const legendY = 20;
        let legendX = 20;
        result.radar_chart.datasets.forEach((dataset, idx) => {
            ctx.fillStyle = colors[idx % colors.length].replace('0.4', '1');
            ctx.fillRect(legendX, legendY, 12, 12);
            ctx.fillStyle = 'var(--text-primary)';
            ctx.font = '12px "Microsoft YaHei", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(dataset.label, legendX + 20, legendY + 10);
            legendX += ctx.measureText(dataset.label).width + 60;
        });
    }

    getNestedValue(obj, path) {
        return path.split('.').reduce((o, k) => o?.[k], obj);
    }

    setupEventListeners() {
        const tempSlider = document.getElementById('alloy-temp-slider');
        const tempLabel = document.getElementById('alloy-temp-label');
        if (tempSlider && tempLabel) {
            tempSlider.addEventListener('input', (e) => {
                tempLabel.textContent = e.target.value;
            });
        }

        const compareBtn = document.getElementById('btn-compare-alloys');
        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.compareAlloys());
        }
    }
}

window.AlloyPanel = AlloyPanel;
