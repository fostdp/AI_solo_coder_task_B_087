"""
合金成分分析模块 - 用于管理和分析金箔锻制中的合金配比参数

该模块提供了：
- AlloyComposition 数据类：封装合金的成分、物理属性和力学性能
- 工厂函数：根据配置创建合金实例
- 默认合金配置：24K纯金、22K金铜合金等标准配比
- 合金对比分析：多维度性能对比和可视化数据准备

主要用于金箔锻制工艺仿真中的材料选择、性能预测和工艺参数优化。
"""
import numpy as np
from dataclasses import dataclass
from typing import Tuple, List, Optional, Dict

from .physics_model import MaterialProperties


@dataclass
class AlloyComposition:
    """合金配比参数 - 影响延展性、硬度、色泽"""
    key: str
    name: str
    gold_ratio: float
    copper_ratio: float
    silver_ratio: float
    color_rgb: Tuple[int, int, int]
    malleability_factor: float
    hardness_vickers: float
    historical_period: str
    typical_uses: List[str]
    description: str

    def __post_init__(self):
        self.youngs_modulus_alloy = 79.0 * (1.0 + 0.3 * self.copper_ratio + 0.1 * self.silver_ratio)
        self.yield_strength_alloy = 120.0 * (1.0 + 2.5 * self.copper_ratio + 1.5 * self.silver_ratio)
        self.ultimate_strength_alloy = 210.0 * (1.0 + 1.8 * self.copper_ratio + 1.0 * self.silver_ratio)
        self.density_alloy = (
            19300.0 * self.gold_ratio
            + 8960.0 * self.copper_ratio
            + 10490.0 * self.silver_ratio
        )
        self.recrystallization_temp_alloy = (
            200.0 * self.gold_ratio
            + 270.0 * self.copper_ratio
            + 220.0 * self.silver_ratio
        )
        self.melting_point_alloy = (
            1064.0 * self.gold_ratio
            + 1085.0 * self.copper_ratio
            + 961.0 * self.silver_ratio
        )
        self.work_hardening_coeff_alloy = 0.45 * (1.0 - 0.3 * self.copper_ratio)
        self.work_hardening_exp_alloy = 0.35 * (1.0 - 0.2 * self.silver_ratio)

    def to_material_properties(self) -> MaterialProperties:
        """转换为 MaterialProperties 供物理模型使用"""
        return MaterialProperties(
            youngs_modulus=self.youngs_modulus_alloy,
            poisson_ratio=0.42 * (1.0 - 0.05 * self.copper_ratio),
            yield_strength=self.yield_strength_alloy,
            ultimate_strength=self.ultimate_strength_alloy,
            density=self.density_alloy,
            initial_thickness_um=500.0,
            work_hardening_coeff=self.work_hardening_coeff_alloy,
            work_hardening_exp=self.work_hardening_exp_alloy,
            recrystallization_temp=self.recrystallization_temp_alloy,
            melting_point=self.melting_point_alloy,
        )

    def get_ductility_metrics(self, temperature_c: float = 25.0) -> dict:
        """计算延展性指标"""
        temp_factor = 1.0
        if temperature_c > self.recrystallization_temp_alloy:
            temp_factor = 1.5

        max_elongation_pct = (
            60.0 * self.malleability_factor
            * temp_factor
            * (1.0 - 0.5 * self.copper_ratio)
        )
        reduction_in_area_pct = (
            80.0 * self.malleability_factor
            * temp_factor
            * (1.0 - 0.4 * self.copper_ratio)
        )
        strain_rate_sensitivity = 0.05 + 0.1 * self.copper_ratio

        return {
            "alloy_key": self.key,
            "alloy_name": self.name,
            "max_elongation_pct": float(max_elongation_pct),
            "reduction_in_area_pct": float(reduction_in_area_pct),
            "strain_rate_sensitivity": float(strain_rate_sensitivity),
            "hardness_vickers": float(self.hardness_vickers),
            "malleability_factor": float(self.malleability_factor),
            "formability_index": float(
                (max_elongation_pct * reduction_in_area_pct) / 100.0
            ),
            "temperature_c": float(temperature_c),
            "temperature_factor": float(temp_factor),
            "color_rgb": list(self.color_rgb),
        }

    def compare_with_pure_gold(self) -> dict:
        """与纯金性能对比"""
        return {
            "ductility_ratio": float(self.malleability_factor),
            "hardness_ratio": float(self.hardness_vickers / 25.0),
            "yield_strength_ratio": float(self.yield_strength_alloy / 120.0),
            "density_ratio": float(self.density_alloy / 19300.0),
            "cost_ratio": float(self.gold_ratio),
            "wear_resistance_relative": float(1.0 + 1.5 * self.copper_ratio),
            "tarnish_resistance_relative": float(1.0 - 0.3 * self.copper_ratio),
        }


def get_alloy_composition(key: str, config: Optional[Dict] = None) -> Optional[AlloyComposition]:
    """
    工厂函数：根据配置创建 AlloyComposition 实例

    参数:
        key: 合金配比键名
        config: 材料配置字典（从 material.json 读取的 alloy_compositions）

    返回:
        AlloyComposition 实例，若不存在则返回 None
    """
    if config is None:
        default_alloys = _default_alloy_config()
        alloy_cfg = default_alloys.get(key)
    else:
        alloy_cfg = config.get(key)

    if alloy_cfg is None:
        return None

    return AlloyComposition(
        key=key,
        name=alloy_cfg.get("name", key),
        gold_ratio=alloy_cfg.get("gold_ratio", 1.0),
        copper_ratio=alloy_cfg.get("copper_ratio", 0.0),
        silver_ratio=alloy_cfg.get("silver_ratio", 0.0),
        color_rgb=tuple(alloy_cfg.get("color_rgb", [255, 215, 0])),
        malleability_factor=alloy_cfg.get("malleability_factor", 1.0),
        hardness_vickers=alloy_cfg.get("hardness_vickers", 25),
        historical_period=alloy_cfg.get("historical_period", "未知"),
        typical_uses=list(alloy_cfg.get("typical_uses", [])),
        description=alloy_cfg.get("description", ""),
    )


def _default_alloy_config() -> Dict:
    """默认合金配置（当无法从文件读取时使用）"""
    return {
        "pure_gold_24k": {
            "name": "纯金 (24K)",
            "gold_ratio": 0.9999,
            "copper_ratio": 0.0,
            "silver_ratio": 0.0,
            "color_rgb": [255, 215, 0],
            "malleability_factor": 1.0,
            "hardness_vickers": 25,
            "historical_period": "商代至今",
            "typical_uses": ["皇家器物", "佛像贴金", "高级装饰"],
            "description": "99.99% 纯金，延展性最佳，南京金箔传统用料",
        },
        "gold_copper_22k": {
            "name": "金铜合金 (22K)",
            "gold_ratio": 0.9167,
            "copper_ratio": 0.0833,
            "silver_ratio": 0.0,
            "color_rgb": [255, 200, 50],
            "malleability_factor": 0.85,
            "hardness_vickers": 60,
            "historical_period": "唐代开始普及",
            "typical_uses": ["日用金器", "建筑装饰", "普通佛像"],
            "description": "91.67%金 + 8.33%铜，硬度增加，耐磨性提升",
        },
    }


def compare_alloys(alloy_keys: List[str], config: Optional[Dict] = None) -> Dict:
    """
    对比多种合金的性能参数

    参数:
        alloy_keys: 合金键名列表
        config: 材料配置字典

    返回:
        对比结果字典
    """
    alloys = [get_alloy_composition(key, config) for key in alloy_keys]
    alloys = [a for a in alloys if a is not None]

    if len(alloys) < 2:
        return {"error": "需要至少两种合金进行对比"}

    metrics_list = [a.get_ductility_metrics() for a in alloys]
    comparisons = [a.compare_with_pure_gold() for a in alloys]

    radar_labels = [
        "延展性系数", "硬度 HV", "屈服强度比",
        "密度比", "成本比", "耐磨性", "耐变色性"
    ]

    radar_datasets = []
    for a, comp in zip(alloys, comparisons):
        radar_data = [
            a.malleability_factor * 100,
            min(a.hardness_vickers / 120.0 * 100, 100),
            min(comp["yield_strength_ratio"] / 3.0 * 100, 100),
            comp["density_ratio"] * 100,
            comp["cost_ratio"] * 100,
            comp["wear_resistance_relative"] * 100,
            comp["tarnish_resistance_relative"] * 100,
        ]
        radar_datasets.append({
            "label": a.name,
            "data": radar_data,
            "color_rgb": list(a.color_rgb),
        })

    best_alloy = max(alloys, key=lambda a: a.malleability_factor)

    return {
        "alloys": [
            {
                "key": a.key,
                "name": a.name,
                "composition": {
                    "gold_pct": a.gold_ratio * 100,
                    "copper_pct": a.copper_ratio * 100,
                    "silver_pct": a.silver_ratio * 100,
                },
                "ductility_metrics": m,
                "comparison_with_pure_gold": c,
                "material_properties": {
                    "youngs_modulus_gpa": a.youngs_modulus_alloy,
                    "yield_strength_mpa": a.yield_strength_alloy,
                    "ultimate_strength_mpa": a.ultimate_strength_alloy,
                    "density_kgm3": a.density_alloy,
                    "recrystallization_temp_c": a.recrystallization_temp_alloy,
                    "melting_point_c": a.melting_point_alloy,
                },
                "color_rgb": list(a.color_rgb),
            }
            for a, m, c in zip(alloys, metrics_list, comparisons)
        ],
        "radar_chart": {
            "labels": radar_labels,
            "datasets": radar_datasets,
        },
        "recommendation": {
            "best_ductility": f"{best_alloy.name} ({best_alloy.key})",
            "best_hardness": max(alloys, key=lambda a: a.hardness_vickers).name,
            "best_cost_effective": min(alloys, key=lambda a: a.gold_ratio).name,
            "summary": "对于佛像贴金推荐纯金(24K)以获得最佳延展性和传统色泽；建筑装饰可选用金铜合金降低成本并提升耐磨性",
        },
    }
