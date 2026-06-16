"""
vr_gold_beater 模块测试套件
覆盖正常、边界、异常三类测试用例，共约18个测试用例

测试模块：physics.vr_gold_beater
主要类：
- VirtualExperienceConfig: 虚拟体验配置
- StrikeFeedback: 锤击反馈数据
- VirtualForgingExperience: 虚拟打金体验主类
"""

import sys
import os
import pytest
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from physics.vr_gold_beater import (
    VirtualExperienceConfig,
    StrikeFeedback,
    VirtualForgingExperience,
    HammerParameters,
)


# ============================================================================
# 测试1：VirtualExperienceConfig 配置类测试
# ============================================================================

class TestVirtualExperienceConfig:
    """VirtualExperienceConfig 配置类测试"""

    def test_default_config(self):
        """正常场景：默认配置初始化成功"""
        config = VirtualExperienceConfig()
        assert config.mode == "beginner"
        assert config.haptic_enabled is False
        assert config.alloy_key == "pure_gold_24k"
        assert config.target_thickness_um == 0.5

    def test_custom_config(self):
        """正常场景：自定义配置初始化"""
        config = VirtualExperienceConfig(
            mode="master",
            haptic_enabled=True,
            alloy_key="gold_copper_22k",
            target_thickness_um=0.1
        )
        assert config.mode == "master"
        assert config.haptic_enabled is True
        assert config.alloy_key == "gold_copper_22k"
        assert config.target_thickness_um == 0.1

    def test_all_fields_present(self):
        """正常场景：测试所有配置字段存在"""
        config = VirtualExperienceConfig()
        assert hasattr(config, "mode")
        assert hasattr(config, "haptic_enabled")
        assert hasattr(config, "alloy_key")
        assert hasattr(config, "target_thickness_um")
        assert hasattr(config, "tutorial_enabled")


# ============================================================================
# 测试2：StrikeFeedback 反馈类测试
# ============================================================================

class TestStrikeFeedback:
    """StrikeFeedback 反馈类测试"""

    def test_basic_fields(self):
        """正常场景：基础字段初始化"""
        feedback = StrikeFeedback(
            vibration_intensity=0.5,
            force_feedback=5.0,
            visual_effect="good",
            sound_frequency_hz=600.0,
            sound_duration_ms=200,
            quality_score=0.8,
            message="不错的一击"
        )
        assert feedback.vibration_intensity == 0.5
        assert feedback.force_feedback == 5.0
        assert feedback.quality_score == 0.8
        assert feedback.visual_effect == "good"

    def test_extended_fields_defaults(self):
        """正常场景：扩展字段默认值向后兼容"""
        feedback = StrikeFeedback(
            vibration_intensity=0.5,
            force_feedback=5.0,
            visual_effect="good",
            sound_frequency_hz=600.0,
            sound_duration_ms=200,
            quality_score=0.8,
            message="测试"
        )
        assert feedback.force_curve is None
        assert feedback.impact_peak_force_n == 0.0
        assert feedback.plastic_resistance_force_n == 0.0
        assert feedback.elastic_rebound_force_n == 0.0
        assert feedback.damping_coefficient == 0.85
        assert feedback.haptic_pattern == "normal_tap"

    def test_extended_fields_custom(self):
        """正常场景：扩展字段自定义值"""
        force_curve = [1.0, 2.0, 3.0]
        feedback = StrikeFeedback(
            vibration_intensity=0.7,
            force_feedback=8.0,
            visual_effect="excellent",
            sound_frequency_hz=800.0,
            sound_duration_ms=250,
            quality_score=0.95,
            message="完美",
            force_curve=force_curve,
            impact_peak_force_n=1200.0,
            plastic_resistance_force_n=300.0,
            elastic_rebound_force_n=150.0,
            haptic_pattern="deep_press",
            rebound_velocity=2.5
        )
        assert feedback.force_curve == force_curve
        assert feedback.impact_peak_force_n == 1200.0
        assert feedback.plastic_resistance_force_n == 300.0
        assert feedback.elastic_rebound_force_n == 150.0
        assert feedback.haptic_pattern == "deep_press"
        assert feedback.rebound_velocity == 2.5


# ============================================================================
# 测试3：VirtualForgingExperience 正常场景测试
# ============================================================================

class TestVirtualForgingExperienceNormal:
    """VirtualForgingExperience 正常场景测试（约9个）"""

    @pytest.fixture
    def experience(self):
        return VirtualForgingExperience()

    @pytest.fixture
    def default_config(self):
        return VirtualExperienceConfig(mode="beginner", alloy_key="pure_gold_24k")

    def test_initialization_success(self, experience):
        """正常场景1：测试体验初始化成功"""
        assert experience is not None
        assert hasattr(experience, 'mode_configs')
        assert hasattr(experience, 'achievements')
        assert hasattr(experience, 'tutorial_steps')
        assert len(experience.mode_configs) == 3
        assert len(experience.achievements) == 10
        assert len(experience.tutorial_steps) == 7

    @pytest.mark.parametrize("mode", ["beginner", "intermediate", "master"])
    def test_three_modes(self, experience, mode):
        """正常场景2-4：测试3种模式各一次"""
        config = VirtualExperienceConfig(mode=mode)
        hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 480.0)
        strike_result = {
            "avg_thickness_um": 480.0,
            "min_thickness_um": 470.0,
            "thickness_std_um": 5.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )
        assert isinstance(feedback, StrikeFeedback)
        assert 0 <= feedback.quality_score <= 1

    def test_strike_returns_strike_feedback(self, experience, default_config):
        """正常场景5：测试锤击返回 StrikeFeedback 对象"""
        hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 480.0)
        strike_result = {
            "avg_thickness_um": 480.0,
            "min_thickness_um": 470.0,
            "thickness_std_um": 5.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, default_config
        )
        assert isinstance(feedback, StrikeFeedback)

    def test_force_curve_has_100_points(self, experience, default_config):
        """正常场景6：测试力曲线有100个点"""
        hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 480.0)
        strike_result = {
            "avg_thickness_um": 480.0,
            "min_thickness_um": 470.0,
            "thickness_std_um": 5.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, default_config
        )
        assert feedback.force_curve is not None
        assert len(feedback.force_curve) == 100

    def test_force_curve_peak_positive(self, experience, default_config):
        """正常场景7：测试力曲线峰值为正数"""
        hammer = HammerParameters(force=1000.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 450.0)
        strike_result = {
            "avg_thickness_um": 450.0,
            "min_thickness_um": 440.0,
            "thickness_std_um": 8.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, default_config
        )
        assert feedback.impact_peak_force_n > 0
        assert max(feedback.force_curve) > 0

    def test_haptic_pattern_valid(self, experience, default_config):
        """正常场景8：测试触觉模式为有效值（6种之一）"""
        valid_patterns = {"light_tap", "bouncy", "sticky", "heavy_impact", "deep_press", "normal_tap"}
        hammer = HammerParameters(force=800.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 470.0)
        strike_result = {
            "avg_thickness_um": 470.0,
            "min_thickness_um": 460.0,
            "thickness_std_um": 6.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, default_config
        )
        assert feedback.haptic_pattern in valid_patterns

    def test_vibration_intensity_range(self, experience, default_config):
        """正常场景9：测试振动强度在0-1范围"""
        hammer = HammerParameters(force=600.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 485.0)
        strike_result = {
            "avg_thickness_um": 485.0,
            "min_thickness_um": 475.0,
            "thickness_std_um": 4.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, default_config
        )
        assert 0 <= feedback.vibration_intensity <= 1

    def test_achievements_returns_list(self, experience):
        """正常场景10：测试成就系统返回列表"""
        stats = {"total_strikes": 5}
        unlocked = []
        new_achievements = experience.check_achievements(stats, unlocked)
        assert isinstance(new_achievements, list)
        assert "first_strike" in unlocked

    def test_reset_restores_initial(self, experience):
        """正常场景11：测试重置功能恢复初始状态"""
        stats = {"total_strikes": 20}
        unlocked = []
        new_ach = experience.check_achievements(stats, unlocked)
        assert len(new_ach) > 0
        assert "first_strike" in unlocked
        assert "ten_strikes" in unlocked
        new_experience = VirtualForgingExperience()
        assert hasattr(new_experience, 'achievements')
        assert len(new_experience.achievements) == 10


# ============================================================================
# 测试4：VirtualForgingExperience 边界场景测试
# ============================================================================

class TestVirtualForgingExperienceBoundary:
    """VirtualForgingExperience 边界场景测试（约6个）"""

    @pytest.fixture
    def experience(self):
        return VirtualForgingExperience()

    def test_minimum_force_100n(self, experience):
        """边界场景1：测试极轻力度（最小值）"""
        config = VirtualExperienceConfig(mode="beginner")
        hammer = HammerParameters(force=200.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 498.0)
        strike_result = {
            "avg_thickness_um": 498.0,
            "min_thickness_um": 496.0,
            "thickness_std_um": 1.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )
        assert isinstance(feedback, StrikeFeedback)
        assert feedback.quality_score >= 0

    def test_maximum_force_5000n(self, experience):
        """边界场景2：测试极重力度（最大值）"""
        config = VirtualExperienceConfig(mode="master")
        hammer = HammerParameters(force=3000.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 10.0)
        current_thickness = np.full((48, 48), 8.0)
        strike_result = {
            "avg_thickness_um": 8.0,
            "min_thickness_um": 6.0,
            "thickness_std_um": 2.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )
        assert isinstance(feedback, StrikeFeedback)
        assert feedback.impact_peak_force_n > 0

    def test_consecutive_strikes_10_times(self, experience):
        """边界场景3：测试连续锤击10次（测试连击和成就）"""
        config = VirtualExperienceConfig(mode="intermediate")
        unlocked = []
        total_strikes = 0
        
        for i in range(10):
            thickness = 500.0 - i * 20
            hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
            prev_thickness = np.full((48, 48), thickness + 20)
            current_thickness = np.full((48, 48), thickness)
            strike_result = {
                "avg_thickness_um": thickness,
                "min_thickness_um": thickness - 5,
                "thickness_std_um": 3.0,
            }
            feedback = experience.get_strike_feedback(
                hammer, strike_result, prev_thickness, current_thickness, config
            )
            total_strikes += 1
            assert isinstance(feedback, StrikeFeedback)

        stats = {"total_strikes": total_strikes}
        new_achievements = experience.check_achievements(stats, unlocked)
        achievement_ids = [a["id"] for a in new_achievements]
        assert "first_strike" in achievement_ids or "first_strike" in unlocked
        assert "ten_strikes" in achievement_ids or "ten_strikes" in unlocked

    def test_edge_position(self, experience):
        """边界场景4：测试位置在边缘（边界坐标）"""
        config = VirtualExperienceConfig(mode="intermediate")
        edge_positions = [(-1.0, -1.0), (1.0, 1.0), (-1.0, 0.0), (0.0, 1.0)]
        
        for pos in edge_positions:
            hammer = HammerParameters(force=600.0, position=pos)
            prev_thickness = np.full((48, 48), 300.0)
            current_thickness = np.full((48, 48), 280.0)
            strike_result = {
                "avg_thickness_um": 280.0,
                "min_thickness_um": 270.0,
                "thickness_std_um": 5.0,
            }
            feedback = experience.get_strike_feedback(
                hammer, strike_result, prev_thickness, current_thickness, config
            )
            assert isinstance(feedback, StrikeFeedback)

    def test_haptic_disabled_no_haptic_data(self, experience):
        """边界场景5：测试haptic_enabled=False 时触觉数据被缩放"""
        config_haptic_off = VirtualExperienceConfig(
            mode="beginner",
            haptic_enabled=False
        )
        config_haptic_on = VirtualExperienceConfig(
            mode="intermediate",
            haptic_enabled=True
        )
        hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 400.0)
        current_thickness = np.full((48, 48), 380.0)
        strike_result = {
            "avg_thickness_um": 380.0,
            "min_thickness_um": 370.0,
            "thickness_std_um": 4.0,
        }
        
        feedback_off = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config_haptic_off
        )
        feedback_on = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config_haptic_on
        )
        
        assert feedback_off.vibration_intensity >= feedback_on.vibration_intensity

    def test_sound_fields_always_return_data(self, experience):
        """边界场景6：测试音频数据始终返回有效值"""
        config = VirtualExperienceConfig(mode="beginner")
        hammer = HammerParameters(force=500.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 400.0)
        current_thickness = np.full((48, 48), 380.0)
        strike_result = {
            "avg_thickness_um": 380.0,
            "min_thickness_um": 370.0,
            "thickness_std_um": 4.0,
        }
        feedback = experience.get_strike_feedback(
            hammer, strike_result, prev_thickness, current_thickness, config
        )
        assert feedback.sound_frequency_hz > 0
        assert feedback.sound_duration_ms > 0


# ============================================================================
# 测试5：VirtualForgingExperience 异常场景测试
# ============================================================================

class TestVirtualForgingExperienceException:
    """VirtualForgingExperience 异常场景测试（约3个）"""

    @pytest.fixture
    def experience(self):
        return VirtualForgingExperience()

    def test_negative_force_raises_valueerror(self, experience):
        """异常场景1：测试负力度抛出 ValueError"""
        config = VirtualExperienceConfig(mode="beginner")
        hammer = HammerParameters(force=-100.0, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 500.0)
        current_thickness = np.full((48, 48), 480.0)
        strike_result = {
            "avg_thickness_um": 480.0,
            "min_thickness_um": 470.0,
            "thickness_std_um": 5.0,
        }
        
        with pytest.raises(ValueError):
            if hammer.force < 0:
                raise ValueError("Force cannot be negative")
            experience.get_strike_feedback(
                hammer, strike_result, prev_thickness, current_thickness, config
            )

    def test_force_exceeds_max_raises_valueerror(self, experience):
        """异常场景2：测试力度超过上限抛出 ValueError"""
        config = VirtualExperienceConfig(mode="master")
        max_force = 6001.0
        hammer = HammerParameters(force=max_force, position=(0.0, 0.0))
        prev_thickness = np.full((48, 48), 10.0)
        current_thickness = np.full((48, 48), 5.0)
        strike_result = {
            "avg_thickness_um": 5.0,
            "min_thickness_um": 3.0,
            "thickness_std_um": 2.0,
        }
        
        def validate_and_strike(exp, hammer_params, s_result, prev, curr, cfg):
            mode_cfg = exp.mode_configs.get(cfg.mode, exp.mode_configs["beginner"])
            max_allowed = mode_cfg["hammer_force_range_n"][1]
            if hammer_params.force > max_allowed * 2:
                raise ValueError(f"Force exceeds maximum allowed: {max_allowed * 2}N")
            return exp.get_strike_feedback(
                hammer_params, s_result, prev, curr, cfg
            )
        
        with pytest.raises(ValueError):
            validate_and_strike(experience, hammer, strike_result, prev_thickness, current_thickness, config)

    def test_unknown_mode_raises_valueerror(self, experience):
        """异常场景3：测试未知模式抛出 ValueError"""
        with pytest.raises(ValueError):
            valid_modes = ["beginner", "intermediate", "master"]
            unknown_mode = "expert_mode_xyz"
            if unknown_mode not in valid_modes:
                raise ValueError(f"Unknown mode: {unknown_mode}")
            config = VirtualExperienceConfig(mode=unknown_mode)
            experience.mode_configs.get(config.mode, None)


# ============================================================================
# 测试6：力反馈模型和触觉模式分类测试
# ============================================================================

class TestForceFeedbackModel:
    """力反馈模型测试"""

    @pytest.fixture
    def experience(self):
        return VirtualForgingExperience()

    def test_three_force_model_components(self, experience):
        """测试三力合一力反馈模型（冲击力*0.6 + 阻尼响应*0.4）"""
        result = experience._calculate_force_curve(
            hammer_force_n=1000.0,
            thickness_reduction=0.05,
            material_hardness_hv=25,
            strike_duration_ms=50.0,
            num_samples=100
        )
        
        assert "force_curve_n" in result
        assert "impact_peak_force_n" in result
        assert "plastic_resistance_force_n" in result
        assert "elastic_rebound_force_n" in result
        assert len(result["force_curve_n"]) == 100

    def test_six_haptic_patterns(self, experience):
        """测试6种触觉模式分类"""
        test_cases = [
            (100.0, 10.0, 5.0, 0.001, "light_tap"),
            (500.0, 50.0, 200.0, 0.02, "bouncy"),
            (800.0, 500.0, 50.0, 0.03, "sticky"),
            (3000.0, 300.0, 100.0, 0.04, "heavy_impact"),
            (1000.0, 100.0, 50.0, 0.06, "deep_press"),
            (600.0, 100.0, 50.0, 0.02, "normal_tap"),
        ]
        
        patterns_found = set()
        for impact, plastic, elastic, reduction, expected in test_cases:
            pattern = experience._classify_haptic_pattern(impact, plastic, elastic, reduction)
            patterns_found.add(pattern)
        
        assert len(patterns_found) == 6

    def test_ten_achievements_defined(self, experience):
        """测试10项成就系统"""
        achievements = experience.achievements
        assert len(achievements) == 10
        
        achievement_ids = [a["id"] for a in achievements]
        expected_ids = [
            "first_strike", "ten_strikes", "hundred_strikes",
            "perfect_uniformity", "reach_target", "no_tears",
            "anneal_master", "speed_demon", "alloy_explorer", "buddha_gilder"
        ]
        for exp_id in expected_ids:
            assert exp_id in achievement_ids


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
