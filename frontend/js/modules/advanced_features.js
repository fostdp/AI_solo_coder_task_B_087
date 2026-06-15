/**
 * 高级功能模块 - 合金配比、工艺对比、佛像贴金、虚拟打金体验
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

class ProcessComparisonPanel {
    constructor(apiClient) {
        this.apiClient = apiClient;
        this.init();
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        const thicknessSlider = document.getElementById('process-thickness-slider');
        const thicknessLabel = document.getElementById('process-thickness-label');
        if (thicknessSlider && thicknessLabel) {
            thicknessSlider.addEventListener('input', (e) => {
                thicknessLabel.textContent = e.target.value;
            });
        }

        const areaSlider = document.getElementById('process-area-slider');
        const areaLabel = document.getElementById('process-area-label');
        if (areaSlider && areaLabel) {
            areaSlider.addEventListener('input', (e) => {
                areaLabel.textContent = e.target.value;
            });
        }

        const compareBtn = document.getElementById('btn-compare-process');
        if (compareBtn) {
            compareBtn.addEventListener('click', () => this.compareProcesses());
        }
    }

    async compareProcesses() {
        const targetThickness = parseFloat(document.getElementById('process-thickness-slider').value);
        const productionArea = parseFloat(document.getElementById('process-area-slider').value);
        const useCase = document.getElementById('process-usecase').value;

        try {
            const result = await this.apiClient.compareProcesses(targetThickness, productionArea, useCase);
            this.renderResult(result);
            this.drawRadarChart(result);
            this.renderDetailGrid(result);
        } catch (e) {
            showToast('error', '对比失败', e.message);
        }
    }

    renderResult(result) {
        const container = document.getElementById('process-compare-result');
        if (!container) return;

        const metrics = [
            { key: 'uniformity_error_pct', label: '均匀度误差', suffix: '%', lowerBetter: true },
            { key: 'total_energy_kwh', label: '总能耗', suffix: ' kWh', lowerBetter: true },
            { key: 'total_labor_hours', label: '总工时', suffix: ' h', lowerBetter: true },
            { key: 'estimated_total_cost_cny', label: '预估成本', suffix: ' 元', lowerBetter: true },
            { key: 'environmental_impact_score', label: '环境影响', suffix: '', lowerBetter: true },
            { key: 'surface_roughness_um', label: '表面粗糙度', suffix: ' μm', lowerBetter: true },
            { key: 'material_utilization_pct', label: '材料利用率', suffix: '%', lowerBetter: false },
            { key: 'weighted_total_score', label: '综合得分', suffix: '', lowerBetter: false },
        ];

        const processes = [
            { key: 'ancient_forging', name: '古代锻制', data: result.ancient_forging },
            { key: 'modern_vacuum_coating', name: '现代真空镀膜', data: result.modern_vacuum_coating },
            { key: 'modern_electroplating', name: '现代电镀', data: result.modern_electroplating },
        ];

        container.innerHTML = `
            <h4>⚙️ 工艺对比结果</h4>
            <div class="recommendation-box">${result.recommendation}</div>
            <table class="compare-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        ${processes.map(p => `<th>${p.name}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${metrics.map(metric => `
                        <tr>
                            <td>${metric.label}</td>
                            ${processes.map(p => {
                                const val = p.data[metric.key];
                                const values = processes.map(pp => pp.data[metric.key]);
                                const bestVal = metric.lowerBetter ? Math.min(...values) : Math.max(...values);
                                const isBest = val === bestVal;
                                const scoreClass = val < 30 ? 'score-excellent' : val < 70 ? 'score-good' : 'score-poor';
                                const displayVal = typeof val === 'number' ? val.toFixed(2) : val;
                                return `<td>
                                    <span class="${isBest ? 'score-badge ' + scoreClass : ''}">
                                        ${displayVal}${metric.suffix}
                                    </span>
                                </td>`;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }

    drawRadarChart(result) {
        const canvas = document.getElementById('process-radar-canvas');
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        const radius = Math.min(centerX, centerY) - 40;
        const labels = result.radar_chart_data.labels;
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

        const labelMap = {
            'uniformity': '均匀性',
            'min_thickness': '最小厚度',
            'energy_efficiency': '能效',
            'labor_efficiency': '人效',
            'environmental_impact': '环保',
            'surface_quality': '表面质量',
            'material_utilization': '材料利用',
            'total_cost': '成本'
        };

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
            ctx.fillText(labelMap[labels[i]] || labels[i], labelX, labelY);
        }

        const colors = [
            'rgba(212, 175, 55, 0.4)',
            'rgba(88, 166, 255, 0.4)',
            'rgba(248, 81, 73, 0.4)',
        ];

        result.radar_chart_data.datasets.forEach((dataset, idx) => {
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
        result.radar_chart_data.datasets.forEach((dataset, idx) => {
            ctx.fillStyle = colors[idx % colors.length].replace('0.4', '1');
            ctx.fillRect(legendX, legendY, 12, 12);
            ctx.fillStyle = 'var(--text-primary)';
            ctx.font = '12px "Microsoft YaHei", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(dataset.label, legendX + 20, legendY + 10);
            legendX += ctx.measureText(dataset.label).width + 60;
        });
    }

    renderDetailGrid(result) {
        const container = document.getElementById('process-detail-grid');
        if (!container) return;

        const processes = [
            { key: 'ancient_forging', name: '古代锻制', data: result.ancient_forging, icon: '🏺' },
            { key: 'modern_vacuum_coating', name: '现代真空镀膜', data: result.modern_vacuum_coating, icon: '⚡' },
            { key: 'modern_electroplating', name: '现代电镀', data: result.modern_electroplating, icon: '🔋' },
        ];

        container.innerHTML = processes.map(p => `
            <div class="process-card">
                <h5>${p.icon} ${p.name}</h5>
                <div class="process-stat">
                    <span class="process-stat-label">最小可达厚度</span>
                    <span class="process-stat-value">${p.data.achievable_thickness_um} μm</span>
                </div>
                <div class="process-stat">
                    <span class="process-stat-label">均匀度误差</span>
                    <span class="process-stat-value">${p.data.uniformity_error_pct}%</span>
                </div>
                <div class="process-stat">
                    <span class="process-stat-label">表面粗糙度</span>
                    <span class="process-stat-value">${p.data.surface_roughness_um} μm</span>
                </div>
                <div class="process-stat">
                    <span class="process-stat-label">材料利用率</span>
                    <span class="process-stat-value">${p.data.material_utilization_pct}%</span>
                </div>
                <div class="process-stat">
                    <span class="process-stat-label">环境影响</span>
                    <span class="process-stat-value">${p.data.environmental_impact_score}/10</span>
                </div>
                <div class="process-stat">
                    <span class="process-stat-label">综合评分</span>
                    <span class="process-stat-value score-badge ${
                        p.data.weighted_total_score > 70 ? 'score-excellent' :
                        p.data.weighted_total_score > 40 ? 'score-good' : 'score-poor'
                    }">${p.data.weighted_total_score.toFixed(1)}</span>
                </div>
                <div class="process-defects">
                    <div class="process-defects-title">典型缺陷：</div>
                    ${p.data.typical_defects.map(d => `<span class="process-defect-tag">${d}</span>`).join('')}
                </div>
            </div>
        `).join('');
    }
}

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

    playStrikeSound(frequency, duration, quality) {
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

    setupEventListeners() {
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

        document.getElementById('exp-mode')?.addEventListener('change', (e) => {
            this.currentMode = e.target.value;
            this.updateForceRange();
        });

        document.getElementById('exp-alloy')?.addEventListener('change', (e) => {
            this.currentAlloy = e.target.value;
        });

        document.getElementById('btn-exp-reset')?.addEventListener('click', () => this.resetExperience());
        document.getElementById('btn-exp-strike')?.addEventListener('click', () => this.performStrike());
        document.getElementById('btn-exp-anneal')?.addEventListener('click', () => this.performAnneal());
        document.getElementById('btn-exp-gilding')?.addEventListener('click', () => this.completeAndGilding());

        document.getElementById('tutorial-prev')?.addEventListener('click', () => this.prevTutorialStep());
        document.getElementById('tutorial-next')?.addEventListener('click', () => this.nextTutorialStep());
        document.getElementById('tutorial-skip')?.addEventListener('click', () => this.skipTutorial());

        document.addEventListener('keydown', (e) => {
            if (e.code === 'Space') {
                e.preventDefault();
                const activeTab = document.querySelector('.tab-btn.active')?.dataset.tab;
                if (activeTab === 'experience') {
                    this.performStrike();
                }
            }
        });
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
        this.chargeHammer();
    }

    handleMouseUp() {
        if (this.isCharging) {
            this.performStrike();
        }
        this.isCharging = false;
        this.chargeStart = 0;
    }

    chargeHammer() {
        this.isCharging = true;
        this.chargeStart = Date.now();
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

    startRenderLoop() {
        const render = () => {
            this.renderExperienceCanvas();
            this.updateForceDisplay();
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

    calculateForceFromCharge(progress) {
        const forceRanges = {
            beginner: [200, 800],
            intermediate: [300, 1500],
            master: [500, 3000],
        };
        const range = forceRanges[this.currentMode] || forceRanges.beginner;
        return range[0] + progress * (range[1] - range[0]);
    }

    updateForceDisplay() {
        const forceLabel = document.getElementById('exp-force-label');
        const forceBar = document.getElementById('force-bar');
        const forceMarker = document.getElementById('force-marker');

        if (forceLabel) forceLabel.textContent = Math.round(this.hammerForce);

        const forceRanges = {
            beginner: [200, 800],
            intermediate: [300, 1500],
            master: [500, 3000],
        };
        const range = forceRanges[this.currentMode] || forceRanges.beginner;
        const progress = (this.hammerForce - range[0]) / (range[1] - range[0]);

        if (forceBar) forceBar.style.width = `${progress * 100}%`;
        if (forceMarker) forceMarker.style.left = `${progress * 100}%`;
    }

    async performStrike() {
        try {
            const result = await this.apiClient.virtualExperienceStrike(
                this.hammerForce,
                this.hammerPosition.x,
                this.hammerPosition.y,
                15,
                this.currentMode
            );

            if (result.state?.thickness_distribution?.data) {
                this.thicknessData = result.state.thickness_distribution.data;
            }

            if (result.feedback) {
                this.playStrikeSound(
                    result.feedback.sound_frequency_hz,
                    result.feedback.sound_duration_ms,
                    result.feedback.quality_score
                );

                this.showFeedback(result.feedback);
            }

            if (result.score) {
                this.totalScore += result.score.total_score;
                this.updateScoreDisplay(result);
            }

            if (result.new_achievements && result.new_achievements.length > 0) {
                result.new_achievements.forEach(ach => {
                    this.showAchievementPopup(ach);
                    this.unlockedAchievements.push(ach.id);
                });
                this.renderAchievements();
            }

            this.updateStats(result.stats);

        } catch (e) {
            showToast('error', '锤击失败', e.message);
        }
    }

    showFeedback(feedback) {
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

    updateScoreDisplay(result) {
        document.getElementById('exp-score').textContent = Math.round(this.totalScore);
        document.getElementById('exp-combo').textContent = result.score.consecutive_good_strikes;
    }

    updateStats(stats) {
        document.getElementById('exp-strikes').textContent = stats.total_strikes;
    }

    showAchievementPopup(achievement) {
        const popup = document.createElement('div');
        popup.className = 'achievement-popup';
        popup.innerHTML = `
            <div class="achievement-popup-icon">${achievement.icon}</div>
            <div class="achievement-popup-info">
                <h5>🎉 成就解锁！</h5>
                <p><strong>${achievement.name}</strong> - ${achievement.desc}</p>
                <p style="color: var(--accent-gold);">+${achievement.points} 分</p>
            </div>
        `;

        document.body.appendChild(popup);

        setTimeout(() => {
            popup.style.animation = 'achievementSlideIn 0.5s ease reverse';
            setTimeout(() => popup.remove(), 500);
        }, 3000);
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
                this.updateTutorialDisplay();
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
            this.showFeedback({
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
                this.showAchievementPopup(newAch);
                this.unlockedAchievements.push(newAch.id);
                this.renderAchievements();
            }

            document.querySelector('[data-tab="buddha"]')?.click();

        } catch (e) {
            showToast('error', '贴金失败', e.message);
        }
    }

    updateTutorialDisplay() {
        const tutorials = [
            { title: '认识工具', text: '这是您的锻锤，可以通过鼠标或触控操作控制锤击力度和位置' },
            { title: '第一次锤击', text: '点击金箔中央，尝试一次轻锤。观察厚度变化' },
            { title: '理解厚度', text: '蓝色区域较薄，红色区域较厚。我们需要让金箔均匀变薄' },
            { title: '厚处打重锤', text: '应该在较厚的地方（红色）使用更大的力度' },
            { title: '退火处理', text: '当金箔变硬时（加工硬化），需要进行退火处理恢复塑性' },
            { title: '小心破裂', text: '避免在同一位置连续重锤，否则金箔会破裂！' },
            { title: '开始您的创作', text: '目标：将500μm厚的金片锻打到0.5μm，均匀度90%以上。祝您成功！' },
        ];

        if (this.tutorialStep >= 0 && this.tutorialStep < tutorials.length) {
            const t = tutorials[this.tutorialStep];
            document.getElementById('tutorial-step').textContent = `${this.tutorialStep + 1}/${tutorials.length}`;
            document.getElementById('tutorial-title').textContent = t.title;
            document.getElementById('tutorial-text').textContent = t.text;
        }
    }

    nextTutorialStep() {
        this.tutorialStep++;
        if (this.tutorialStep >= 7) {
            this.skipTutorial();
        } else {
            this.updateTutorialDisplay();
        }
    }

    prevTutorialStep() {
        if (this.tutorialStep > 0) {
            this.tutorialStep--;
            this.updateTutorialDisplay();
        }
    }

    skipTutorial() {
        this.tutorialEnabled = false;
        document.getElementById('tutorial-banner').style.display = 'none';
        showToast('info', '教程已跳过', '可以自由探索了！');
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
