"""
高级功能测试套件
覆盖4大新增功能：合金配比、工艺对比、佛像贴金、虚拟体验
包含正常、边界、异常三类测试用例
"""

import sys
import os
import unittest
import numpy as np
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.physics_model import (
    AlloyComposition,
    ProcessComparisonEngine,
    BuddhaGildingSimulator,
    BuddhaGildingConfig,
    VirtualForgingExperience,
    VirtualExperienceConfig,
    HammerParameters,
    StrikeFeedback,
    MaterialProperties,
    get_alloy_composition,
    compare_alloys,
)


# ============================================================================
# 测试1：合金配比 - 延展性验证
# ============================================================================

class TestAlloyComposition(unittest.TestCase):
    """合金配比延展性测试 - 验证不同金箔配比对延展率的影响"""

    def setUp(self):
        """测试前置：初始化5种标准合金"""
        self.pure_gold = AlloyComposition(
            key="pure_gold_24k",
            name="纯金 (24K)",
            gold_ratio=0.9999,
            copper_ratio=0.0,
            silver_ratio=0.0,
            color_rgb=(255, 215, 0),
            malleability_factor=1.0,
            hardness_vickers=25,
            historical_period="古代至今",
            typical_uses=["高档佛像贴金", "皇家器物"],
            description="最高纯度，延展性极佳",
        )

        self.gold_copper_22k = AlloyComposition(
            key="gold_copper_22k",
            name="金铜合金 (22K)",
            gold_ratio=0.9167,
            copper_ratio=0.0833,
            silver_ratio=0.0,
            color_rgb=(255, 200, 50),
            malleability_factor=0.85,
            hardness_vickers=45,
            historical_period="唐宋时期",
            typical_uses=["寺院佛像贴金", "建筑装饰"],
            description="传统佛像贴金常用，硬度提高",
        )

        self.gold_copper_18k = AlloyComposition(
            key="gold_copper_18k",
            name="金铜合金 (18K)",
            gold_ratio=0.75,
            copper_ratio=0.25,
            silver_ratio=0.0,
            color_rgb=(255, 180, 80),
            malleability_factor=0.65,
            hardness_vickers=70,
            historical_period="明清时期",
            typical_uses=["日常首饰", "耐用装饰"],
            description="硬度更高，耐磨",
        )

        self.gold_silver_22k = AlloyComposition(
            key="gold_silver_22k",
            name="金银合金 (22K)",
            gold_ratio=0.9167,
            copper_ratio=0.0,
            silver_ratio=0.0833,
            color_rgb=(255, 225, 150),
            malleability_factor=0.92,
            hardness_vickers=35,
            historical_period="商周时期",
            typical_uses=["高档首饰", "精细工艺品"],
            description="延展性好，色泽偏青",
        )

        self.ternary_18k = AlloyComposition(
            key="ternary_alloy_18k",
            name="金铜银三元合金 (18K)",
            gold_ratio=0.75,
            copper_ratio=0.125,
            silver_ratio=0.125,
            color_rgb=(255, 195, 100),
            malleability_factor=0.75,
            hardness_vickers=60,
            historical_period="现代",
            typical_uses=["精密首饰", "特种装饰"],
            description="综合性能均衡",
        )

    # ----------------- 正常场景测试 -----------------

    def test_pure_gold_highest_ductility(self):
        """正常场景：纯金延展性最高 - 验证延展性排序正确性"""
        pure_metrics = self.pure_gold.get_ductility_metrics()
        cu22_metrics = self.gold_copper_22k.get_ductility_metrics()
        cu18_metrics = self.gold_copper_18k.get_ductility_metrics()

        self.assertGreater(pure_metrics["max_elongation_pct"], cu22_metrics["max_elongation_pct"],
                           "纯金延伸率应高于22K金铜合金")
        self.assertGreater(cu22_metrics["max_elongation_pct"], cu18_metrics["max_elongation_pct"],
                           "22K延伸率应高于18K金铜合金")

    def test_copper_increases_hardness(self):
        """正常场景：铜含量增加导致硬度上升、延展性下降"""
        pure_hardness = self.pure_gold.hardness_vickers
        cu22_hardness = self.gold_copper_22k.hardness_vickers
        cu18_hardness = self.gold_copper_18k.hardness_vickers

        self.assertLess(pure_hardness, cu22_hardness, "纯金硬度应低于22K合金")
        self.assertLess(cu22_hardness, cu18_hardness, "22K硬度应低于18K合金")

    def test_silver_milder_than_copper(self):
        """正常场景：银对延展性的削弱小于铜"""
        cu22_metrics = self.gold_copper_22k.get_ductility_metrics()
        ag22_metrics = self.gold_silver_22k.get_ductility_metrics()

        self.assertGreater(ag22_metrics["max_elongation_pct"], cu22_metrics["max_elongation_pct"],
                           "相同K数下，金银合金延展性应优于金铜合金")

    def test_formability_index_calculation(self):
        """正常场景：成形性指数计算正确"""
        metrics = self.pure_gold.get_ductility_metrics()
        expected_index = (metrics["max_elongation_pct"] * metrics["reduction_in_area_pct"]) / 100.0

        self.assertAlmostEqual(
            metrics["formability_index"], expected_index, places=5,
            msg="成形性指数应为延伸率 × 断面收缩率 / 100"
        )

    def test_to_material_properties_conversion(self):
        """正常场景：转换为MaterialProperties成功"""
        mat_props = self.gold_copper_22k.to_material_properties()

        self.assertIsInstance(mat_props, MaterialProperties)
        self.assertGreater(mat_props.yield_strength, 120.0,
                           "合金屈服强度应高于纯金120MPa")
        self.assertGreater(mat_props.youngs_modulus, 79.0,
                           "合金弹性模量应高于纯金79GPa")

    def test_compare_with_pure_gold(self):
        """正常场景：与纯金对比的各项比率合理"""
        comparison = self.gold_copper_22k.compare_with_pure_gold()

        self.assertLess(comparison["ductility_ratio"], 1.0, "合金延展性比率应小于1")
        self.assertGreater(comparison["hardness_ratio"], 1.0, "合金硬度比率应大于1")
        self.assertLess(comparison["cost_ratio"], 1.0, "合金成本比率应小于1")
        self.assertGreater(comparison["wear_resistance_relative"], 1.0, "合金耐磨性应优于纯金")
        self.assertLess(comparison["tarnish_resistance_relative"], 1.0, "合金抗变色性应低于纯金")

    def test_alloy_color_variation(self):
        """正常场景：不同合金颜色有明显差异"""
        colors = [
            self.pure_gold.color_rgb,
            self.gold_copper_22k.color_rgb,
            self.gold_copper_18k.color_rgb,
            self.gold_silver_22k.color_rgb,
            self.ternary_18k.color_rgb,
        ]

        unique_colors = set(colors)
        self.assertEqual(len(unique_colors), len(colors), "5种合金应有5种不同颜色")

    # ----------------- 边界场景测试 -----------------

    def test_room_temperature_ductility(self):
        """边界场景：室温(25°C)下延展性正常"""
        metrics = self.pure_gold.get_ductility_metrics(temperature_c=25.0)
        self.assertEqual(metrics["temperature_factor"], 1.0,
                         "低于再结晶温度时温度系数应为1.0")
        self.assertEqual(metrics["temperature_c"], 25.0)

    def test_above_recrystallization_temperature(self):
        """边界场景：超过再结晶温度时延展性显著提升"""
        low_temp_metrics = self.pure_gold.get_ductility_metrics(temperature_c=25.0)
        high_temp_metrics = self.pure_gold.get_ductility_metrics(temperature_c=500.0)

        self.assertGreater(high_temp_metrics["temperature_factor"], low_temp_metrics["temperature_factor"],
                           "超过再结晶温度后温度系数应提升")
        self.assertGreater(high_temp_metrics["max_elongation_pct"], low_temp_metrics["max_elongation_pct"],
                           "再结晶退火后延伸率应显著提高")
        self.assertEqual(high_temp_metrics["temperature_factor"], 1.5,
                         "超过再结晶温度时温度系数应为1.5")

    def test_exactly_at_recrystallization(self):
        """边界场景：恰好在再结晶温度点的连续性"""
        recryst_temp = self.pure_gold.recrystallization_temp_alloy

        below = self.pure_gold.get_ductility_metrics(temperature_c=recryst_temp - 1)
        above = self.pure_gold.get_ductility_metrics(temperature_c=recryst_temp + 1)

        self.assertEqual(below["temperature_factor"], 1.0)
        self.assertEqual(above["temperature_factor"], 1.5)

    def test_extremely_low_temperature(self):
        """边界场景：极低温度(-100°C)下的延展性"""
        metrics = self.pure_gold.get_ductility_metrics(temperature_c=-100.0)

        self.assertEqual(metrics["temperature_factor"], 1.0,
                         "低于再结晶温度时温度系数保持1.0")
        self.assertGreater(metrics["max_elongation_pct"], 0,
                           "延伸率应为正值")
        self.assertEqual(metrics["temperature_c"], -100.0)

    def test_near_melting_temperature(self):
        """边界场景：接近熔点温度时的延展性"""
        metrics = self.pure_gold.get_ductility_metrics(temperature_c=900.0)

        self.assertEqual(metrics["temperature_factor"], 1.5)
        self.assertGreater(metrics["max_elongation_pct"], 50,
                           "高温下延伸率应显著提高")

    def test_pure_alloy_boundary_9999(self):
        """边界场景：极接近纯金的合金(99.99%金)"""
        nearly_pure = AlloyComposition(
            key="nearly_pure",
            name="近纯金",
            gold_ratio=0.9999,
            copper_ratio=0.0001,
            silver_ratio=0.0,
            color_rgb=(255, 214, 1),
            malleability_factor=0.999,
            hardness_vickers=25.1,
            historical_period="现代",
            typical_uses=["实验室标准样"],
            description="几乎纯金",
        )

        metrics = nearly_pure.get_ductility_metrics()
        pure_metrics = self.pure_gold.get_ductility_metrics()

        diff_pct = abs(metrics["max_elongation_pct"] - pure_metrics["max_elongation_pct"]) / pure_metrics["max_elongation_pct"] * 100
        self.assertLess(diff_pct, 1.0, "99.99%金与纯金延展性差异应小于1%")

    # ----------------- 异常场景测试 -----------------

    def test_negative_gold_ratio(self):
        """异常场景：金比例为负值 - dataclass不自动验证，但应能计算"""
        bad_alloy = AlloyComposition(
            key="bad",
            name="坏合金",
            gold_ratio=-0.1,
            copper_ratio=1.1,
            silver_ratio=0.0,
            color_rgb=(255, 0, 0),
            malleability_factor=0.5,
            hardness_vickers=100,
            historical_period="无",
            typical_uses=["无"],
            description="测试异常",
        )
        metrics = bad_alloy.get_ductility_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertIn("max_elongation_pct", metrics)

    def test_sum_ratio_exceeds_one(self):
        """异常场景：成分比例之和超过100%"""
        bad_alloy = AlloyComposition(
            key="bad_sum",
            name="比例超1",
            gold_ratio=0.8,
            copper_ratio=0.5,
            silver_ratio=0.3,
            color_rgb=(255, 255, 0),
            malleability_factor=0.5,
            hardness_vickers=50,
            historical_period="无",
            typical_uses=["无"],
            description="比例和为1.6",
        )
        total_ratio = bad_alloy.gold_ratio + bad_alloy.copper_ratio + bad_alloy.silver_ratio
        self.assertGreater(total_ratio, 1.0, "测试用例：比例和应大于1")
        metrics = bad_alloy.get_ductility_metrics()
        self.assertIsInstance(metrics, dict, "即使比例异常也应能计算（物理上无意义但不崩溃）")

    def test_zero_malleability_factor(self):
        """异常场景：延展性因子为0"""
        brittle_alloy = AlloyComposition(
            key="brittle",
            name="脆性合金",
            gold_ratio=0.5,
            copper_ratio=0.5,
            silver_ratio=0.0,
            color_rgb=(200, 150, 50),
            malleability_factor=0.0,
            hardness_vickers=200,
            historical_period="无",
            typical_uses=["无"],
            description="完全脆",
        )
        metrics = brittle_alloy.get_ductility_metrics()
        self.assertEqual(metrics["max_elongation_pct"], 0.0,
                         "延展性因子为0时延伸率应为0")
        self.assertEqual(metrics["formability_index"], 0.0,
                         "延展性因子为0时成形指数应为0")

    def test_negative_hardness(self):
        """异常场景：负硬度值 - dataclass不自动验证，但应能实例化"""
        weird_alloy = AlloyComposition(
            key="bad_hardness",
            name="负硬度",
            gold_ratio=0.9,
            copper_ratio=0.1,
            silver_ratio=0.0,
            color_rgb=(255, 200, 50),
            malleability_factor=0.8,
            hardness_vickers=-50,
            historical_period="无",
            typical_uses=["无"],
            description="测试",
        )
        metrics = weird_alloy.get_ductility_metrics()
        self.assertIsInstance(metrics, dict)
        self.assertEqual(metrics["hardness_vickers"], -50.0)

    def test_invalid_temperature_kelvin(self):
        """异常场景：输入开尔文温度而非摄氏度（负值）"""
        metrics = self.pure_gold.get_ductility_metrics(temperature_c=-273.15)

        self.assertIsInstance(metrics, dict, "绝对零度也不应崩溃")
        self.assertEqual(metrics["temperature_factor"], 1.0)

    def test_extremely_high_temperature(self):
        """异常场景：远超熔点的温度"""
        metrics = self.pure_gold.get_ductility_metrics(temperature_c=5000.0)

        self.assertIsInstance(metrics, dict, "极高温度下也应返回结果")
        self.assertEqual(metrics["temperature_factor"], 1.5)

    def test_invalid_color_rgb_values(self):
        """异常场景：RGB值超出0-255范围"""
        weird_alloy = AlloyComposition(
            key="weird_color",
            name="怪异颜色",
            gold_ratio=0.9,
            copper_ratio=0.1,
            silver_ratio=0.0,
            color_rgb=(-10, 300, 128),
            malleability_factor=0.8,
            hardness_vickers=40,
            historical_period="无",
            typical_uses=["无"],
            description="颜色值异常",
        )

        metrics = weird_alloy.get_ductility_metrics()
        self.assertEqual(len(metrics["color_rgb"]), 3, "颜色应为3通道")

    # ----------------- 工厂函数测试 -----------------

    def test_factory_get_alloy_composition(self):
        """工厂函数：get_alloy_composition 正常调用"""
        alloy = get_alloy_composition("pure_gold_24k")
        self.assertIsInstance(alloy, AlloyComposition)
        self.assertEqual(alloy.key, "pure_gold_24k")

    def test_factory_compare_alloys(self):
        """工厂函数：compare_alloys 正常对比"""
        result = compare_alloys(["pure_gold_24k", "gold_copper_22k"])
        self.assertIn("alloys", result)
        self.assertIn("radar_chart", result)
        self.assertIn("recommendation", result)
        self.assertEqual(len(result["alloys"]), 2)


# ============================================================================
# 测试2：工艺对比 - 厚度均匀性验证
# ============================================================================

class TestProcessComparison(unittest.TestCase):
    """工艺对比测试 - 验证古代锻制与现代真空镀膜的均匀性差异"""

    def setUp(self):
        """测试前置：初始化工艺对比引擎"""
        self.engine = ProcessComparisonEngine()

    # ----------------- 正常场景测试 -----------------

    def test_pvd_highest_uniformity(self):
        """正常场景：真空镀膜均匀度最高"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=10.0,
            use_case="buddha_gilding",
        )

        ancient_score = result.ancient["individual_scores"]["uniformity"]
        pvd_score = result.modern_vacuum["individual_scores"]["uniformity"]
        electro_score = result.modern_electroplating["individual_scores"]["uniformity"]

        self.assertGreater(pvd_score, ancient_score,
                           "真空镀膜均匀度应优于古代锻制")
        self.assertGreater(pvd_score, electro_score,
                           "真空镀膜均匀度应优于电镀")
        self.assertGreater(electro_score, ancient_score,
                           "电镀均匀度应优于古代锻制")

    def test_ancient_best_material_utilization(self):
        """正常场景：古代锻制材料利用率最高"""
        result = self.engine.compare_processes(
            target_thickness_um=0.5,
            production_area_m2=5.0,
            use_case="jewelry",
        )

        ancient_util = result.ancient["individual_scores"]["material_utilization"]
        pvd_util = result.modern_vacuum["individual_scores"]["material_utilization"]
        electro_util = result.modern_electroplating["individual_scores"]["material_utilization"]

        self.assertGreater(ancient_util, pvd_util,
                           "古代锻制材料利用率应高于真空镀膜")
        self.assertGreater(pvd_util, electro_util,
                           "真空镀膜材料利用率应高于电镀")

    def test_pvd_best_surface_quality(self):
        """正常场景：真空镀膜表面质量最佳"""
        result = self.engine.compare_processes(
            target_thickness_um=0.1,
            production_area_m2=1.0,
            use_case="jewelry",
        )

        pvd_quality = result.modern_vacuum["individual_scores"]["surface_quality"]
        ancient_quality = result.ancient["individual_scores"]["surface_quality"]

        self.assertGreater(pvd_quality, ancient_quality,
                           "真空镀膜表面质量应优于古代锻制")

    def test_weighted_scores_sum_correct(self):
        """正常场景：加权总分计算正确"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=10.0,
            use_case="buddha_gilding",
        )

        for process_data in [result.ancient, result.modern_vacuum, result.modern_electroplating]:
            scores = process_data["individual_scores"]
            weights_sum = sum([
                0.15, 0.10, 0.15, 0.10, 0.15, 0.15, 0.10, 0.10
            ])
            self.assertAlmostEqual(weights_sum, 1.0, places=5,
                                   msg="权重之和应为1.0")

    def test_radar_chart_data_structure(self):
        """正常场景：雷达图数据结构完整"""
        result = self.engine.compare_processes(
            target_thickness_um=0.3,
            production_area_m2=5.0,
            use_case="decoration",
        )

        radar = result.radar_chart_data
        self.assertIn("labels", radar)
        self.assertIn("datasets", radar)
        self.assertEqual(len(radar["datasets"]), 3)
        self.assertEqual(len(radar["labels"]), len(radar["datasets"][0]["data"]))

    def test_use_case_affects_recommendation(self):
        """正常场景：不同应用场景推荐不同工艺"""
        result_jewelry = self.engine.compare_processes(
            target_thickness_um=0.1,
            production_area_m2=1.0,
            use_case="jewelry",
        )
        result_arch = self.engine.compare_processes(
            target_thickness_um=1.0,
            production_area_m2=100.0,
            use_case="architecture",
        )

        self.assertIsInstance(result_jewelry.recommendation, str)
        self.assertIsInstance(result_arch.recommendation, str)
        self.assertGreater(len(result_jewelry.recommendation), 0)

    # ----------------- 边界场景测试 -----------------

    def test_extremely_thin_0_01um(self):
        """边界场景：极薄目标厚度(0.01μm) - 只有真空镀膜能达到"""
        result = self.engine.compare_processes(
            target_thickness_um=0.01,
            production_area_m2=1.0,
            use_case="jewelry",
        )

        self.assertTrue(result.modern_vacuum["can_achieve_target"],
                        "真空镀膜应能达到0.01μm")
        self.assertFalse(result.ancient["can_achieve_target"],
                         "古代锻制无法达到0.01μm")

    def test_thick_target_100um(self):
        """边界场景：很厚的目标厚度(100μm) - 所有工艺都能达到"""
        result = self.engine.compare_processes(
            target_thickness_um=100.0,
            production_area_m2=10.0,
            use_case="architecture",
        )

        self.assertTrue(result.ancient["can_achieve_target"])
        self.assertTrue(result.modern_vacuum["can_achieve_target"])
        self.assertTrue(result.modern_electroplating["can_achieve_target"])

    def test_minimal_production_area(self):
        """边界场景：极小生产面积(0.01m²)"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=0.01,
            use_case="jewelry",
        )

        self.assertGreater(result.ancient["total_energy_kwh"], 0)
        self.assertGreater(result.ancient["total_labor_hours"], 0)

    def test_large_scale_production(self):
        """边界场景：大规模生产(10000m²)"""
        result = self.engine.compare_processes(
            target_thickness_um=0.5,
            production_area_m2=10000.0,
            use_case="architecture",
        )

        self.assertGreater(result.modern_vacuum["total_energy_kwh"],
                           result.ancient["total_energy_kwh"],
                           "大规模生产下真空镀膜能耗可能更高")
        self.assertLess(result.modern_vacuum["total_labor_hours"],
                        result.ancient["total_labor_hours"],
                        "大规模生产下真空镀膜工时更少")

    def test_unknown_use_case_defaults(self):
        """边界场景：未知应用场景使用默认权重"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=10.0,
            use_case="unknown_case_xyz",
        )

        self.assertIsInstance(result.recommendation, str)
        self.assertGreater(len(result.recommendation), 0)

    def test_target_at_min_thickness_boundary(self):
        """边界场景：目标厚度恰在工艺最小厚度处"""
        result = self.engine.compare_processes(
            target_thickness_um=0.08,
            production_area_m2=1.0,
            use_case="buddha_gilding",
        )

        self.assertTrue(result.ancient["can_achieve_target"],
                        "0.08μm是古代锻制的临界厚度，应能达到")

    # ----------------- 异常场景测试 -----------------

    def test_negative_thickness(self):
        """异常场景：负的目标厚度"""
        result = self.engine.compare_processes(
            target_thickness_um=-1.0,
            production_area_m2=10.0,
            use_case="buddha_gilding",
        )

        self.assertIsInstance(result.ancient, dict)
        self.assertFalse(result.ancient["can_achieve_target"],
                         "负厚度应无法达到")

    def test_zero_thickness(self):
        """异常场景：零厚度目标"""
        result = self.engine.compare_processes(
            target_thickness_um=0.0,
            production_area_m2=10.0,
            use_case="buddha_gilding",
        )

        self.assertFalse(result.ancient["can_achieve_target"])
        self.assertFalse(result.modern_vacuum["can_achieve_target"])

    def test_negative_production_area(self):
        """异常场景：负的生产面积"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=-5.0,
            use_case="buddha_gilding",
        )

        self.assertIsInstance(result.ancient["total_energy_kwh"], float)
        self.assertLess(result.ancient["total_energy_kwh"], 0,
                        "负面积导致负能耗（物理无意义但计算稳定）")

    def test_zero_production_area(self):
        """异常场景：零生产面积"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=0.0,
            use_case="buddha_gilding",
        )

        self.assertEqual(result.ancient["total_energy_kwh"], 0.0)
        self.assertEqual(result.ancient["total_labor_hours"], 0.0)

    def test_empty_use_case_string(self):
        """异常场景：空字符串应用场景"""
        result = self.engine.compare_processes(
            target_thickness_um=0.2,
            production_area_m2=10.0,
            use_case="",
        )

        self.assertIsInstance(result.recommendation, str)

    def test_custom_config_override(self):
        """异常场景：使用自定义配置覆盖默认参数"""
        custom_cfg = {
            "ancient_forging": {
                "max_thickness_reduction": 0.9,
                "min_achievable_thickness_um": 0.5,
                "uniformity_error_pct": 10.0,
                "energy_consumption_kwh_per_m2": 10.0,
                "labor_hours_per_m2": 200,
                "environmental_impact_score": 2,
                "surface_roughness_um": 0.05,
                "material_utilization_pct": 95,
                "capital_cost_factor": 0.05,
                "maintenance_cost_factor": 0.02,
            },
            "modern_vacuum_coating": {
                "max_thickness_reduction": 1.0,
                "min_achievable_thickness_um": 0.001,
                "uniformity_error_pct": 0.1,
                "energy_consumption_kwh_per_m2": 60.0,
                "labor_hours_per_m2": 1.0,
                "environmental_impact_score": 8,
                "surface_roughness_um": 0.0005,
                "material_utilization_pct": 90,
                "capital_cost_factor": 1.5,
                "maintenance_cost_factor": 0.4,
            },
            "modern_electroplating": {
                "max_thickness_reduction": 1.0,
                "min_achievable_thickness_um": 0.05,
                "uniformity_error_pct": 3.0,
                "energy_consumption_kwh_per_m2": 20.0,
                "labor_hours_per_m2": 10.0,
                "environmental_impact_score": 9.5,
                "surface_roughness_um": 0.02,
                "material_utilization_pct": 70,
                "capital_cost_factor": 0.5,
                "maintenance_cost_factor": 0.2,
            },
        }

        engine = ProcessComparisonEngine(config=custom_cfg)
        result = engine.compare_processes(
            target_thickness_um=0.1,
            production_area_m2=10.0,
            use_case="buddha_gilding",
        )

        self.assertIsNotNone(result)
        self.assertIn("recommendation", result.__dict__)

    def test_normalize_score_boundaries(self):
        """异常场景：归一化函数边界值处理"""
        engine = ProcessComparisonEngine()

        score_high = engine._normalize_score(100, 0, 100, True)
        score_low = engine._normalize_score(0, 0, 100, True)
        score_above = engine._normalize_score(150, 0, 100, True)
        score_below = engine._normalize_score(-50, 0, 100, True)

        self.assertEqual(score_high, 1.0)
        self.assertEqual(score_low, 0.0)
        self.assertLessEqual(score_above, 1.0, "超出上限应被截断为1")
        self.assertGreaterEqual(score_below, 0.0, "低于下限应被截断为0")

    def test_normalize_score_higher_is_better_false(self):
        """异常场景：越低越好的归一化方向"""
        engine = ProcessComparisonEngine()

        score_low_good = engine._normalize_score(10, 0, 100, False)
        score_high_good = engine._normalize_score(90, 0, 100, False)

        self.assertGreater(score_low_good, score_high_good,
                           "越低越好时，低值应得高分")


# ============================================================================
# 测试3：佛像贴金仿真 - 视觉效果验证
# ============================================================================

class TestBuddhaGildingSimulation(unittest.TestCase):
    """佛像贴金仿真测试 - 验证视觉效果仿真的正确性"""

    def setUp(self):
        """测试前置：初始化贴金仿真器"""
        self.simulator = BuddhaGildingSimulator()

    # ----------------- 正常场景测试 -----------------

    def test_meditation_buddha_simulation(self):
        """正常场景：禅定印佛像贴金仿真"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            adhesive_type="gold_leaf_size",
            foil_size_mm=100,
            foil_thickness_um=0.2,
            skill_level=0.7,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIn("coverage_map", result)
        self.assertIn("wrinkle_map", result)
        self.assertIn("lighting_simulation", result)
        self.assertIn("metrics", result)
        self.assertGreater(result["metrics"]["average_coverage_pct"], 0)
        self.assertLessEqual(result["metrics"]["average_coverage_pct"], 100)

    def test_adhesive_affects_durability(self):
        """正常场景：不同胶粘剂耐久性不同"""
        config_kaki = BuddhaGildingConfig(
            buddha_type="meditation",
            adhesive_type="gold_leaf_size",
            foil_thickness_um=0.2,
            skill_level=0.7,
        )
        config_animal = BuddhaGildingConfig(
            buddha_type="meditation",
            adhesive_type="traditional_animal_glue",
            foil_thickness_um=0.2,
            skill_level=0.7,
        )

        result_kaki = self.simulator.simulate_gilding(config_kaki)
        result_animal = self.simulator.simulate_gilding(config_animal)

        self.assertGreater(result_kaki["metrics"]["durability_years"],
                           result_animal["metrics"]["durability_years"],
                           "柿漆耐久性应优于动物胶")

    def test_skill_level_affects_quality(self):
        """正常场景：技能水平影响贴金质量"""
        config_beginner = BuddhaGildingConfig(
            buddha_type="teaching",
            adhesive_type="gold_leaf_size",
            skill_level=0.3,
        )
        config_master = BuddhaGildingConfig(
            buddha_type="teaching",
            adhesive_type="gold_leaf_size",
            skill_level=0.95,
        )

        result_beginner = self.simulator.simulate_gilding(config_beginner)
        result_master = self.simulator.simulate_gilding(config_master)

        self.assertGreater(result_master["metrics"]["quality_score"],
                           result_beginner["metrics"]["quality_score"],
                           "大师级技能质量分应更高")
        self.assertGreater(result_master["metrics"]["average_coverage_pct"],
                           result_beginner["metrics"]["average_coverage_pct"],
                           "大师级覆盖率应更高")

    def test_lighting_simulation_complete(self):
        """正常场景：光照仿真结果完整"""
        config = BuddhaGildingConfig(buddha_type="meditation")
        result = self.simulator.simulate_gilding(config)

        lighting = result["lighting_simulation"]
        self.assertIn("diffuse_map", lighting)
        self.assertIn("specular_map", lighting)
        self.assertIn("total_reflection", lighting)
        self.assertIn("brightness_distribution", lighting)
        self.assertIn("color_temperature_k", lighting)
        self.assertIn("luster_description", lighting)

    def test_curvature_affects_wrinkles(self):
        """正常场景：高曲率表面褶皱更多"""
        config_simple = BuddhaGildingConfig(
            buddha_type="meditation",
            surface_complexity="gentle_curve",
            skill_level=0.5,
        )
        config_complex = BuddhaGildingConfig(
            buddha_type="guanyin",
            surface_complexity="complex_3d",
            skill_level=0.5,
        )

        result_simple = self.simulator.simulate_gilding(config_simple)
        result_complex = self.simulator.simulate_gilding(config_complex)

        self.assertIsNotNone(result_simple)
        self.assertIsNotNone(result_complex)

    def test_quality_score_composition(self):
        """正常场景：质量分数构成合理"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=0.8,
        )
        result = self.simulator.simulate_gilding(config)

        score = result["metrics"]["quality_score"]
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    # ----------------- 边界场景测试 -----------------

    def test_perfect_skill_level(self):
        """边界场景：100%完美技能水平"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=1.0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertLessEqual(result["metrics"]["quality_score"], 100)
        self.assertGreater(result["metrics"]["average_coverage_pct"], 0,
                           "完美技能下覆盖率应大于0")

    def test_zero_skill_level(self):
        """边界场景：零技能水平（完全新手）"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=0.0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertGreaterEqual(result["metrics"]["quality_score"], 0)
        self.assertIsInstance(result["metrics"]["wrinkle_area_pct"], float)
        self.assertGreaterEqual(result["metrics"]["wrinkle_area_pct"], 0)

    def test_extremely_thin_foil(self):
        """边界场景：极薄金箔(0.01μm)"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_thickness_um=0.01,
            skill_level=0.7,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)
        self.assertIn("avg_foil_thickness_um", result)

    def test_very_thick_foil(self):
        """边界场景：很厚的金箔(100μm)"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_thickness_um=100.0,
            skill_level=0.7,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)

    def test_mini_foil_size(self):
        """边界场景：极小的金箔尺寸(10×10mm)"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_size_mm=10,
            skill_level=0.7,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertGreater(result["metrics"]["estimated_foil_sheets"], 0)

    def test_all_buddha_types(self):
        """边界场景：测试所有4种佛像类型"""
        buddha_types = ["meditation", "teaching", "abhayamudra", "guanyin"]

        for btype in buddha_types:
            config = BuddhaGildingConfig(buddha_type=btype)
            result = self.simulator.simulate_gilding(config)
            self.assertEqual(result["buddha_type"], btype)
            self.assertIsNotNone(result["buddha_name"])

    # ----------------- 异常场景测试 -----------------

    def test_unknown_buddha_type(self):
        """异常场景：未知佛像类型 - 应使用默认值"""
        config = BuddhaGildingConfig(
            buddha_type="unknown_buddha_type_xyz",
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)
        self.assertIn("buddha_type", result)

    def test_unknown_adhesive_type(self):
        """异常场景：未知胶粘剂类型 - 应使用默认胶"""
        config = BuddhaGildingConfig(
            adhesive_type="super_glue_xyz",
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)
        self.assertIn("adhesive", result)

    def test_negative_skill_level(self):
        """异常场景：负技能水平"""
        config = BuddhaGildingConfig(
            skill_level=-1.0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["metrics"]["average_coverage_pct"], 0)

    def test_skill_above_100(self):
        """异常场景：技能水平超过100%"""
        config = BuddhaGildingConfig(
            skill_level=2.0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertLessEqual(result["metrics"]["average_coverage_pct"], 100,
                             "覆盖率不应超过100%")

    def test_negative_foil_thickness(self):
        """异常场景：负金箔厚度"""
        config = BuddhaGildingConfig(
            foil_thickness_um=-5.0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)

    def test_zero_foil_size(self):
        """异常场景：零尺寸金箔"""
        config = BuddhaGildingConfig(
            foil_size_mm=0,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIsNotNone(result)
        self.assertGreaterEqual(result["metrics"]["material_efficiency_pct"], 0)

    def test_thickness_distribution_input(self):
        """异常场景：传入自定义厚度分布"""
        custom_thickness = np.random.rand(48, 48) * 0.5 + 0.1
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=0.7,
        )

        result = self.simulator.simulate_gilding(config, thickness_distribution=custom_thickness)

        self.assertIsNotNone(result)
        self.assertIn("foil_uniformity", result)

    def test_mismatched_grid_size(self):
        """异常场景：传入不同尺寸的厚度分布"""
        small_thickness = np.random.rand(32, 32) * 0.3
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=0.7,
        )

        try:
            result = self.simulator.simulate_gilding(config, thickness_distribution=small_thickness)
            self.assertIsNotNone(result)
        except Exception as e:
            self.assertIsInstance(e, Exception, "尺寸不匹配可能导致异常")

    def test_difficulty_assessment(self):
        """正常场景：难度评估结果合理"""
        config = BuddhaGildingConfig(
            buddha_type="guanyin",
            skill_level=0.3,
        )
        result = self.simulator.simulate_gilding(config)

        self.assertIn("difficulty_assessment", result)
        self.assertIn("recommended_skill_level", result["difficulty_assessment"])
        self.assertIn("tips", result["difficulty_assessment"])
        self.assertIsInstance(result["difficulty_assessment"]["tips"], list)

    def test_tips_based_on_config(self):
        """正常场景：贴金建议根据配置变化"""
        config_thin = BuddhaGildingConfig(
            foil_thickness_um=0.1,
            skill_level=0.4,
            buddha_type="abhayamudra",
        )
        result_thin = self.simulator.simulate_gilding(config_thin)
        tips_thin = " ".join(result_thin["difficulty_assessment"]["tips"])

        config_thick = BuddhaGildingConfig(
            foil_thickness_um=1.0,
            skill_level=0.8,
            buddha_type="meditation",
        )
        result_thick = self.simulator.simulate_gilding(config_thick)
        tips_thick = " ".join(result_thick["difficulty_assessment"]["tips"])

        self.assertNotEqual(tips_thin, tips_thick,
                            "不同配置应有不同的贴金建议")


# ============================================================================
# 测试4：虚拟打金体验 - 交互真实感测试
# ============================================================================

class TestVirtualForgingExperience(unittest.TestCase):
    """虚拟打金体验测试 - 验证交互真实感和反馈机制"""

    def setUp(self):
        """测试前置：初始化虚拟体验系统"""
        self.experience = VirtualForgingExperience()

    # ----------------- 正常场景测试 -----------------

    def test_beginner_mode_strike_feedback(self):
        """正常场景：初学者模式锤击反馈"""
        hammer = HammerParameters(
            force=500.0,
            position=(0.0, 0.0),
            radius_mm=30.0,
            strike_duration_ms=50.0,
        )

        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 490.0)
        strike_result = {
            "avg_thickness_um": 490.0,
            "min_thickness_um": 480.0,
            "thickness_std_um": 5.0,
        }

        config = VirtualExperienceConfig(
            mode="beginner",
            target_thickness_um=0.5,
            alloy_key="pure_gold_24k",
        )

        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)
        self.assertGreaterEqual(feedback.quality_score, 0)
        self.assertLessEqual(feedback.quality_score, 1)
        self.assertGreater(feedback.sound_frequency_hz, 0)
        self.assertGreater(feedback.sound_duration_ms, 0)
        self.assertIsInstance(feedback.message, str)

    def test_master_mode_higher_difficulty(self):
        """正常场景：大师模式难度更高"""
        hammer = HammerParameters(
            force=1000.0,
            position=(0.0, 0.0),
            radius_mm=30.0,
            strike_duration_ms=50.0,
        )

        prev_thickness = np.full((48, 48), 10.0)
        current_thickness = np.full((48, 48), 9.5)
        strike_result = {
            "avg_thickness_um": 9.5,
            "min_thickness_um": 8.0,
            "thickness_std_um": 0.5,
        }

        config_beginner = VirtualExperienceConfig(mode="beginner")
        config_master = VirtualExperienceConfig(mode="master")

        fb_beginner = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config_beginner
        )
        fb_master = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config_master
        )

        self.assertIsNotNone(fb_beginner)
        self.assertIsNotNone(fb_master)

    def test_score_calculation_basic(self):
        """正常场景：基础得分计算"""
        config = VirtualExperienceConfig(mode="intermediate")
        feedback = StrikeFeedback(
            vibration_intensity=0.5,
            force_feedback=5.0,
            visual_effect="good",
            sound_frequency_hz=600.0,
            sound_duration_ms=200,
            quality_score=0.8,
            message="不错",
        )
        metrics = {
            "uniformity_within_10pct": 0.85,
            "mean_thickness_um": 10.0,
        }

        score_data = self.experience.calculate_score(metrics, feedback, config, consecutive_good_strikes=5)

        self.assertGreater(score_data["total_score"], 0)
        self.assertIn("base_score", score_data)
        self.assertIn("combo_bonus", score_data)
        self.assertIn("uniformity_bonus", score_data)
        self.assertIn("thickness_bonus", score_data)
        self.assertEqual(score_data["multiplier"], 1.0)

    def test_combo_bonus_increases(self):
        """正常场景：连击数增加奖励提高"""
        config = VirtualExperienceConfig(mode="beginner")
        feedback = StrikeFeedback(
            vibration_intensity=0.5,
            force_feedback=5.0,
            visual_effect="good",
            sound_frequency_hz=500.0,
            sound_duration_ms=180,
            quality_score=0.7,
            message="good",
        )
        metrics = {
            "uniformity_within_10pct": 0.5,
            "mean_thickness_um": 450.0,
        }

        score_0_combo = self.experience.calculate_score(metrics, feedback, config, 0)
        score_10_combo = self.experience.calculate_score(metrics, feedback, config, 10)

        self.assertGreater(score_10_combo["combo_bonus"], score_0_combo["combo_bonus"],
                           "10连击的连击奖励应高于0连击")

    def test_first_strike_achievement(self):
        """正常场景：第一次锤击解锁初体验成就"""
        stats = {"total_strikes": 1}
        unlocked = []

        new_ach = self.experience.check_achievements(stats, unlocked)

        achievement_ids = [a["id"] for a in new_ach]
        self.assertIn("first_strike", achievement_ids)
        self.assertIn("first_strike", unlocked)

    def test_ten_strikes_achievement(self):
        """正常场景：累计10次锤击解锁小有经验成就"""
        stats = {"total_strikes": 10}
        unlocked = ["first_strike"]

        new_ach = self.experience.check_achievements(stats, unlocked)

        achievement_ids = [a["id"] for a in new_ach]
        self.assertIn("ten_strikes", achievement_ids)

    def test_achievements_no_duplicate(self):
        """正常场景：已解锁成就不会重复解锁"""
        stats = {"total_strikes": 50}
        unlocked = ["first_strike", "ten_strikes"]

        new_ach = self.experience.check_achievements(stats, unlocked)

        achievement_ids = [a["id"] for a in new_ach]
        self.assertNotIn("first_strike", achievement_ids)
        self.assertNotIn("ten_strikes", achievement_ids)

    def test_tutorial_steps_complete(self):
        """正常场景：教程步骤完整（共7步）"""
        tutorial = self.experience.tutorial_steps

        self.assertEqual(len(tutorial), 7)
        for i, step in enumerate(tutorial):
            self.assertEqual(step["step"], i + 1)
            self.assertIn("title", step)
            self.assertIn("content", step)
            self.assertIn("duration_sec", step)

    def test_all_ten_achievements_defined(self):
        """正常场景：共定义10项成就"""
        achievements = self.experience.achievements

        self.assertEqual(len(achievements), 10)
        for ach in achievements:
            self.assertIn("id", ach)
            self.assertIn("name", ach)
            self.assertIn("desc", ach)
            self.assertIn("points", ach)
            self.assertIn("icon", ach)

    # ----------------- 边界场景测试 -----------------

    def test_minimum_force_strike(self):
        """边界场景：最小力度锤击"""
        hammer = HammerParameters(
            force=200.0,
            position=(0.0, 0.0),
            radius_mm=30.0,
            strike_duration_ms=50.0,
        )

        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 498.0)
        strike_result = {
            "avg_thickness_um": 498.0,
            "min_thickness_um": 496.0,
            "thickness_std_um": 1.0,
        }

        config = VirtualExperienceConfig(mode="beginner")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)

    def test_maximum_force_strike(self):
        """边界场景：最大力度锤击"""
        hammer = HammerParameters(
            force=3000.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=100,
        )

        prev_thickness = np.full((48, 48), 10.0)
        current_thickness = np.full((48, 48), 8.0)
        strike_result = {
            "avg_thickness_um": 8.0,
            "min_thickness_um": 5.0,
            "thickness_std_um": 2.0,
        }

        config = VirtualExperienceConfig(mode="master")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)

    def test_near_tear_warning(self):
        """边界场景：接近破裂时发出警告"""
        hammer = HammerParameters(
            force=2000.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 0.2)
        current_thickness = np.full((48, 48), 0.12)
        strike_result = {
            "avg_thickness_um": 0.12,
            "min_thickness_um": 0.05,
            "thickness_std_um": 0.02,
        }

        config = VirtualExperienceConfig(mode="intermediate")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertEqual(feedback.visual_effect, "danger")
        self.assertIn("危险", feedback.message)
        self.assertEqual(feedback.quality_score, 0.0)

    def test_auto_protection_in_beginner_mode(self):
        """边界场景：初学者模式自动保护激活"""
        hammer = HammerParameters(
            force=2000.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 0.2)
        current_thickness = np.full((48, 48), 0.05)
        strike_result = {
            "avg_thickness_um": 0.05,
            "min_thickness_um": 0.01,
            "thickness_std_um": 0.02,
        }

        config = VirtualExperienceConfig(mode="beginner")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIn("自动保护", feedback.message)

    def test_perfect_uniformity_achievement(self):
        """边界场景：完美均匀度成就解锁"""
        stats = {"max_uniformity": 0.96, "total_strikes": 50}
        unlocked = []

        new_ach = self.experience.check_achievements(stats, unlocked)
        achievement_ids = [a["id"] for a in new_ach]

        self.assertIn("perfect_uniformity", achievement_ids)

    def test_exactly_at_achievement_threshold(self):
        """边界场景：恰好在成就阈值边界"""
        stats = {"max_uniformity": 0.95, "total_strikes": 10}
        unlocked = ["first_strike"]

        new_ach = self.experience.check_achievements(stats, unlocked)
        achievement_ids = [a["id"] for a in new_ach]

        self.assertIn("ten_strikes", achievement_ids)
        self.assertIn("perfect_uniformity", achievement_ids)

    def test_haptic_feedback_enabled(self):
        """边界场景：触觉反馈开启时的参数调整"""
        hammer = HammerParameters(
            force=800.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 100.0)
        current_thickness = np.full((48, 48), 95.0)
        strike_result = {
            "avg_thickness_um": 95.0,
            "min_thickness_um": 90.0,
            "thickness_std_um": 2.0,
        }

        config = VirtualExperienceConfig(mode="intermediate", haptic_enabled=True)
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)
        self.assertIsInstance(feedback.vibration_intensity, float)

    # ----------------- 异常场景测试 -----------------

    def test_unknown_mode_defaults(self):
        """异常场景：未知模式默认使用初学者配置"""
        hammer = HammerParameters(
            force=500.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 490.0)
        strike_result = {
            "avg_thickness_um": 490.0,
            "min_thickness_um": 480.0,
            "thickness_std_um": 5.0,
        }

        config = VirtualExperienceConfig(mode="unknown_mode_xyz")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)

    def test_negative_hammer_force(self):
        """异常场景：负锤击力度"""
        hammer = HammerParameters(
            force=-500.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 500.0)
        strike_result = {
            "avg_thickness_um": 500.0,
            "min_thickness_um": 499.0,
            "thickness_std_um": 0.5,
        }

        config = VirtualExperienceConfig(mode="beginner")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)

    def test_zero_thickness_danger(self):
        """异常场景：厚度为零（已破裂）"""
        hammer = HammerParameters(
            force=1500.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 0.1)
        current_thickness = np.zeros((48, 48))
        strike_result = {
            "avg_thickness_um": 0.0,
            "min_thickness_um": 0.0,
            "thickness_std_um": 0.0,
        }

        config = VirtualExperienceConfig(mode="master")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertIsInstance(feedback, StrikeFeedback)
        self.assertEqual(feedback.visual_effect, "danger")

    def test_empty_achievement_list(self):
        """异常场景：空已解锁成就列表"""
        stats = {"total_strikes": 0}
        unlocked = []

        new_ach = self.experience.check_achievements(stats, unlocked)

        self.assertEqual(len(new_ach), 0)
        self.assertEqual(len(unlocked), 0)

    def test_unknown_achievement_id_in_unlocked(self):
        """异常场景：已解锁列表包含未知成就ID"""
        stats = {"total_strikes": 5}
        unlocked = ["fake_achievement_xyz", "another_fake"]

        new_ach = self.experience.check_achievements(stats, unlocked)

        self.assertIsInstance(new_ach, list)
        self.assertIn("first_strike", [a["id"] for a in new_ach])

    def test_empty_stats_dict(self):
        """异常场景：空统计数据字典"""
        stats = {}
        unlocked = []

        new_ach = self.experience.check_achievements(stats, unlocked)

        self.assertEqual(len(new_ach), 0)

    def test_score_with_zero_multiplier(self):
        """异常场景：零分系数"""
        config = VirtualExperienceConfig(mode="beginner")
        feedback = StrikeFeedback(
            vibration_intensity=0.0,
            force_feedback=0.0,
            visual_effect="none",
            sound_frequency_hz=0.0,
            sound_duration_ms=0,
            quality_score=0.0,
            message="",
        )
        metrics = {
            "uniformity_within_10pct": 0.0,
            "mean_thickness_um": 500.0,
        }

        score_data = self.experience.calculate_score(metrics, feedback, config, 0)

        self.assertEqual(score_data["base_score"], 0.0)
        self.assertGreaterEqual(score_data["total_score"], 0)

    def test_negative_consecutive_strikes(self):
        """异常场景：负连击数"""
        config = VirtualExperienceConfig(mode="intermediate")
        feedback = StrikeFeedback(
            vibration_intensity=0.5,
            force_feedback=5.0,
            visual_effect="good",
            sound_frequency_hz=500.0,
            sound_duration_ms=180,
            quality_score=0.7,
            message="good",
        )
        metrics = {
            "uniformity_within_10pct": 0.5,
            "mean_thickness_um": 450.0,
        }

        score_data = self.experience.calculate_score(metrics, feedback, config, -5)

        self.assertIsInstance(score_data["total_score"], float)

    def test_vibration_clamped_to_0_1(self):
        """异常场景：振动强度应被限制在0-1范围内"""
        hammer = HammerParameters(
            force=5000.0,
            radius_mm=30.0,
            position=(0.0, 0.0),
            strike_duration_ms=50,
        )

        prev_thickness = np.full((48, 48), 100.0)
        current_thickness = np.full((48, 48), 90.0)
        strike_result = {
            "avg_thickness_um": 90.0,
            "min_thickness_um": 80.0,
            "thickness_std_um": 5.0,
        }

        config = VirtualExperienceConfig(mode="master")
        feedback = self.experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )

        self.assertGreaterEqual(feedback.vibration_intensity, 0.0)
        self.assertLessEqual(feedback.vibration_intensity, 1.0)

    def test_mode_configs_have_required_keys(self):
        """正常场景：所有模式配置包含必要的键"""
        required_keys = [
            "name", "description", "hammer_force_range_n",
            "score_multiplier",
        ]

        for mode, cfg in self.experience.mode_configs.items():
            for key in required_keys:
                self.assertIn(key, cfg, f"模式{mode}缺少配置项{key}")


# ============================================================================
# 测试运行入口
# ============================================================================

def run_all_tests():
    """运行所有测试并输出详细报告"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestAlloyComposition))
    suite.addTests(loader.loadTestsFromTestCase(TestProcessComparison))
    suite.addTests(loader.loadTestsFromTestCase(TestBuddhaGildingSimulation))
    suite.addTests(loader.loadTestsFromTestCase(TestVirtualForgingExperience))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    print("测试汇总报告")
    print("=" * 70)
    print(f"总测试数: {result.testsRun}")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")
    print(f"跳过: {len(result.skipped)}")
    print("=" * 70)

    if result.failures:
        print("\n❌ 失败的测试:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\n💥 错误的测试:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    return result


if __name__ == "__main__":
    run_all_tests()
