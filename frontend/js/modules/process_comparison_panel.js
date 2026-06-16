/**
 * 工艺对比面板模块 - 古代锻制、现代真空镀膜、现代电镀三种工艺的对比分析
 * 提供8个维度的性能对比、雷达图可视化、指标对比表格和工艺推荐
 */

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

window.ProcessComparisonPanel = ProcessComparisonPanel;
