"""
工艺对比分析模块单元测试
覆盖正常、边界、异常三类场景，共15个测试用例
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.process_comparator import (
    ProcessParameters,
    AncientForgingParams,
    VacuumCoatingParams,
    ProcessComparisonResult,
    ProcessComparisonEngine,
)


@pytest.fixture
def engine():
    """测试夹具：初始化工艺对比引擎"""
    return ProcessComparisonEngine()


# ============================================================================
# 正常场景测试（7个）
# ============================================================================

class TestNormalScenarios:
    """正常场景测试"""

    def test_engine_initialization_success(self, engine):
        """正常场景1：测试引擎初始化成功"""
        assert isinstance(engine, ProcessComparisonEngine)
        assert hasattr(engine, 'config')
        assert 'ancient_forging' in engine.config
        assert 'modern_vacuum_coating' in engine.config
        assert 'modern_electroplating' in engine.config

    def test_typical_parameters_comparison(self, engine):
        """正常场景2：测试典型参数对比（厚度1μm，面积100cm²）"""
        result = engine.compare_processes(
            target_thickness_um=1.0,
            area_cm2=100.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.ancient['target_thickness_um'] == 1.0
        assert result.ancient['can_achieve_target'] is True
        assert result.modern_vacuum['can_achieve_target'] is True
        assert result.modern_electroplating['can_achieve_target'] is True

    def test_result_contains_all_three_processes(self, engine):
        """正常场景3：测试结果包含所有3种工艺"""
        result = engine.compare_processes(
            target_thickness_um=0.5,
            area_cm2=50.0,
        )

        assert hasattr(result, 'ancient')
        assert hasattr(result, 'modern_vacuum')
        assert hasattr(result, 'modern_electroplating')
        assert isinstance(result.ancient, dict)
        assert isinstance(result.modern_vacuum, dict)
        assert isinstance(result.modern_electroplating, dict)

    def test_eight_metrics_completeness(self, engine):
        """正常场景4：测试每个工艺的8个指标完整性"""
        expected_metrics = [
            'uniformity_error_pct',
            'total_energy_kwh',
            'total_time_h',
            'estimated_cost_cny',
            'environmental_impact_score',
            'surface_roughness_um',
            'material_utilization_pct',
            'overall_score',
        ]

        result = engine.compare_processes(
            target_thickness_um=0.2,
            area_cm2=100.0,
        )

        for process_data in [result.ancient, result.modern_vacuum, result.modern_electroplating]:
            for metric in expected_metrics:
                assert metric in process_data, f"缺少指标: {metric}"
                assert process_data[metric] is not None, f"指标值为空: {metric}"

    def test_overall_score_within_range(self, engine):
        """正常场景5：测试综合得分在0-100范围内"""
        result = engine.compare_processes(
            target_thickness_um=1.0,
            area_cm2=100.0,
        )

        for process_data in [result.ancient, result.modern_vacuum, result.modern_electroplating]:
            score = process_data['overall_score']
            assert 0 <= score <= 100, f"综合得分应在0-100范围内，实际: {score}"

    def test_uniformity_error_positive(self, engine):
        """正常场景6：测试均匀性误差为正数"""
        result = engine.compare_processes(
            target_thickness_um=0.5,
            area_cm2=200.0,
        )

        for process_data in [result.ancient, result.modern_vacuum, result.modern_electroplating]:
            error = process_data['uniformity_error_pct']
            assert error > 0, f"均匀性误差应为正数，实际: {error}"

    def test_get_single_process_metrics(self, engine):
        """正常场景7：测试获取单个工艺指标"""
        metrics = engine.get_process_metrics('ancient_forging')

        assert isinstance(metrics, dict)
        assert 'uniformity_error_pct' in metrics
        assert 'total_energy_kwh' in metrics
        assert 'total_time_h' in metrics
        assert 'estimated_cost_cny' in metrics
        assert 'environmental_impact_score' in metrics
        assert 'surface_roughness_um' in metrics
        assert 'material_utilization_pct' in metrics
        assert 'overall_score' in metrics
        assert 0 <= metrics['overall_score'] <= 100


# ============================================================================
# 边界场景测试（5个）
# ============================================================================

class TestBoundaryScenarios:
    """边界场景测试"""

    def test_extremely_small_thickness(self, engine):
        """边界场景1：测试极小厚度（0.01μm）"""
        result = engine.compare_processes(
            target_thickness_um=0.01,
            area_cm2=100.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.modern_vacuum['can_achieve_target'] is True
        assert result.ancient['can_achieve_target'] is False
        assert result.modern_electroplating['can_achieve_target'] is False

    def test_extremely_large_thickness(self, engine):
        """边界场景2：测试极大厚度（1000μm）"""
        result = engine.compare_processes(
            target_thickness_um=1000.0,
            area_cm2=100.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.ancient['can_achieve_target'] is True
        assert result.modern_vacuum['can_achieve_target'] is True
        assert result.modern_electroplating['can_achieve_target'] is True
        assert result.ancient['target_thickness_um'] == 1000.0

    def test_zero_area_boundary_protection(self, engine):
        """边界场景3：测试零面积边界（应保护，不除零）"""
        result = engine.compare_processes(
            target_thickness_um=1.0,
            area_cm2=0.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.ancient['total_energy_kwh'] >= 0
        assert result.ancient['total_time_h'] >= 0
        assert result.ancient['estimated_cost_cny'] > 0

    def test_large_area(self, engine):
        """边界场景4：测试大面积（10000cm²）"""
        result = engine.compare_processes(
            target_thickness_um=1.0,
            area_cm2=10000.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.ancient['total_energy_kwh'] > 0
        assert result.modern_vacuum['total_energy_kwh'] > result.ancient['total_energy_kwh']
        assert result.ancient['total_time_h'] > result.modern_vacuum['total_time_h']

    def test_zero_thickness_boundary(self, engine):
        """边界场景5：测试厚度为0的边界保护"""
        result = engine.compare_processes(
            target_thickness_um=0.0,
            area_cm2=100.0,
        )

        assert isinstance(result, ProcessComparisonResult)
        assert result.ancient['can_achieve_target'] is False
        assert result.modern_vacuum['can_achieve_target'] is False
        assert result.modern_electroplating['can_achieve_target'] is False
        assert result.ancient['target_thickness_um'] == 0.0


# ============================================================================
# 异常场景测试（3个）
# ============================================================================

class TestExceptionScenarios:
    """异常场景测试"""

    def test_negative_thickness_raises_valueerror(self, engine):
        """异常场景1：测试负厚度抛出 ValueError"""
        with pytest.raises(ValueError) as excinfo:
            engine.compare_processes(
                target_thickness_um=-1.0,
                area_cm2=100.0,
            )
        assert "厚度" in str(excinfo.value)
        assert "负数" in str(excinfo.value)

    def test_negative_area_raises_valueerror(self, engine):
        """异常场景2：测试负面积抛出 ValueError"""
        with pytest.raises(ValueError) as excinfo:
            engine.compare_processes(
                target_thickness_um=1.0,
                area_cm2=-100.0,
            )
        assert "面积" in str(excinfo.value)
        assert "负数" in str(excinfo.value)

    def test_nonexistent_process_key_raises_keyerror(self, engine):
        """异常场景3：测试获取不存在的工艺指标抛出 KeyError"""
        with pytest.raises(KeyError) as excinfo:
            engine.get_process_metrics('nonexistent_process')
        assert "nonexistent_process" in str(excinfo.value)
        assert "未知的工艺键" in str(excinfo.value)


# ============================================================================
# 附加测试：参数验证功能
# ============================================================================

class TestParameterValidation:
    """参数验证功能测试"""

    def test_validate_ancient_forging_params_valid(self, engine):
        """测试有效的古代锻制参数验证"""
        params = AncientForgingParams(
            temperature_c=450.0,
            hammer_force_n=500.0,
            strike_count=1000,
            foil_thickness_um=0.2,
            area_cm2=100.0,
        )
        assert engine.validate_params(params) is True

    def test_validate_ancient_forging_params_invalid(self, engine):
        """测试无效的古代锻制参数验证"""
        params = AncientForgingParams(
            temperature_c=450.0,
            hammer_force_n=-500.0,
            strike_count=1000,
            foil_thickness_um=0.2,
            area_cm2=100.0,
        )
        assert engine.validate_params(params) is False

    def test_validate_vacuum_coating_params_valid(self, engine):
        """测试有效的真空镀膜参数验证"""
        params = VacuumCoatingParams(
            deposition_rate_nm_s=0.333,
            base_pressure_pa=1e-3,
            substrate_temp_c=150.0,
            power_w=5000.0,
            argon_flow_sccm=20.0,
        )
        assert engine.validate_params(params) is True

    def test_validate_vacuum_coating_params_invalid(self, engine):
        """测试无效的真空镀膜参数验证"""
        params = VacuumCoatingParams(
            deposition_rate_nm_s=-0.333,
            base_pressure_pa=1e-3,
            substrate_temp_c=150.0,
            power_w=5000.0,
            argon_flow_sccm=20.0,
        )
        assert engine.validate_params(params) is False

    def test_validate_non_process_params(self, engine):
        """测试非 ProcessParameters 对象验证"""
        assert engine.validate_params("not a params object") is False
        assert engine.validate_params(None) is False


# ============================================================================
# 附加测试：数据类实例化
# ============================================================================

class TestDataclassInstantiation:
    """数据类实例化测试"""

    def test_process_parameters_base_class(self):
        """测试 ProcessParameters 基类实例化"""
        params = ProcessParameters(name="测试工艺", process_type="test")
        assert params.name == "测试工艺"
        assert params.process_type == "test"

    def test_ancient_forging_params_defaults(self):
        """测试 AncientForgingParams 默认值"""
        params = AncientForgingParams()
        assert params.process_type == "ancient_forging"
        assert params.temperature_c == 450.0
        assert params.hammer_force_n == 500.0
        assert params.strike_count == 1000
        assert params.foil_thickness_um == 0.2
        assert params.area_cm2 == 100.0

    def test_vacuum_coating_params_defaults(self):
        """测试 VacuumCoatingParams 默认值"""
        params = VacuumCoatingParams()
        assert params.process_type == "modern_vacuum_coating"
        assert params.deposition_rate_nm_s == 0.333
        assert params.base_pressure_pa == 1e-3
        assert params.substrate_temp_c == 150.0
        assert params.power_w == 5000.0
        assert params.argon_flow_sccm == 20.0

    def test_result_key_map_mapping(self, engine):
        """测试 result_key_map 映射关系"""
        mapping = engine.result_key_map
        assert mapping["ancient_forging"] == "ancient"
        assert mapping["modern_vacuum_coating"] == "modern_vacuum"
        assert mapping["modern_electroplating"] == "modern_electroplating"
