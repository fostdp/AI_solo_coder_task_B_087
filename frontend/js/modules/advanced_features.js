/**
 * 高级功能模块 - 合金配比、工艺对比、佛像贴金、虚拟打金体验
 * 
 * 本文件已重构为聚合入口文件，从4个独立模块导入并重新导出：
 * - alloy_panel.js         - 合金配比分析面板
 * - process_comparison_panel.js  - 工艺对比分析面板
 * - buddha_gilding_panel.js - 佛像贴金仿真面板
 * - virtual_experience.js   - 虚拟打金体验
 * 
 * 保持向后兼容：所有原有导出均保持不变
 */

import AlloyPanel from './alloy_panel.js';
import ProcessComparisonPanel from './process_comparison_panel.js';
import BuddhaGildingPanel from './buddha_gilding_panel.js';
import VirtualExperience from './virtual_experience.js';

if (typeof window !== 'undefined') {
    window.AlloyPanel = AlloyPanel;
    window.ProcessComparisonPanel = ProcessComparisonPanel;
    window.BuddhaGildingPanel = BuddhaGildingPanel;
    window.VirtualExperience = VirtualExperience;
}

export {
    AlloyPanel,
    ProcessComparisonPanel,
    BuddhaGildingPanel,
    VirtualExperience,
};

export default {
    AlloyPanel,
    ProcessComparisonPanel,
    BuddhaGildingPanel,
    VirtualExperience,
};
