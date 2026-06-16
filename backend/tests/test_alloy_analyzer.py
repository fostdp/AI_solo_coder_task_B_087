"""
合金分析模块测试套件
测试模块：physics.alloy_analyzer
覆盖正常、边界、异常场景，共约15个测试用例
"""

import sys
import os
import unittest
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.alloy_analyzer import (
    AlloyComposition,
    get_alloy_composition,
    compare_alloys,
)


def load_test_config():
    """加载材料配置用于测试"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "material.json"
    )
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    return config.get("alloy_compositions", {})


VALID_ALLOY_KEYS = [
    "pure_gold_24k",
    "gold_copper_22k",
    "gold_copper_18k",
    "gold_silver_22k",
    "ternary_alloy_18k",
]


class TestAlloyAnalyzer(unittest.TestCase):
    """合金分析模块测试类"""

    @classmethod
    def setUpClass(cls):
        """类级别的测试前置：加载配置"""
        cls.config = load_test_config()

    # =========================================================================
    # 正常场景测试（约8个）
    # =========================================================================

    def test_get_all_valid_alloys(self):
        """正常场景：测试所有5种合金能正确获取"""
        for key in VALID_ALLOY_KEYS:
            alloy = get_alloy_composition(key, self.config)
            self.assertIsInstance(alloy, AlloyComposition)
            self.assertEqual(alloy.key, key)

    def test_alloy_data_integrity(self):
        """正常场景：测试合金成分数据完整性"""
        alloy = get_alloy_composition("pure_gold_24k", self.config)

        self.assertIsNotNone(alloy.key)
        self.assertIsNotNone(alloy.name)
        self.assertIsInstance(alloy.gold_ratio, float)
        self.assertIsInstance(alloy.copper_ratio, float)
        self.assertIsInstance(alloy.silver_ratio, float)
        self.assertIsInstance(alloy.color_rgb, tuple)
        self.assertEqual(len(alloy.color_rgb), 3)
        self.assertIsInstance(alloy.malleability_factor, float)
        self.assertIsInstance(alloy.hardness_vickers, (int, float))
        self.assertIsNotNone(alloy.historical_period)
        self.assertIsInstance(alloy.typical_uses, list)
        self.assertIsNotNone(alloy.description)

    def test_post_init_calculated_properties(self):
        """正常场景：测试 __post_init__ 计算属性"""
        alloy = get_alloy_composition("gold_copper_22k", self.config)

        self.assertIsInstance(alloy.youngs_modulus_alloy, float)
        self.assertGreater(alloy.youngs_modulus_alloy, 79.0)

        self.assertIsInstance(alloy.yield_strength_alloy, float)
        self.assertGreater(alloy.yield_strength_alloy, 120.0)

        self.assertIsInstance(alloy.ultimate_strength_alloy, float)
        self.assertGreater(alloy.ultimate_strength_alloy, 210.0)

        self.assertIsInstance(alloy.density_alloy, float)
        self.assertIsInstance(alloy.recrystallization_temp_alloy, float)
        self.assertIsInstance(alloy.melting_point_alloy, float)
        self.assertIsInstance(alloy.work_hardening_coeff_alloy, float)
        self.assertIsInstance(alloy.work_hardening_exp_alloy, float)

    def test_experimental_data_exists(self):
        """正常场景：测试实验数据字段存在性"""
        for key in VALID_ALLOY_KEYS:
            cfg = self.config.get(key, {})
            self.assertIn("experimental_data", cfg)
            exp_data = cfg["experimental_data"]
            self.assertIn("data_source", exp_data)
            self.assertIn("measured_properties", exp_data)
            measured = exp_data["measured_properties"]
            self.assertIn("youngs_modulus_gpa", measured)
            self.assertIn("yield_strength_mpa", measured)
            self.assertIn("ultimate_strength_mpa", measured)
            self.assertIn("elongation_pct", measured)
            self.assertIn("hardness_hv", measured)

    def test_compare_two_alloys(self):
        """正常场景：测试对比2种合金"""
        result = compare_alloys(
            ["pure_gold_24k", "gold_copper_22k"],
            self.config
        )

        self.assertNotIn("error", result)
        self.assertIn("alloys", result)
        self.assertEqual(len(result["alloys"]), 2)
        self.assertIn("radar_chart", result)
        self.assertIn("recommendation", result)

    def test_compare_three_alloys(self):
        """正常场景：测试对比3种合金"""
        result = compare_alloys(
            ["pure_gold_24k", "gold_copper_22k", "gold_silver_22k"],
            self.config
        )

        self.assertNotIn("error", result)
        self.assertEqual(len(result["alloys"]), 3)
        self.assertEqual(len(result["radar_chart"]["datasets"]), 3)

    def test_radar_chart_dimensions(self):
        """正常场景：测试雷达图数据维度完整性"""
        result = compare_alloys(
            ["pure_gold_24k", "gold_copper_22k"],
            self.config
        )

        radar = result["radar_chart"]
        self.assertIn("labels", radar)
        self.assertIn("datasets", radar)

        expected_labels = [
            "延展性系数", "硬度 HV", "屈服强度比",
            "密度比", "成本比", "耐磨性", "耐变色性"
        ]
        self.assertEqual(radar["labels"], expected_labels)
        self.assertEqual(len(radar["labels"]), 7)

        for dataset in radar["datasets"]:
            self.assertIn("label", dataset)
            self.assertIn("data", dataset)
            self.assertIn("color_rgb", dataset)
            self.assertEqual(len(dataset["data"]), 7)

    def test_recommendation_fields(self):
        """正常场景：测试推荐建议字段存在性"""
        result = compare_alloys(
            ["pure_gold_24k", "gold_copper_22k", "gold_copper_18k"],
            self.config
        )

        rec = result["recommendation"]
        self.assertIn("best_ductility", rec)
        self.assertIn("best_hardness", rec)
        self.assertIn("best_cost_effective", rec)
        self.assertIn("summary", rec)

        self.assertIsInstance(rec["best_ductility"], str)
        self.assertIsInstance(rec["best_hardness"], str)
        self.assertIsInstance(rec["best_cost_effective"], str)
        self.assertIsInstance(rec["summary"], str)
        self.assertGreater(len(rec["summary"]), 0)

    # =========================================================================
    # 边界场景测试（约4个）
    # =========================================================================

    def test_empty_list_comparison(self):
        """边界场景：测试空列表对比（应返回错误信息）"""
        result = compare_alloys([], self.config)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "需要至少两种合金进行对比")

    def test_single_element_comparison(self):
        """边界场景：测试单元素列表对比"""
        result = compare_alloys(["pure_gold_24k"], self.config)

        self.assertIn("error", result)
        self.assertEqual(result["error"], "需要至少两种合金进行对比")

    def test_comparison_includes_base_alloy(self):
        """边界场景：测试对比含基准合金（纯金）"""
        result = compare_alloys(
            ["pure_gold_24k", "gold_copper_18k"],
            self.config
        )

        self.assertNotIn("error", result)
        alloys = result["alloys"]
        keys = [a["key"] for a in alloys]
        self.assertIn("pure_gold_24k", keys)
        self.assertIn("gold_copper_18k", keys)

        pure_gold_data = next(a for a in alloys if a["key"] == "pure_gold_24k")
        self.assertIn("comparison_with_pure_gold", pure_gold_data)

    def test_all_five_alloys_comparison(self):
        """边界场景：测试所有5种合金同时对比"""
        result = compare_alloys(VALID_ALLOY_KEYS, self.config)

        self.assertNotIn("error", result)
        self.assertEqual(len(result["alloys"]), 5)
        self.assertEqual(len(result["radar_chart"]["datasets"]), 5)

        keys_in_result = [a["key"] for a in result["alloys"]]
        for key in VALID_ALLOY_KEYS:
            self.assertIn(key, keys_in_result)

    # =========================================================================
    # 异常场景测试（约3个）
    # =========================================================================

    def test_nonexistent_alloy_key(self):
        """异常场景：测试不存在的 alloy_key 返回 None"""
        result = get_alloy_composition("invalid_alloy_key_xyz", self.config)
        self.assertIsNone(result)

    def test_compare_with_nonexistent_key(self):
        """异常场景：测试对比列表含不存在的 key（应过滤掉）"""
        result = compare_alloys(
            ["pure_gold_24k", "invalid_key", "gold_copper_22k"],
            self.config
        )

        self.assertNotIn("error", result)
        self.assertEqual(len(result["alloys"]), 2)
        keys = [a["key"] for a in result["alloys"]]
        self.assertNotIn("invalid_key", keys)
        self.assertIn("pure_gold_24k", keys)
        self.assertIn("gold_copper_22k", keys)

    def test_compare_with_all_nonexistent_keys(self):
        """异常场景：测试对比列表全部为无效 key"""
        result = compare_alloys(
            ["invalid_1", "invalid_2", "invalid_3"],
            self.config
        )

        self.assertIn("error", result)
        self.assertEqual(result["error"], "需要至少两种合金进行对比")

    # =========================================================================
    # 附加验证测试
    # =========================================================================

    def test_alloy_ductility_metrics(self):
        """附加：测试 get_ductility_metrics 方法"""
        alloy = get_alloy_composition("pure_gold_24k", self.config)
        metrics = alloy.get_ductility_metrics()

        self.assertIsInstance(metrics, dict)
        self.assertIn("max_elongation_pct", metrics)
        self.assertIn("formability_index", metrics)
        self.assertIn("hardness_vickers", metrics)
        self.assertGreater(metrics["max_elongation_pct"], 0)

    def test_to_material_properties(self):
        """附加：测试 to_material_properties 方法"""
        from physics.physics_model import MaterialProperties

        alloy = get_alloy_composition("gold_copper_22k", self.config)
        mat_props = alloy.to_material_properties()

        self.assertIsInstance(mat_props, MaterialProperties)
        self.assertGreater(mat_props.youngs_modulus, 0)
        self.assertGreater(mat_props.yield_strength, 0)

    def test_compare_with_pure_gold(self):
        """附加：测试 compare_with_pure_gold 方法"""
        alloy = get_alloy_composition("gold_copper_18k", self.config)
        comparison = alloy.compare_with_pure_gold()

        self.assertIsInstance(comparison, dict)
        self.assertIn("ductility_ratio", comparison)
        self.assertIn("hardness_ratio", comparison)
        self.assertIn("yield_strength_ratio", comparison)
        self.assertIn("cost_ratio", comparison)

        self.assertLess(comparison["cost_ratio"], 1.0)
        self.assertGreater(comparison["hardness_ratio"], 1.0)


if __name__ == "__main__":
    unittest.main()
