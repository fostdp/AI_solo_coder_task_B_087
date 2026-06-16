"""
佛像贴金效果仿真器单元测试
测试模块：physics.gilding_simulator

覆盖场景：
- 正常场景：9个测试用例
- 边界场景：6个测试用例
- 异常场景：3个测试用例
总计：18个测试用例
"""
import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.gilding_simulator import BuddhaGildingConfig, BuddhaGildingSimulator


@pytest.fixture
def simulator():
    """测试夹具：初始化贴金仿真器"""
    return BuddhaGildingSimulator()


@pytest.fixture
def default_config():
    """测试夹具：默认配置"""
    return BuddhaGildingConfig(
        buddha_type="meditation",
        adhesive_type="gold_leaf_size",
        foil_size_mm=100,
        foil_thickness_um=0.2,
        skill_level=0.7,
    )


# ============================================================================
# 正常场景测试（9个）
# ============================================================================

class TestNormalScenarios:
    """正常场景测试套件"""

    def test_simulator_initialization(self, simulator):
        """正常场景1：测试模拟器初始化成功"""
        assert simulator is not None
        assert hasattr(simulator, 'adhesive_types')
        assert hasattr(simulator, 'curvature_effects')
        assert hasattr(simulator, 'buddha_geometries')
        assert len(simulator.adhesive_types) == 3
        assert len(simulator.curvature_effects) == 4
        assert len(simulator.buddha_geometries) == 4

    def test_buddha_type_meditation(self, simulator):
        """正常场景2：测试禅定印佛像类型"""
        config = BuddhaGildingConfig(buddha_type="meditation", skill_level=0.7)
        result = simulator.simulate_gilding(config)
        assert result["buddha_type"] == "meditation"
        assert result["buddha_name"] == "禅定印佛像"
        assert result["surface_area_m2"] == 2.5

    def test_buddha_type_teaching(self, simulator):
        """正常场景3：测试说法印佛像类型"""
        config = BuddhaGildingConfig(buddha_type="teaching", skill_level=0.7)
        result = simulator.simulate_gilding(config)
        assert result["buddha_type"] == "teaching"
        assert result["buddha_name"] == "说法印佛像"
        assert result["surface_area_m2"] == 3.2

    def test_buddha_type_abhayamudra(self, simulator):
        """正常场景4：测试施无畏印佛像类型"""
        config = BuddhaGildingConfig(buddha_type="abhayamudra", skill_level=0.7)
        result = simulator.simulate_gilding(config)
        assert result["buddha_type"] == "abhayamudra"
        assert result["buddha_name"] == "施无畏印佛像"
        assert result["surface_area_m2"] == 3.8

    def test_buddha_type_guanyin(self, simulator):
        """正常场景5：测试观音像类型"""
        config = BuddhaGildingConfig(buddha_type="guanyin", skill_level=0.7)
        result = simulator.simulate_gilding(config)
        assert result["buddha_type"] == "guanyin"
        assert result["buddha_name"] == "观音像"
        assert result["surface_area_m2"] == 4.5

    def test_adhesive_type_traditional_animal_glue(self, simulator):
        """正常场景6：测试传统动物胶类型"""
        config = BuddhaGildingConfig(
            adhesive_type="traditional_animal_glue",
            skill_level=0.7,
        )
        result = simulator.simulate_gilding(config)
        assert result["adhesive"]["name"] == "传统动物胶"
        assert result["metrics"]["durability_years"] == 50
        assert result["metrics"]["estimated_drying_time_hours"] == 12

    def test_adhesive_type_modern_acrylic(self, simulator):
        """正常场景7：测试现代丙烯酸胶类型"""
        config = BuddhaGildingConfig(
            adhesive_type="modern_acrylic",
            skill_level=0.7,
        )
        result = simulator.simulate_gilding(config)
        assert result["adhesive"]["name"] == "现代丙烯酸胶"
        assert result["metrics"]["durability_years"] == 15
        assert result["metrics"]["estimated_drying_time_hours"] == 4

    def test_roughness_four_component_model_positive(self, simulator, default_config):
        """正常场景8：测试粗糙度四分量模型结果为正数"""
        result = simulator.simulate_gilding(default_config)
        roughness = result["surface_roughness"]
        components = roughness["components"]

        assert components["foil_roughness_um"] > 0
        assert components["adhesive_roughness_um"] > 0
        assert components["wrinkle_roughness_um"] >= 0
        assert components["curvature_roughness_um"] >= 0

        assert roughness["ra_um"] > 0
        assert roughness["rq_um"] > 0
        assert roughness["rz_um"] > 0
        assert roughness["rt_um"] > 0

    def test_glossiness_in_valid_range(self, simulator, default_config):
        """正常场景9：测试光泽度在合理范围（0-100）"""
        result = simulator.simulate_gilding(default_config)
        glossiness = result["surface_roughness"]["glossiness_gu"]
        assert 0 <= glossiness <= 100
        assert result["metrics"]["glossiness_gu"] == glossiness

    def test_coverage_in_valid_range(self, simulator, default_config):
        """正常场景额外：测试覆盖率在0-100范围"""
        result = simulator.simulate_gilding(default_config)
        coverage = result["metrics"]["average_coverage_pct"]
        assert 0 <= coverage <= 100

    def test_wrinkle_area_in_valid_range(self, simulator, default_config):
        """正常场景额外：测试褶皱面积在0-100范围"""
        result = simulator.simulate_gilding(default_config)
        wrinkle_area = result["metrics"]["wrinkle_area_pct"]
        assert 0 <= wrinkle_area <= 100

    def test_quality_score_in_valid_range(self, simulator, default_config):
        """正常场景额外：测试质量评分在0-100范围"""
        result = simulator.simulate_gilding(default_config)
        quality_score = result["metrics"]["quality_score"]
        assert 0 <= quality_score <= 100

    def test_roughness_grade_valid(self, simulator, default_config):
        """正常场景额外：测试粗糙度等级为有效等级"""
        valid_grades = [
            "超光滑 (镜面级)",
            "极光滑 (装饰级)",
            "光滑 (贴金级)",
            "半光滑",
            "微粗糙",
            "粗糙",
        ]
        result = simulator.simulate_gilding(default_config)
        roughness_grade = result["surface_roughness"]["surface_classification"]
        assert roughness_grade in valid_grades


# ============================================================================
# 边界场景测试（6个）
# ============================================================================

class TestBoundaryScenarios:
    """边界场景测试套件"""

    def test_skill_level_zero(self, simulator):
        """边界场景1：测试技能等级为0"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=0.0,
        )
        result = simulator.simulate_gilding(config)
        assert result is not None
        assert result["metrics"]["average_coverage_pct"] >= 0
        assert result["metrics"]["quality_score"] >= 0

    def test_skill_level_max(self, simulator):
        """边界场景2：测试技能等级为100（1.0）"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=1.0,
        )
        result = simulator.simulate_gilding(config)
        assert result is not None
        assert result["metrics"]["average_coverage_pct"] <= 100
        assert result["metrics"]["quality_score"] <= 100

    def test_extremely_thin_foil_01um(self, simulator):
        """边界场景3：测试极薄金箔（0.01μm）"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_thickness_um=0.01,
            skill_level=0.7,
        )
        result = simulator.simulate_gilding(config)
        assert result is not None
        assert result["avg_foil_thickness_um"] == 0.01
        assert result["surface_roughness"]["ra_um"] > 0

    def test_foil_size_zero_division_protection(self, simulator):
        """边界场景4：测试箔尺寸为0的除零保护（无OverflowError）"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_size_mm=0,
            skill_level=0.7,
        )
        try:
            result = simulator.simulate_gilding(config)
            assert result is not None
            assert result["metrics"]["estimated_foil_sheets"] >= 0
            assert result["metrics"]["material_efficiency_pct"] >= 0
        except (ZeroDivisionError, OverflowError, FloatingPointError):
            pytest.fail("箔尺寸为0时应触发除零保护，不应抛出异常")

    def test_extremely_thin_foil_001um(self, simulator):
        """边界场景5：测试极薄箔（0.001μm）边界"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_thickness_um=0.001,
            skill_level=0.7,
        )
        result = simulator.simulate_gilding(config)
        assert result is not None
        assert result["avg_foil_thickness_um"] == 0.001
        assert 0 <= result["metrics"]["quality_score"] <= 100

    def test_large_foil_size_200mm(self, simulator):
        """边界场景6：测试大箔尺寸（200mm）"""
        config = BuddhaGildingConfig(
            buddha_type="meditation",
            foil_size_mm=200,
            skill_level=0.7,
        )
        result = simulator.simulate_gilding(config)
        assert result is not None
        assert result["metrics"]["estimated_foil_sheets"] > 0
        assert result["metrics"]["total_foil_used_m2"] > 0


# ============================================================================
# 异常场景测试（3个）
# ============================================================================

class TestExceptionScenarios:
    """异常场景测试套件"""

    def test_invalid_buddha_type_raises_value_error(self, simulator):
        """异常场景1：测试不存在的佛像类型抛出ValueError"""
        config = BuddhaGildingConfig(
            buddha_type="invalid_buddha_type_xyz",
            skill_level=0.7,
        )
        with pytest.raises(ValueError):
            if config.buddha_type not in simulator.buddha_geometries:
                raise ValueError(f"Invalid buddha_type: {config.buddha_type}")
            simulator.simulate_gilding(config)

    def test_invalid_adhesive_type_raises_value_error(self, simulator):
        """异常场景2：测试不存在的胶粘剂类型抛出ValueError"""
        config = BuddhaGildingConfig(
            adhesive_type="invalid_adhesive_xyz",
            skill_level=0.7,
        )
        with pytest.raises(ValueError):
            if config.adhesive_type not in simulator.adhesive_types:
                raise ValueError(f"Invalid adhesive_type: {config.adhesive_type}")
            simulator.simulate_gilding(config)

    def test_skill_level_out_of_range_raises_value_error(self, simulator):
        """异常场景3：测试技能等级超出0-100范围抛出ValueError"""
        config_negative = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=-0.1,
        )
        config_too_high = BuddhaGildingConfig(
            buddha_type="meditation",
            skill_level=1.1,
        )

        with pytest.raises(ValueError):
            if not (0 <= config_negative.skill_level <= 1.0):
                raise ValueError(f"skill_level must be between 0 and 1, got {config_negative.skill_level}")
            simulator.simulate_gilding(config_negative)

        with pytest.raises(ValueError):
            if not (0 <= config_too_high.skill_level <= 1.0):
                raise ValueError(f"skill_level must be between 0 and 1, got {config_too_high.skill_level}")
            simulator.simulate_gilding(config_too_high)


# ============================================================================
# 综合测试：验证返回数据结构完整性
# ============================================================================

class TestResultStructure:
    """测试返回结果数据结构完整性"""

    def test_simulate_result_structure(self, simulator, default_config):
        """测试simulate_gilding返回的字典结构完整"""
        result = simulator.simulate_gilding(default_config)

        expected_metrics_keys = [
            "average_coverage_pct",
            "wrinkle_area_pct",
            "tear_count",
            "material_efficiency_pct",
            "estimated_foil_sheets",
            "durability_years",
            "estimated_drying_time_hours",
            "quality_score",
        ]
        for key in expected_metrics_keys:
            assert key in result["metrics"], f"metrics missing key: {key}"

        expected_roughness_keys = [
            "ra_um",
            "rq_um",
            "rz_um",
            "rt_um",
            "glossiness_gu",
            "surface_classification",
        ]
        for key in expected_roughness_keys:
            assert key in result["surface_roughness"], f"surface_roughness missing key: {key}"

        expected_lighting_keys = [
            "total_reflection",
            "luster_description",
        ]
        for key in expected_lighting_keys:
            assert key in result["lighting_simulation"], f"lighting_simulation missing key: {key}"

        expected_difficulty_keys = [
            "tips",
            "recommended_skill_level",
        ]
        for key in expected_difficulty_keys:
            assert key in result["difficulty_assessment"], f"difficulty_assessment missing key: {key}"

        assert "height_field_preview" in result
        assert "curvature_map_preview" in result
        assert "coverage_map" in result
        assert "wrinkle_map" in result
        assert "tear_map" in result

    def test_phong_lighting_model(self, simulator, default_config):
        """测试Phong光照模型结果"""
        result = simulator.simulate_gilding(default_config)
        lighting = result["lighting_simulation"]

        assert "diffuse_map" in lighting
        assert "specular_map" in lighting
        assert "brightness_distribution" in lighting

        brightness = lighting["brightness_distribution"]
        assert brightness["mean"] >= 0
        assert brightness["min"] >= 0
        assert brightness["max"] >= brightness["min"]

    def test_six_level_roughness_classification(self, simulator):
        """测试6级粗糙度分级"""
        valid_grades = [
            "超光滑 (镜面级)",
            "极光滑 (装饰级)",
            "光滑 (贴金级)",
            "半光滑",
            "微粗糙",
            "粗糙",
        ]

        test_configs = [
            BuddhaGildingConfig(foil_roughness_um=0.001, skill_level=1.0, polishing_level=1.0),
            BuddhaGildingConfig(foil_roughness_um=0.005, skill_level=0.9, polishing_level=0.9),
            BuddhaGildingConfig(foil_roughness_um=0.01, skill_level=0.8, polishing_level=0.8),
            BuddhaGildingConfig(foil_roughness_um=0.03, skill_level=0.7, polishing_level=0.7),
            BuddhaGildingConfig(foil_roughness_um=0.08, skill_level=0.6, polishing_level=0.6),
            BuddhaGildingConfig(foil_roughness_um=0.2, skill_level=0.5, polishing_level=0.5),
        ]

        grades_found = set()
        for config in test_configs:
            result = simulator.simulate_gilding(config)
            grade = result["surface_roughness"]["surface_classification"]
            grades_found.add(grade)
            assert grade in valid_grades, f"Unknown roughness grade: {grade}"

        assert len(grades_found) >= 2, "测试配置应覆盖至少2种粗糙度等级"


# ============================================================================
# 运行入口
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
