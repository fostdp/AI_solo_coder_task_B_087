"""
金箔锻制工艺仿真系统 - FastAPI API网关
基于模块化+Redis Pub/Sub架构重构

模块划分:
  - dtu_receiver:     传感器数据采集与校验
  - plasticity_simulator: 塑性变形计算
  - rl_optimizer_module:  强化学习路径优化
  - alarm_ws:        告警评估与WebSocket推送

通信方式:
  - 同步路径: API直接调用模块方法 (性能优先)
  - 异步路径: Redis Pub/Sub (解耦, 可独立部署)
"""
import sys
import os
import time
import json
import asyncio
import threading
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from enum import Enum

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Query,
    Body,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from physics.physics_model import (
    HammerParameters,
    AlloyComposition,
    ProcessComparisonEngine,
    ProcessComparisonResult,
    BuddhaGildingSimulator,
    BuddhaGildingConfig,
    VirtualForgingExperience,
    VirtualExperienceConfig,
    StrikeFeedback,
    get_alloy_composition,
    compare_alloys,
)
from modules.common import RedisBus, REDIS_CHANNELS, load_material_config, load_rl_config
from modules.dtu_receiver import DtuReceiver
from modules.plasticity_simulator import PlasticitySimulator
from modules.rl_optimizer_module import RlOptimizerModule
from modules.alarm_ws import AlarmWsService

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS


INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "gold-foil-simulation-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "craftsman-research")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "gold-foil-data")

FRACTURE_THRESHOLD_UM = 0.1
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


class StrikeMode(str, Enum):
    MANUAL = "manual"
    HEURISTIC = "heuristic"
    RL = "rl"
    PRETRAINED = "pretrained"


class HammerRequest(BaseModel):
    force_N: float = Field(500.0, ge=100, le=3000, description="锤击力度 (N)")
    position_x_mm: float = Field(0.0, description="锤击X坐标 (mm)")
    position_y_mm: float = Field(0.0, description="锤击Y坐标 (mm)")
    radius_mm: float = Field(15.0, description="锤头半径 (mm)")


class AnnealRequest(BaseModel):
    temperature_c: float = Field(400.0, ge=100, le=900, description="退火温度 (°C)")
    duration_min: float = Field(10.0, ge=1, le=120, description="退火持续时间 (分钟)")


class SimulationConfig(BaseModel):
    grid_size: int = Field(48, ge=16, le=128, description="物理网格大小")
    initial_thickness_um: float = Field(500.0, ge=100, le=2000, description="初始厚度 (μm)")
    rl_grid_size: int = Field(8, ge=4, le=16, description="RL策略网格大小")
    target_thickness_um: float = Field(0.5, ge=0.05, le=50, description="目标厚度 (μm)")


class AlloySelectRequest(BaseModel):
    alloy_key: str = Field("pure_gold_24k", description="合金配比键名")


class AlloyCompareRequest(BaseModel):
    alloy_keys: List[str] = Field(["pure_gold_24k", "gold_copper_22k", "gold_silver_22k"], description="要对比的合金列表")
    temperature_c: float = Field(25.0, description="环境温度")


class ProcessCompareRequest(BaseModel):
    target_thickness_um: float = Field(0.2, ge=0.01, le=10, description="目标厚度")
    production_area_m2: float = Field(10.0, ge=1, description="生产面积")
    use_case: str = Field("buddha_gilding", description="应用场景: buddha_gilding/decoration/jewelry/architecture")


class BuddhaGildingRequest(BaseModel):
    buddha_type: str = Field("meditation", description="佛像类型: meditation/teaching/abhayamudra/guanyin")
    adhesive_type: str = Field("gold_leaf_size", description="胶粘剂类型: traditional_animal_glue/modern_acrylic/gold_leaf_size")
    skill_level: float = Field(0.7, ge=0.1, le=1.0, description="工匠技能水平")
    use_current_foil: bool = Field(True, description="是否使用当前仿真金箔的厚度分布")


class VirtualExperienceStrikeRequest(BaseModel):
    force_N: float = Field(500.0, ge=200, le=3000, description="锤击力度")
    position_x_mm: float = Field(0.0, description="X坐标")
    position_y_mm: float = Field(0.0, description="Y坐标")
    radius_mm: float = Field(15.0, description="锤头半径")
    experience_mode: str = Field("beginner", description="体验模式: beginner/intermediate/master")


class VirtualExperienceInitRequest(BaseModel):
    mode: str = Field("beginner", description="体验模式")
    alloy_key: str = Field("pure_gold_24k", description="合金配比")
    target_thickness_um: float = Field(0.5, description="目标厚度")


class GoldFoilSystem:
    """系统总成 - 整合所有模块，提供统一API入口"""

    def __init__(self):
        self._lock = threading.Lock()

        self.mat_config = load_material_config()
        self.rl_config_raw = load_rl_config()

        self.redis_bus = RedisBus()

        self.dtu_receiver = DtuReceiver(self.redis_bus)
        self.plasticity = PlasticitySimulator(self.redis_bus)
        self.rl_optimizer = RlOptimizerModule(
            self.redis_bus,
            physics_model=self.plasticity.physics,
        )
        self.alarm_ws = AlarmWsService(self.redis_bus, threshold_um=FRACTURE_THRESHOLD_UM)

        self.strike_history: List[dict] = []
        self.auto_sim_running = False
        self.auto_sim_thread = None

        self.foil_id = "NF-LIVE-001"
        self.craftsman_id = "master_wu"
        self.session_id = self.plasticity.session_id

        self._alloy_config = self.mat_config.get("alloy_compositions", {})
        self._process_config = self.mat_config.get("process_comparison", {})
        self._buddha_config = self.mat_config.get("buddha_gilding", {})
        self._experience_config = self.mat_config.get("virtual_experience", {})

        self.process_comparison_engine = ProcessComparisonEngine(self._process_config)
        self.buddha_gilding_simulator = BuddhaGildingSimulator()
        self.virtual_experience = VirtualForgingExperience()

        self.current_alloy_key = "pure_gold_24k"
        self.current_alloy = get_alloy_composition(self.current_alloy_key, self._alloy_config)

        self.virtual_experience_stats = {
            "total_strikes": 0,
            "anneal_count": 0,
            "max_uniformity": 0.0,
            "target_reached": False,
            "completed_without_tear": True,
            "strikes_in_60s": 0,
            "alloys_tried": [self.current_alloy_key],
            "gilding_completed": False,
        }
        self.achievements_unlocked: List[str] = []
        self.consecutive_good_strikes = 0
        self.last_strike_time = 0.0
        self.experience_session_start = time.time()

        self._init_influxdb()

    def _init_influxdb(self):
        try:
            self.influx_client = influxdb_client.InfluxDBClient(
                url=INFLUXDB_URL,
                token=INFLUXDB_TOKEN,
                org=INFLUXDB_ORG
            )
            self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.influx_client.query_api()
            self.influxdb_available = True
        except Exception as e:
            print(f"[WARN] InfluxDB不可用: {e}")
            self.influxdb_available = False
            self.influx_client = None
            self.write_api = None
            self.query_api = None

    def apply_manual_strike(self, hammer: HammerParameters) -> dict:
        with self._lock:
            result = self.plasticity.apply_strike_direct(hammer)
            thickness_data = self.plasticity.physics.get_thickness_distribution()
            fracture_risk = self.plasticity.physics.check_fracture_risk(FRACTURE_THRESHOLD_UM)

            self._persist_strike(result, thickness_data, fracture_risk)

            response = {
                "strike": result,
                "metrics": thickness_data["metrics"],
                "fracture_risk": fracture_risk,
                "timestamp": datetime.now().isoformat(),
            }

            self._record_and_check_alert(response, fracture_risk)

            self.redis_bus.publish(REDIS_CHANNELS["strike_result"], {
                "strike": result,
                "foil_id": self.foil_id,
                "session_id": self.session_id,
                "timestamp": time.time(),
            })
            self.redis_bus.publish(REDIS_CHANNELS["thickness_updated"], {
                "thickness_distribution": thickness_data,
                "metrics": thickness_data["metrics"],
                "timestamp": time.time(),
            })

            return response

    def apply_rl_strike(self, mode_str: str = "heuristic") -> dict:
        with self._lock:
            action, strike_result, reward, fracture_risk = self.rl_optimizer.step_with_physics(
                mode=self._resolve_action_type(mode_str)
            )
            thickness_data = self.plasticity.physics.get_thickness_distribution()

            self._persist_strike(
                strike_result,
                thickness_data,
                fracture_risk,
                rl_action=action,
                rl_reward=reward,
            )

            response = {
                "action": {
                    "force_N": action.force,
                    "position_mm": list(action.position),
                    "radius_mm": action.radius_mm,
                },
                "strike": strike_result,
                "metrics": thickness_data["metrics"],
                "fracture_risk": fracture_risk,
                "rl_reward": reward,
                "rl_stats": self.rl_optimizer.get_policy_stats(),
                "timestamp": datetime.now().isoformat(),
            }

            self._record_and_check_alert(response, fracture_risk)

            self.redis_bus.publish(REDIS_CHANNELS["strike_result"], {
                "strike": strike_result,
                "action": {"force_N": action.force, "position_mm": list(action.position)},
                "rl_reward": reward,
                "foil_id": self.foil_id,
                "session_id": self.session_id,
                "timestamp": time.time(),
            })
            self.redis_bus.publish(REDIS_CHANNELS["thickness_updated"], {
                "thickness_distribution": thickness_data,
                "metrics": thickness_data["metrics"],
                "timestamp": time.time(),
            })

            return response

    def _record_and_check_alert(self, response: dict, fracture_risk: dict):
        self.strike_history.append(response)
        if len(self.strike_history) > 1000:
            self.strike_history = self.strike_history[-1000:]

        if fracture_risk["risk_level"] != "none":
            alert = {
                "type": "fracture_warning",
                "level": fracture_risk["risk_level"],
                "message": f"厚度低于{FRACTURE_THRESHOLD_UM}μm，破裂风险：{fracture_risk['risk_level'].upper()}",
                "risk": fracture_risk,
                "timestamp": datetime.now().isoformat(),
            }
            self.alarm_ws.evaluator.alert_history.append(alert)
            response["alert"] = alert
            self.redis_bus.publish(REDIS_CHANNELS["alarm_triggered"], alert)

    def _persist_strike(self, strike_result, thickness_data, fracture_risk,
                       rl_action=None, rl_reward=0.0):
        if not self.influxdb_available or self.write_api is None:
            return

        now = datetime.now(timezone.utc)

        try:
            metrics_point = influxdb_client.Point("forging_metrics") \
                .tag("foil_id", self.foil_id) \
                .tag("session_id", self.session_id) \
                .tag("craftsman", self.craftsman_id) \
                .field("hammer_force", strike_result["hammer_force_N"]) \
                .field("temperature", strike_result["avg_temperature_c"]) \
                .field("avg_thickness", strike_result["avg_thickness_um"]) \
                .field("min_thickness", strike_result["min_thickness_um"]) \
                .field("max_thickness", strike_result["max_thickness_um"]) \
                .field("thickness_std", strike_result["thickness_std_um"]) \
                .field("elongation_rate", strike_result["elongation_rate"]) \
                .field("total_elongation", strike_result["total_elongation"]) \
                .time(now)

            uniformity = thickness_data["metrics"]
            uniform_point = influxdb_client.Point("uniformity_metrics") \
                .tag("foil_id", self.foil_id) \
                .tag("session_id", self.session_id) \
                .field("coefficient_of_variation", uniformity["coefficient_of_variation"]) \
                .field("uniformity_within_5pct", uniformity["uniformity_within_5pct"]) \
                .field("uniformity_within_10pct", uniformity["uniformity_within_10pct"]) \
                .field("range_ratio", uniformity["range_ratio"]) \
                .time(now)

            risk_point = influxdb_client.Point("fracture_risk") \
                .tag("foil_id", self.foil_id) \
                .tag("session_id", self.session_id) \
                .tag("risk_level", fracture_risk["risk_level"]) \
                .field("risk_count", fracture_risk["risk_count"]) \
                .field("risk_fraction", fracture_risk["risk_fraction"]) \
                .field("min_thickness_um", fracture_risk["min_thickness_um"]) \
                .time(now)

            points = [metrics_point, uniform_point, risk_point]

            if rl_action is not None:
                rl_point = influxdb_client.Point("rl_optimization") \
                    .tag("foil_id", self.foil_id) \
                    .tag("session_id", self.session_id) \
                    .field("rl_reward", rl_reward) \
                    .field("rl_action_force_N", rl_action.force) \
                    .field("rl_action_x_mm", rl_action.position[0]) \
                    .field("rl_action_y_mm", rl_action.position[1]) \
                    .time(now)
                points.append(rl_point)

            self.write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=points)
        except Exception as e:
            print(f"[WARN] 写入InfluxDB失败: {e}")

    def apply_annealing(self, temp_c, duration_min) -> dict:
        with self._lock:
            result = self.plasticity.physics.apply_annealing(temp_c, duration_min)
            self.redis_bus.publish(REDIS_CHANNELS["system_event"], {
                "type": "anneal_complete",
                "result": result,
                "timestamp": time.time(),
            })
            return {
                "annealing": result,
                "metrics": self.plasticity.physics.get_uniformity_metrics(),
                "timestamp": datetime.now().isoformat(),
            }

    def reset(self, config: SimulationConfig = None):
        with self._lock:
            self.plasticity.reset()
            self.rl_optimizer.session.prev_metrics = None
            self.rl_optimizer.session.prev_state = None
            self.rl_optimizer.session.current_episode_reward = 0.0
            self.rl_optimizer.session.step_count = 0
            self.alarm_ws.evaluator.reset()

            self.session_id = self.plasticity.session_id
            self.strike_history = []

            self.redis_bus.publish(REDIS_CHANNELS["system_event"], {
                "type": "reset",
                "session_id": self.session_id,
                "timestamp": time.time(),
            })

    def get_state(self) -> dict:
        with self._lock:
            state = self.plasticity.get_state()
            state["craftsman"] = self.craftsman_id
            state["auto_sim_running"] = self.auto_sim_running
            state["recent_alerts"] = self.alarm_ws.get_alert_history(20)
            state["rl_stats"] = self.rl_optimizer.get_policy_stats()
            return state

    def get_thickness_viz(self) -> dict:
        with self._lock:
            return self.plasticity.get_thickness_viz()

    def get_mesh_quality(self) -> dict:
        with self._lock:
            return self.plasticity.get_mesh_quality()

    def trigger_pretrain_async(self, num_demos=20, steps_per_demo=40, pretrain_epochs=40):
        return self.rl_optimizer.trigger_pretrain_async(
            num_demos=num_demos,
            steps_per_demo=steps_per_demo,
            pretrain_epochs=pretrain_epochs,
        )

    def _resolve_action_type(self, mode: str):
        from rl.rl_optimizer import ActionType
        if mode == "pretrained":
            if not self.rl_optimizer.session.policy.is_pretrained:
                try:
                    self.rl_optimizer.trigger_pretrain_async()
                except Exception:
                    pass
            return ActionType.PRETRAINED
        if mode == "rl":
            return ActionType.Q_LEARNING
        return ActionType.HEURISTIC

    def set_alloy_composition(self, alloy_key: str) -> dict:
        """设置当前合金配比"""
        with self._lock:
            alloy = get_alloy_composition(alloy_key, self._alloy_config)
            if alloy is None:
                raise ValueError(f"未知合金配比: {alloy_key}")

            self.current_alloy = alloy
            self.current_alloy_key = alloy_key

            mat_props = alloy.to_material_properties()
            self.plasticity.physics.material = mat_props
            self.plasticity.physics.reset()

            if alloy_key not in self.virtual_experience_stats["alloys_tried"]:
                self.virtual_experience_stats["alloys_tried"].append(alloy_key)

            return {
                "message": f"已切换至 {alloy.name}",
                "alloy": {
                    "key": alloy.key,
                    "name": alloy.name,
                    "composition": {
                        "gold_pct": alloy.gold_ratio * 100,
                        "copper_pct": alloy.copper_ratio * 100,
                        "silver_pct": alloy.silver_ratio * 100,
                    },
                    "ductility_metrics": alloy.get_ductility_metrics(),
                    "material_properties": {
                        "youngs_modulus_gpa": mat_props.youngs_modulus,
                        "yield_strength_mpa": mat_props.yield_strength,
                        "ultimate_strength_mpa": mat_props.ultimate_strength,
                        "density_kgm3": mat_props.density,
                        "recrystallization_temp_c": mat_props.recrystallization_temp,
                        "melting_point_c": mat_props.melting_point,
                    },
                    "color_rgb": list(alloy.color_rgb),
                    "historical_period": alloy.historical_period,
                    "typical_uses": alloy.typical_uses,
                    "description": alloy.description,
                },
            }

    def get_alloy_list(self) -> dict:
        """获取所有可用合金配比列表"""
        with self._lock:
            alloys = []
            for key, cfg in self._alloy_config.items():
                alloy = get_alloy_composition(key, self._alloy_config)
                if alloy:
                    alloys.append({
                        "key": key,
                        "name": alloy.name,
                        "composition": {
                            "gold_pct": alloy.gold_ratio * 100,
                            "copper_pct": alloy.copper_ratio * 100,
                            "silver_pct": alloy.silver_ratio * 100,
                        },
                        "malleability_factor": alloy.malleability_factor,
                        "hardness_vickers": alloy.hardness_vickers,
                        "color_rgb": list(alloy.color_rgb),
                        "historical_period": alloy.historical_period,
                        "typical_uses": alloy.typical_uses,
                        "description": alloy.description,
                    })
            return {
                "current_alloy_key": self.current_alloy_key,
                "alloys": sorted(alloys, key=lambda a: -a["composition"]["gold_pct"]),
            }

    def compare_alloys(self, alloy_keys: List[str], temperature_c: float = 25.0) -> dict:
        """对比多种合金性能"""
        with self._lock:
            return compare_alloys(alloy_keys, self._alloy_config)

    def compare_processes(
        self,
        target_thickness_um: float = 0.2,
        production_area_m2: float = 10.0,
        use_case: str = "buddha_gilding",
    ) -> dict:
        """对比古代锻制 vs 现代真空镀膜 vs 现代电镀工艺"""
        with self._lock:
            result = self.process_comparison_engine.compare_processes(
                target_thickness_um=target_thickness_um,
                production_area_m2=production_area_m2,
                use_case=use_case,
            )
            return {
                "target_thickness_um": target_thickness_um,
                "production_area_m2": production_area_m2,
                "use_case": use_case,
                "ancient_forging": result.ancient,
                "modern_vacuum_coating": result.modern_vacuum,
                "modern_electroplating": result.modern_electroplating,
                "recommendation": result.recommendation,
                "radar_chart_data": result.radar_chart_data,
                "comparison_summary": {
                    "best_uniformity": "真空镀膜 (PVD)",
                    "best_energy_efficiency": "古代锻制",
                    "best_labor_efficiency": "真空镀膜 (PVD)",
                    "lowest_environmental_impact": "古代锻制",
                    "best_surface_quality": "真空镀膜 (PVD)",
                    "lowest_cost": "古代锻制",
                },
            }

    def simulate_buddha_gilding(
        self,
        buddha_type: str = "meditation",
        adhesive_type: str = "gold_leaf_size",
        skill_level: float = 0.7,
        use_current_foil: bool = True,
    ) -> dict:
        """模拟佛像贴金效果"""
        with self._lock:
            config = BuddhaGildingConfig(
                buddha_type=buddha_type,
                adhesive_type=adhesive_type,
                skill_level=skill_level,
            )

            thickness_dist = None
            if use_current_foil:
                thickness_dist = self.plasticity.physics.thickness_um.copy()
                avg_thick = float(np.mean(thickness_dist))
                config.foil_thickness_um = avg_thick

            result = self.buddha_gilding_simulator.simulate_gilding(config, thickness_dist)
            self.virtual_experience_stats["gilding_completed"] = True

            return result

    def virtual_experience_strike(
        self,
        force_N: float,
        position_x_mm: float,
        position_y_mm: float,
        radius_mm: float,
        experience_mode: str = "beginner",
    ) -> dict:
        """虚拟打金体验 - 处理一次锤击"""
        with self._lock:
            now = time.time()

            mode_cfg = self.virtual_experience.mode_configs.get(
                experience_mode, self.virtual_experience.mode_configs["beginner"]
            )

            force_range = mode_cfg["hammer_force_range_n"]
            force_clamped = float(np.clip(force_N, force_range[0], force_range[1]))

            if mode_cfg.get("auto_thickness_protection"):
                min_thick = float(np.min(self.plasticity.physics.thickness_um))
                if min_thick < 0.15:
                    force_clamped = min(force_clamped, force_range[0] + (force_range[1] - force_range[0]) * 0.3)

            hammer_params = HammerParameters(
                force=force_clamped,
                position_x_mm=position_x_mm,
                position_y_mm=position_y_mm,
                radius_mm=radius_mm,
            )

            prev_thickness = self.plasticity.physics.thickness_um.copy()

            strike_result = self.plasticity.apply_strike_direct(hammer_params)
            state = self.get_state()

            exp_config = VirtualExperienceConfig(
                mode=experience_mode,
                target_thickness_um=0.5,
                alloy_key=self.current_alloy_key,
            )

            feedback = self.virtual_experience.get_strike_feedback(
                hammer_params=hammer_params,
                strike_result=strike_result,
                prev_thickness=prev_thickness,
                current_thickness=self.plasticity.physics.thickness_um,
                config=exp_config,
            )

            self.virtual_experience_stats["total_strikes"] += 1

            metrics = state["thickness_distribution"]["metrics"]
            uniformity = metrics["uniformity_within_10pct"]
            if uniformity > self.virtual_experience_stats["max_uniformity"]:
                self.virtual_experience_stats["max_uniformity"] = uniformity

            mean_thick = metrics["mean_thickness_um"]
            if mean_thick <= 0.5:
                self.virtual_experience_stats["target_reached"] = True

            if state["fracture_risk"]["risk_level"] == "high" or strike_result.get("min_thickness_um", 1) < 0.1:
                self.virtual_experience_stats["completed_without_tear"] = False

            if now - self.experience_session_start < 60:
                self.virtual_experience_stats["strikes_in_60s"] = self.virtual_experience_stats["total_strikes"]

            if feedback.quality_score > 0.7:
                self.consecutive_good_strikes += 1
            else:
                self.consecutive_good_strikes = max(0, self.consecutive_good_strikes - 1)

            score_result = self.virtual_experience.calculate_score(
                current_metrics=metrics,
                feedback=feedback,
                config=exp_config,
                consecutive_good_strikes=self.consecutive_good_strikes,
            )

            new_achievements = self.virtual_experience.check_achievements(
                stats=self.virtual_experience_stats,
                unlocked=self.achievements_unlocked,
            )

            self.last_strike_time = now

            return {
                "strike_result": strike_result,
                "state": state,
                "feedback": {
                    "vibration_intensity": feedback.vibration_intensity,
                    "force_feedback": feedback.force_feedback,
                    "visual_effect": feedback.visual_effect,
                    "sound_frequency_hz": feedback.sound_frequency_hz,
                    "sound_duration_ms": feedback.sound_duration_ms,
                    "quality_score": feedback.quality_score,
                    "message": feedback.message,
                },
                "score": score_result,
                "new_achievements": new_achievements,
                "stats": self.virtual_experience_stats.copy(),
                "experience_mode": experience_mode,
                "force_applied_N": force_clamped,
                "force_was_limited": force_clamped != force_N,
            }

    def get_virtual_experience_status(self) -> dict:
        """获取虚拟体验状态"""
        with self._lock:
            return {
                "stats": self.virtual_experience_stats.copy(),
                "achievements_unlocked": self.achievements_unlocked.copy(),
                "all_achievements": self.virtual_experience.achievements,
                "consecutive_good_strikes": self.consecutive_good_strikes,
                "session_duration_sec": time.time() - self.experience_session_start,
                "current_mode": "beginner",
                "mode_configs": self.virtual_experience.mode_configs,
            }

    def reset_virtual_experience(self, mode: str = "beginner", alloy_key: str = "pure_gold_24k") -> dict:
        """重置虚拟打金体验"""
        with self._lock:
            self.virtual_experience_stats = {
                "total_strikes": 0,
                "anneal_count": 0,
                "max_uniformity": 0.0,
                "target_reached": False,
                "completed_without_tear": True,
                "strikes_in_60s": 0,
                "alloys_tried": [alloy_key],
                "gilding_completed": False,
            }
            self.achievements_unlocked = []
            self.consecutive_good_strikes = 0
            self.experience_session_start = time.time()

            self.reset()

            if alloy_key != self.current_alloy_key:
                self.set_alloy_composition(alloy_key)

            return {
                "message": "虚拟体验已重置",
                "mode": mode,
                "alloy_key": alloy_key,
                "tutorial": self.virtual_experience.tutorial_steps,
            }

    def get_tutorial_step(self, step_index: int) -> dict:
        """获取教程步骤"""
        with self._lock:
            step = self.virtual_experience.get_tutorial_step(step_index)
            if step is None:
                raise ValueError(f"无效的教程步骤: {step_index}")
            return step

    def query_history(self, measurement="forging_metrics", window_minutes=60, limit=1000):
        if not self.influxdb_available:
            return self.strike_history[-limit:]

        try:
            start_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
            flux_query = f'''
                from(bucket: "{INFLUXDB_BUCKET}")
                    |> range(start: {int(start_time.timestamp())}, stop: now())
                    |> filter(fn: (r) => r._measurement == "{measurement}")
                    |> filter(fn: (r) => r.foil_id == "{self.foil_id}")
                    |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
                    |> sort(columns: ["_time"], desc: true)
                    |> limit(n: {limit})
            '''
            result = self.query_api.query(flux_query)
            records = []
            for table in result:
                for record in table.records:
                    records.append(record.values)
            return records
        except Exception as e:
            print(f"[ERROR] 查询失败: {e}")
            return self.strike_history[-limit:]


app = FastAPI(
    title="金箔锻制工艺仿真与厚度均匀性分析系统",
    description="基于塑性力学与强化学习的南京金箔锻制工艺研究平台 (v3 模块化架构)",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)

system = GoldFoilSystem()


def get_system():
    return system


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "version": "3.0.0",
        "architecture": "modular-redis-pubsub",
        "timestamp": datetime.now().isoformat(),
        "influxdb": "connected" if system.influxdb_available else "disconnected",
        "redis": "connected" if system.redis_bus.available else "memory_mode",
        "active_ws_connections": system.alarm_ws.connection_count(),
    }


@app.get("/api/state")
async def get_system_state():
    """获取完整系统状态"""
    return system.get_state()


@app.get("/api/visualization/thickness")
async def get_thickness_viz():
    """获取厚度可视化数据"""
    return system.get_thickness_viz()


@app.get("/api/metrics/uniformity")
async def get_uniformity_metrics():
    """获取均匀性指标"""
    state = system.get_state()
    return state["thickness_distribution"]["metrics"]


@app.get("/api/risk/fracture")
async def get_fracture_risk():
    """获取破裂风险"""
    return system.get_state()["fracture_risk"]


@app.post("/api/strike")
async def apply_hammer_strike(req: HammerRequest):
    """手动执行一次锤击"""
    hammer = HammerParameters(
        force=req.force_N,
        position=(req.position_x_mm, req.position_y_mm),
        radius_mm=req.radius_mm,
    )
    result = system.apply_manual_strike(hammer)

    if "alert" in result:
        await system.alarm_ws.ws_manager.broadcast({
            "channel": "alerts",
            "data": result["alert"]
        }, channel="alerts")

    await system.alarm_ws.ws_manager.broadcast({
        "channel": "state_update",
        "data": result
    })

    return result


@app.post("/api/strike/auto")
async def apply_auto_strike(
    mode: StrikeMode = Query(StrikeMode.HEURISTIC, description="锤击模式"),
):
    """自动锤击一步（启发式/强化学习/预训练策略）"""
    result = system.apply_rl_strike(mode_str=mode.value)

    if "alert" in result:
        await system.alarm_ws.ws_manager.broadcast({
            "channel": "alerts",
            "data": result["alert"]
        }, channel="alerts")

    await system.alarm_ws.ws_manager.broadcast({
        "channel": "state_update",
        "data": result
    })

    return result


@app.post("/api/anneal")
async def perform_annealing(req: AnnealRequest):
    """执行退火处理"""
    result = system.apply_annealing(req.temperature_c, req.duration_min)
    await system.alarm_ws.ws_manager.broadcast({
        "channel": "state_update",
        "data": {"event": "annealing", **result}
    })
    return result


@app.post("/api/reset")
async def reset_simulation(config: Optional[SimulationConfig] = None):
    """重置仿真"""
    system.reset(config)
    result = {
        "message": "仿真已重置",
        "state": system.get_state()
    }
    await system.alarm_ws.ws_manager.broadcast({
        "channel": "state_update",
        "data": {"event": "reset", **result}
    })
    return result


@app.get("/api/history")
async def get_history(
    measurement: str = Query("forging_metrics", description="测量类型"),
    window_minutes: int = Query(60, ge=1, le=1440, description="时间窗口(分钟)"),
    limit: int = Query(500, ge=1, le=5000, description="返回条数"),
):
    """查询历史数据"""
    return system.query_history(measurement, window_minutes, limit)


@app.get("/api/alerts")
async def get_alerts(limit: int = Query(50, ge=1, le=500)):
    """获取告警历史"""
    return system.alarm_ws.get_alert_history(limit)


@app.post("/api/simulation/auto/start")
async def start_auto_simulation(
    interval_sec: float = Query(1.0, ge=0.1, le=10.0, description="锤击间隔(秒)"),
    max_strikes: Optional[int] = Query(None, description="最大锤击次数"),
    mode: StrikeMode = Query(StrikeMode.HEURISTIC, description="锤击模式"),
):
    """启动自动仿真循环"""
    if system.auto_sim_running:
        raise HTTPException(status_code=400, detail="自动仿真已在运行")

    system.auto_sim_running = True

    def sim_loop():
        count = 0
        try:
            while system.auto_sim_running:
                if max_strikes and count >= max_strikes:
                    break

                result = system.apply_rl_strike(mode_str=mode.value)

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    if "alert" in result:
                        loop.run_until_complete(system.alarm_ws.ws_manager.broadcast({
                            "channel": "alerts",
                            "data": result["alert"]
                        }, channel="alerts"))

                    loop.run_until_complete(system.alarm_ws.ws_manager.broadcast({
                        "channel": "state_update",
                        "data": result
                    }))
                finally:
                    loop.close()

                if result["fracture_risk"]["risk_level"] == "high":
                    time.sleep(2)

                if result["metrics"]["mean_thickness_um"] < 0.12:
                    break

                time.sleep(interval_sec)
                count += 1
        finally:
            system.auto_sim_running = False

    system.auto_sim_thread = threading.Thread(target=sim_loop, daemon=True)
    system.auto_sim_thread.start()

    return {
        "message": "自动仿真已启动",
        "interval_sec": interval_sec,
        "max_strikes": max_strikes,
        "mode": mode.value,
    }


@app.post("/api/simulation/auto/stop")
async def stop_auto_simulation():
    """停止自动仿真"""
    if not system.auto_sim_running:
        raise HTTPException(status_code=400, detail="自动仿真未在运行")

    system.auto_sim_running = False
    if system.auto_sim_thread:
        system.auto_sim_thread.join(timeout=2)

    return {"message": "自动仿真已停止"}


@app.get("/api/stats/summary")
async def get_stats_summary():
    """统计摘要"""
    state = system.get_state()
    metrics = state["thickness_distribution"]["metrics"]
    risk = state["fracture_risk"]
    rl_stats = state.get("rl_stats", {})

    return {
        "total_strikes": state["total_strikes"],
        "total_elongation": state["total_elongation"],
        "current_thickness": {
            "mean_um": metrics["mean_thickness_um"],
            "std_um": metrics["std_thickness_um"],
            "cv": metrics["coefficient_of_variation"],
            "grid_size": metrics.get("grid_size", state.get("grid_size", 48)),
        },
        "uniformity": {
            "within_5pct": metrics["uniformity_within_5pct"],
            "within_10pct": metrics["uniformity_within_10pct"],
        },
        "fracture_risk": risk,
        "temperature_c": state["temperature_c"],
        "plastic_strain": state["plastic_strain"],
        "alerts_count": len(system.alarm_ws.get_alert_history()),
        "in_progress": state["auto_sim_running"],
        "pretrain": {
            "running": rl_stats.get("pretrain_running", False),
            "report": rl_stats.get("pretrain_report"),
            "is_pretrained": rl_stats.get("is_pretrained", False),
        },
    }


@app.post("/api/rl/pretrain")
async def trigger_pretrain(
    num_demos: int = Query(20, ge=5, le=100, description="演示集数量"),
    steps_per_demo: int = Query(40, ge=10, le=100, description="每集步数"),
    pretrain_epochs: int = Query(50, ge=10, le=200, description="训练轮数"),
):
    """启动强化学习预训练"""
    result = system.trigger_pretrain_async(
        num_demos=num_demos,
        steps_per_demo=steps_per_demo,
        pretrain_epochs=pretrain_epochs,
    )
    return result


@app.get("/api/mesh/quality")
async def get_mesh_quality():
    """自适应网格重划 - 质量诊断报告"""
    return system.get_mesh_quality()


# =============================================================
# 新功能 API 端点：合金配比、工艺对比、佛像贴金、虚拟打金体验
# =============================================================

@app.get("/api/alloys")
async def get_all_alloys():
    """获取所有可用合金配比列表"""
    return system.get_alloy_list()


@app.post("/api/alloys/select")
async def select_alloy(request: AlloySelectRequest):
    """切换当前合金配比"""
    try:
        result = system.set_alloy_composition(request.alloy_key)
        await system.alarm_ws.ws_manager.broadcast({
            "channel": "state_update",
            "data": {"event": "alloy_changed", **result}
        })
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/alloys/compare")
async def compare_alloys_endpoint(request: AlloyCompareRequest):
    """对比多种合金的性能参数"""
    result = system.compare_alloys(request.alloy_keys, request.temperature_c)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/alloys/{alloy_key}/ductility")
async def get_alloy_ductility(
    alloy_key: str,
    temperature_c: float = Query(25.0, ge=0, le=1000, description="温度 (°C)"),
):
    """获取指定合金在特定温度下的延展性指标"""
    alloy = get_alloy_composition(alloy_key, system._alloy_config)
    if alloy is None:
        raise HTTPException(status_code=404, detail=f"未知合金: {alloy_key}")
    return {
        "alloy_key": alloy_key,
        "temperature_c": temperature_c,
        "ductility_metrics": alloy.get_ductility_metrics(temperature_c),
    }


@app.post("/api/process/compare")
async def compare_processes_endpoint(request: ProcessCompareRequest):
    """对比古代锻制 vs 现代真空镀膜 vs 现代电镀工艺"""
    return system.compare_processes(
        target_thickness_um=request.target_thickness_um,
        production_area_m2=request.production_area_m2,
        use_case=request.use_case,
    )


@app.get("/api/process/info")
async def get_process_info():
    """获取三种工艺的详细参数信息"""
    return {
        "ancient_forging": system._process_config.get("ancient_forging", {}),
        "modern_vacuum_coating": system._process_config.get("modern_vacuum_coating", {}),
        "modern_electroplating": system._process_config.get("modern_electroplating", {}),
    }


@app.post("/api/buddha/gilding/simulate")
async def simulate_buddha_gilding_endpoint(request: BuddhaGildingRequest):
    """模拟佛像贴金效果"""
    try:
        result = system.simulate_buddha_gilding(
            buddha_type=request.buddha_type,
            adhesive_type=request.adhesive_type,
            skill_level=request.skill_level,
            use_current_foil=request.use_current_foil,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/buddha/types")
async def get_buddha_types():
    """获取可用佛像类型列表"""
    return {
        "buddha_types": [
            {"key": "meditation", "name": "禅定印佛像", "description": "跏趺静坐，右手结禅定印"},
            {"key": "teaching", "name": "说法印佛像", "description": "右手结说法印，象征讲经说法"},
            {"key": "abhayamudra", "name": "施无畏印佛像", "description": "右手举掌施无畏印，代表拔除众生恐惧"},
            {"key": "guanyin", "name": "观音像", "description": "手持净瓶柳枝，头戴宝冠，装饰璎珞"},
        ],
        "adhesive_types": [
            {"key": "traditional_animal_glue", "name": "传统动物胶", "durability": "50年", "drying": "12小时"},
            {"key": "modern_acrylic", "name": "现代丙烯酸胶", "durability": "15年", "drying": "4小时"},
            {"key": "gold_leaf_size", "name": "金箔专用胶 (柿漆)", "durability": "80年", "drying": "24小时"},
        ],
    }


@app.post("/api/experience/strike")
async def virtual_experience_strike_endpoint(request: VirtualExperienceStrikeRequest):
    """虚拟打金体验 - 处理一次锤击"""
    try:
        result = system.virtual_experience_strike(
            force_N=request.force_N,
            position_x_mm=request.position_x_mm,
            position_y_mm=request.position_y_mm,
            radius_mm=request.radius_mm,
            experience_mode=request.experience_mode,
        )

        if "alert" in result["strike_result"]:
            await system.alarm_ws.ws_manager.broadcast({
                "channel": "alerts",
                "data": result["strike_result"]["alert"]
            }, channel="alerts")

        await system.alarm_ws.ws_manager.broadcast({
            "channel": "state_update",
            "data": {
                "event": "experience_strike",
                **{k: v for k, v in result.items() if k != "state"}
            }
        })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/experience/status")
async def get_virtual_experience_status_endpoint():
    """获取虚拟打金体验状态（成就、统计等）"""
    return system.get_virtual_experience_status()


@app.post("/api/experience/reset")
async def reset_virtual_experience_endpoint(request: VirtualExperienceInitRequest):
    """重置虚拟打金体验"""
    try:
        result = system.reset_virtual_experience(
            mode=request.mode,
            alloy_key=request.alloy_key,
        )
        await system.alarm_ws.ws_manager.broadcast({
            "channel": "state_update",
            "data": {"event": "experience_reset", **result}
        })
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/experience/tutorial/{step_index}")
async def get_tutorial_step_endpoint(step_index: int):
    """获取虚拟体验教程步骤"""
    try:
        return system.get_tutorial_step(step_index)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/experience/achievements")
async def get_all_achievements():
    """获取所有可解锁成就列表"""
    return {
        "achievements": system.virtual_experience.achievements,
        "unlocked": system.achievements_unlocked,
    }


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    channel: str = Query("default", description="订阅频道: default/alerts/state"),
):
    """WebSocket实时推送"""
    initial_state = system.get_state()
    await system.alarm_ws.handle_websocket(websocket, channel, initial_state)


@app.get("/")
async def read_root():
    """服务首页 - 前端页面"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {
        "name": "金箔锻制工艺仿真系统 API",
        "version": "3.0.0",
        "architecture": "modular + redis pub/sub",
        "docs": "/docs",
        "modules": ["dtu_receiver", "plasticity_simulator", "rl_optimizer", "alarm_ws"],
    }


if os.path.exists(FRONTEND_DIR):
    try:
        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("  金箔锻制工艺仿真与厚度均匀性分析系统 v3")
    print("  模块化架构 + Redis Pub/Sub")
    print("=" * 60)
    print(f"  模块: dtu_receiver | plasticity_simulator | rl_optimizer | alarm_ws")
    print(f"  API 文档: http://localhost:8000/docs")
    print(f"  WebSocket: ws://localhost:8000/ws")
    print(f"  Redis:  {'连接' if system.redis_bus.available else '内存模式降级'}")
    print(f"  InfluxDB: {'连接' if system.influxdb_available else '未连接'}")
    print(f"  破裂阈值: {FRACTURE_THRESHOLD_UM}μm")
    print("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
