"""
虚拟打金体验模块 - 提供沉浸式打金箔体验系统

本模块包含完整的虚拟打金体验相关类，支持：
- 多种难度模式（初学者/进阶/大师）
- 三力合一力反馈模型（冲击力、塑性阻力、弹性回复力）
- 实时力-时间曲线计算（100个采样点）
- 6种触觉模式分类
- 成就系统与教程引导
- 多种合金材料支持

主要类：
- VirtualExperienceConfig: 虚拟体验配置
- StrikeFeedback: 锤击反馈数据（含完整力反馈信息）
- VirtualForgingExperience: 虚拟打金体验主类
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class HammerParameters:
    """锤击参数"""
    force: float = 500.0
    position: Tuple[float, float] = (0.0, 0.0)
    radius_mm: float = 15.0
    strike_duration_ms: float = 50.0


@dataclass
class VirtualExperienceConfig:
    """虚拟打金体验配置"""
    mode: str = "beginner"
    haptic_enabled: bool = False
    tutorial_enabled: bool = True
    target_thickness_um: float = 0.5
    alloy_key: str = "pure_gold_24k"


@dataclass
class StrikeFeedback:
    """锤击反馈（用于触觉/力反馈）"""
    vibration_intensity: float
    force_feedback: float
    visual_effect: str
    sound_frequency_hz: float
    sound_duration_ms: int
    quality_score: float
    message: str
    force_curve: list = None
    impact_peak_force_n: float = 0.0
    plastic_resistance_force_n: float = 0.0
    elastic_rebound_force_n: float = 0.0
    damping_coefficient: float = 0.85
    strike_duration_ms: float = 50.0
    haptic_pattern: str = "normal_tap"
    force_rise_time_ms: float = 12.5
    force_decay_time_ms: float = 37.5
    rebound_velocity: float = 0.0


class VirtualForgingExperience:
    """
    公众虚拟打金箔体验系统
    提供多种难度模式、实时反馈、成就系统
    """

    def __init__(self):
        self.mode_configs = self._default_mode_configs()
        self.achievements = self._default_achievements()
        self.tutorial_steps = self._default_tutorial()

    def _default_mode_configs(self) -> Dict:
        return {
            "beginner": {
                "name": "初学者模式",
                "description": "适合首次体验，自动保护防止打穿金箔",
                "hammer_force_range_n": [200, 800],
                "anneal_guidance": True,
                "auto_thickness_protection": True,
                "tutorial_enabled": True,
                "haptic_feedback_enabled": False,
                "strike_interval_min_sec": 0.5,
                "score_multiplier": 0.5,
            },
            "intermediate": {
                "name": "进阶模式",
                "description": "更大的力度范围，可开启力反馈体验",
                "hammer_force_range_n": [300, 1500],
                "anneal_guidance": False,
                "auto_thickness_protection": False,
                "tutorial_enabled": False,
                "haptic_feedback_enabled": True,
                "strike_interval_min_sec": 0.3,
                "score_multiplier": 1.0,
            },
            "master": {
                "name": "大师模式",
                "description": "完整物理引擎，与真实锻制完全一致",
                "hammer_force_range_n": [500, 3000],
                "anneal_guidance": False,
                "auto_thickness_protection": False,
                "tutorial_enabled": False,
                "haptic_feedback_enabled": True,
                "strike_interval_min_sec": 0.2,
                "score_multiplier": 2.0,
                "real_physical_engine": True,
            },
        }

    def _default_achievements(self) -> List[Dict]:
        return [
            {"id": "first_strike", "name": "初体验", "desc": "完成第一次锤击", "points": 10, "icon": "🔨"},
            {"id": "ten_strikes", "name": "小有经验", "desc": "累计锤击10次", "points": 25, "icon": "✨"},
            {"id": "hundred_strikes", "name": "熟能生巧", "desc": "累计锤击100次", "points": 100, "icon": "💪"},
            {"id": "perfect_uniformity", "name": "匠心独具", "desc": "厚度均匀度达到95%以上", "points": 200, "icon": "🏆"},
            {"id": "reach_target", "name": "达标", "desc": "达到目标厚度", "points": 150, "icon": "🎯"},
            {"id": "no_tears", "name": "毫发无损", "desc": "全程无破裂完成锻制", "points": 300, "icon": "🛡️"},
            {"id": "anneal_master", "name": "火候大师", "desc": "正确判断并执行3次退火", "points": 150, "icon": "🔥"},
            {"id": "speed_demon", "name": "神速", "desc": "60秒内完成100次锤击", "points": 200, "icon": "⚡"},
            {"id": "alloy_explorer", "name": "合金探索者", "desc": "体验3种不同合金", "points": 180, "icon": "🔬"},
            {"id": "buddha_gilder", "name": "贴金高手", "desc": "完成一次佛像贴金", "points": 250, "icon": "🏵️"},
        ]

    def _default_tutorial(self) -> List[Dict]:
        return [
            {"step": 1, "title": "认识工具", "content": "这是您的锻锤，可以通过鼠标或触控操作控制锤击力度和位置", "duration_sec": 5},
            {"step": 2, "title": "第一次锤击", "content": "点击金箔中央，尝试一次轻锤。观察厚度变化", "duration_sec": 8},
            {"step": 3, "title": "理解厚度", "content": "蓝色区域较薄，红色区域较厚。我们需要让金箔均匀变薄", "duration_sec": 6},
            {"step": 4, "title": "厚处打重锤", "content": "应该在较厚的地方（红色）使用更大的力度", "duration_sec": 6},
            {"step": 5, "title": "退火处理", "content": "当金箔变硬时（加工硬化），需要进行退火处理恢复塑性", "duration_sec": 8},
            {"step": 6, "title": "小心破裂", "content": "避免在同一位置连续重锤，否则金箔会破裂！", "duration_sec": 6},
            {"step": 7, "title": "开始您的创作", "content": "目标：将500μm厚的金片锻打到0.5μm，均匀度90%以上。祝您成功！", "duration_sec": 8},
        ]

    def _calculate_force_curve(
        self,
        hammer_force_n: float,
        thickness_reduction: float,
        material_hardness_hv: float,
        strike_duration_ms: float = 50.0,
        num_samples: int = 100,
    ) -> Dict[str, Any]:
        """
        计算锤击过程的力反馈曲线
        力反馈模型：包含冲击力、塑性变形阻力、弹性回复力、阻尼衰减
        """
        t = np.linspace(0, strike_duration_ms, num_samples)
        t_peak = strike_duration_ms * 0.25

        impact_peak = hammer_force_n * 1.2

        rise_factor = np.exp(-((t - t_peak) ** 2) / (2 * (t_peak / 3) ** 2))
        decay_factor = np.exp(-(t - t_peak) / (strike_duration_ms * 0.3))
        impact_curve = np.where(t < t_peak, rise_factor, decay_factor)
        impact_curve = impact_curve / np.max(impact_curve) * impact_peak

        plastic_resistance = material_hardness_hv * 9.80665 * 0.1
        plastic_activation = 1.0 - np.exp(-thickness_reduction * 50)
        plastic_force = plastic_resistance * plastic_activation

        elastic_modulus = 79e9
        foil_thickness_ratio = 0.1
        elastic_force = elastic_modulus * foil_thickness_ratio * thickness_reduction * 1e-6
        elastic_force = min(elastic_force, hammer_force_n * 0.3)

        damping_coeff = 0.85
        damped_response = np.zeros_like(t)
        for i in range(len(t)):
            if t[i] < t_peak:
                damped_response[i] = impact_curve[i]
            else:
                decay = np.exp(-damping_coeff * (t[i] - t_peak) / (strike_duration_ms * 0.5))
                rebound = elastic_force * np.sin(2 * np.pi * (t[i] - t_peak) / (strike_duration_ms * 0.4))
                damped_response[i] = plastic_force * decay + rebound * decay

        total_force = impact_curve * 0.6 + damped_response * 0.4
        total_force = np.clip(total_force, 0, impact_peak * 1.1)

        peak_idx = int(t_peak / strike_duration_ms * num_samples)
        rise_time = t_peak
        decay_time = strike_duration_ms - t_peak

        rebound_vel = (elastic_force / (hammer_force_n * 0.001)) * 0.1
        rebound_vel = float(np.clip(rebound_vel, 0, 5.0))

        haptic_pattern = self._classify_haptic_pattern(
            impact_peak, plastic_force, elastic_force, thickness_reduction
        )

        return {
            "time_ms": t.tolist(),
            "force_curve_n": total_force.tolist(),
            "impact_peak_force_n": float(impact_peak),
            "plastic_resistance_force_n": float(plastic_force),
            "elastic_rebound_force_n": float(elastic_force),
            "damping_coefficient": float(damping_coeff),
            "strike_duration_ms": float(strike_duration_ms),
            "force_rise_time_ms": float(rise_time),
            "force_decay_time_ms": float(decay_time),
            "haptic_pattern": haptic_pattern,
            "rebound_velocity": rebound_vel,
            "components": {
                "impact": [float(f) for f in impact_curve],
                "plastic": [float(plastic_force * decay) for decay in np.exp(-damping_coeff * (t - t_peak) / (strike_duration_ms * 0.5))],
                "elastic_rebound": [float(elastic_force * np.sin(2 * np.pi * (ti - t_peak) / (strike_duration_ms * 0.4)) * np.exp(-damping_coeff * (ti - t_peak) / (strike_duration_ms * 0.5))) if ti >= t_peak else 0.0 for ti in t],
            }
        }

    def _classify_haptic_pattern(
        self,
        impact_force: float,
        plastic_force: float,
        elastic_force: float,
        reduction: float,
    ) -> str:
        """根据力反馈特征分类触觉模式"""
        plastic_ratio = plastic_force / max(impact_force, 1e-6)
        elastic_ratio = elastic_force / max(impact_force, 1e-6)

        if reduction < 0.005:
            return "light_tap"
        elif elastic_ratio > 0.3:
            return "bouncy"
        elif plastic_ratio > 0.5:
            return "sticky"
        elif impact_force > 2000:
            return "heavy_impact"
        elif reduction > 0.05:
            return "deep_press"
        else:
            return "normal_tap"

    def _get_alloy_hardness(self, alloy_key: str) -> float:
        """获取合金的维氏硬度"""
        alloy_configs = {
            "pure_gold_24k": 25,
            "gold_copper_22k": 60,
            "gold_copper_18k": 120,
            "gold_silver_22k": 45,
            "ternary_alloy_18k": 95,
        }
        return alloy_configs.get(alloy_key, 25)

    def get_strike_feedback(
        self,
        hammer_params: HammerParameters,
        strike_result: Dict,
        prev_thickness: np.ndarray,
        current_thickness: np.ndarray,
        config: VirtualExperienceConfig,
    ) -> StrikeFeedback:
        """
        根据锤击结果生成反馈（视觉、听觉、触觉）
        """
        mode_cfg = self.mode_configs.get(config.mode, self.mode_configs["beginner"])

        avg_thick_after = strike_result.get("avg_thickness_um", 500)
        min_thick_after = strike_result.get("min_thickness_um", 500)
        cv_after = strike_result.get("thickness_std_um", 0) / max(avg_thick_after, 1e-8)

        thickness_reduction = (np.mean(prev_thickness) - avg_thick_after) / max(np.mean(prev_thickness), 1e-8)
        uniformity_improvement = 0
        if prev_thickness.std() > 0:
            cv_before = prev_thickness.std() / prev_thickness.mean()
            uniformity_improvement = (cv_before - cv_after) / max(cv_before, 1e-8)

        force_normalized = (hammer_params.force - mode_cfg["hammer_force_range_n"][0]) / max(
            mode_cfg["hammer_force_range_n"][1] - mode_cfg["hammer_force_range_n"][0], 1e-8
        )

        quality = 0.0
        message = ""

        if min_thick_after < 0.1:
            quality = 0.0
            vibration = 1.0
            feedback_force = -10.0
            visual = "danger"
            sound_freq = 200
            sound_dur = 300
            message = "⚠️ 危险！金箔快要破裂了！"
            if mode_cfg.get("auto_thickness_protection"):
                message += "（自动保护：后续锤击力度将自动降低）"
        elif thickness_reduction < 0.01:
            quality = 0.3
            vibration = 0.2
            feedback_force = 2.0
            visual = "weak"
            sound_freq = 300 + force_normalized * 200
            sound_dur = 150
            message = "力度偏轻，金箔变化不大"
        elif uniformity_improvement > 0.05:
            quality = 0.95
            vibration = 0.5 + force_normalized * 0.3
            feedback_force = 8.0 * force_normalized
            visual = "excellent"
            sound_freq = 600 + force_normalized * 300
            sound_dur = 200
            message = "🌟 太棒了！均匀度大幅提升！"
        elif uniformity_improvement > 0.01:
            quality = 0.75
            vibration = 0.4 + force_normalized * 0.4
            feedback_force = 6.0 * force_normalized
            visual = "good"
            sound_freq = 500 + force_normalized * 250
            sound_dur = 180
            message = "✅ 不错的一击，继续保持！"
        elif cv_after > 0.1 and force_normalized > 0.7:
            quality = 0.4
            vibration = 0.7
            feedback_force = -3.0
            visual = "warning"
            sound_freq = 350
            sound_dur = 200
            message = "⚠️ 这一击可能太厚了，建议打在更厚的区域"
        else:
            quality = 0.6
            vibration = 0.5
            feedback_force = 5.0 * force_normalized
            visual = "normal"
            sound_freq = 450 + force_normalized * 200
            sound_dur = 160
            message = "正常锤击，继续努力"

        if mode_cfg.get("haptic_feedback_enabled"):
            haptic_params = {
                "force_feedback_gain": 0.8,
                "vibration_duration_ms": 100,
                "impact_intensity_factor": 0.6,
            }
            feedback_force *= haptic_params["force_feedback_gain"]
            vibration *= haptic_params["impact_intensity_factor"]

        hardness_hv = self._get_alloy_hardness(config.alloy_key)
        strike_duration = hammer_params.strike_duration_ms or 50.0

        force_curve_result = self._calculate_force_curve(
            hammer_force_n=hammer_params.force,
            thickness_reduction=max(thickness_reduction, 0),
            material_hardness_hv=hardness_hv,
            strike_duration_ms=strike_duration,
        )

        return StrikeFeedback(
            vibration_intensity=float(np.clip(vibration, 0, 1)),
            force_feedback=float(feedback_force),
            visual_effect=visual,
            sound_frequency_hz=float(sound_freq),
            sound_duration_ms=int(sound_dur),
            quality_score=float(quality),
            message=message,
            force_curve=force_curve_result["force_curve_n"],
            impact_peak_force_n=force_curve_result["impact_peak_force_n"],
            plastic_resistance_force_n=force_curve_result["plastic_resistance_force_n"],
            elastic_rebound_force_n=force_curve_result["elastic_rebound_force_n"],
            damping_coefficient=force_curve_result["damping_coefficient"],
            strike_duration_ms=force_curve_result["strike_duration_ms"],
            haptic_pattern=force_curve_result["haptic_pattern"],
            force_rise_time_ms=force_curve_result["force_rise_time_ms"],
            force_decay_time_ms=force_curve_result["force_decay_time_ms"],
            rebound_velocity=force_curve_result["rebound_velocity"],
        )

    def calculate_score(
        self,
        current_metrics: Dict,
        feedback: StrikeFeedback,
        config: VirtualExperienceConfig,
        consecutive_good_strikes: int = 0,
    ) -> Dict:
        """计算玩家得分"""
        mode_cfg = self.mode_configs.get(config.mode, self.mode_configs["beginner"])
        multiplier = mode_cfg.get("score_multiplier", 1.0)

        base_score = feedback.quality_score * 100 * multiplier

        combo_bonus = min(consecutive_good_strikes, 10) * 5 * multiplier

        uniformity = current_metrics.get("uniformity_within_10pct", 0)
        uniformity_bonus = (uniformity - 0.5) * 100 if uniformity > 0.5 else 0

        thickness = current_metrics.get("mean_thickness_um", 500)
        thickness_target = config.target_thickness_um
        thickness_progress = max(0, (500 - thickness) / max(500 - thickness_target, 1e-8))
        thickness_bonus = thickness_progress * 50 * multiplier

        total_score = base_score + combo_bonus + uniformity_bonus + thickness_bonus

        return {
            "base_score": float(base_score),
            "combo_bonus": float(combo_bonus),
            "uniformity_bonus": float(uniformity_bonus),
            "thickness_bonus": float(thickness_bonus),
            "total_score": float(total_score),
            "multiplier": float(multiplier),
            "consecutive_good_strikes": consecutive_good_strikes,
        }

    def check_achievements(
        self,
        stats: Dict,
        unlocked: List[str],
    ) -> List[Dict]:
        """检查是否达成新成就"""
        new_achievements = []
        for ach in self.achievements:
            if ach["id"] in unlocked:
                continue

            unlocked_now = False
            if ach["id"] == "first_strike" and stats.get("total_strikes", 0) >= 1:
                unlocked_now = True
            elif ach["id"] == "ten_strikes" and stats.get("total_strikes", 0) >= 10:
                unlocked_now = True
            elif ach["id"] == "hundred_strikes" and stats.get("total_strikes", 0) >= 100:
                unlocked_now = True
            elif ach["id"] == "perfect_uniformity" and stats.get("max_uniformity", 0) >= 0.95:
                unlocked_now = True
            elif ach["id"] == "reach_target" and stats.get("target_reached", False):
                unlocked_now = True
            elif ach["id"] == "no_tears" and stats.get("completed_without_tear", False):
                unlocked_now = True
            elif ach["id"] == "anneal_master" and stats.get("anneal_count", 0) >= 3:
                unlocked_now = True
            elif ach["id"] == "speed_demon" and stats.get("strikes_in_60s", 0) >= 100:
                unlocked_now = True
            elif ach["id"] == "alloy_explorer" and len(stats.get("alloys_tried", [])) >= 3:
                unlocked_now = True
            elif ach["id"] == "buddha_gilder" and stats.get("gilding_completed", False):
                unlocked_now = True

            if unlocked_now:
                new_achievements.append(ach)
                unlocked.append(ach["id"])

        return new_achievements

    def get_tutorial_step(self, step_index: int) -> Optional[Dict]:
        """获取教程步骤"""
        if 0 <= step_index < len(self.tutorial_steps):
            return self.tutorial_steps[step_index]
        return None
