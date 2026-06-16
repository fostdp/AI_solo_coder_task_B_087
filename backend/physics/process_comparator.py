"""
工艺对比分析模块

本模块提供古代金箔锻制工艺与现代真空镀膜、电镀工艺的对比分析功能。
包含工艺参数定义、多维度评分体系以及雷达图数据生成。

主要功能：
- 工艺参数数据类：定义古代锻制和现代真空镀膜的工艺参数
- 对比结果数据类：封装对比结果
- 对比分析引擎：多维度工艺对比、加权评分、推荐建议
"""
import numpy as np
import json
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class ProcessParameters:
    """工艺参数基类"""
    name: str = ""
    process_type: str = ""


@dataclass
class AncientForgingParams(ProcessParameters):
    """古代锻制工艺参数"""
    temperature_c: float = 450.0
    hammer_force_n: float = 500.0
    strike_count: int = 1000
    foil_thickness_um: float = 0.2
    area_cm2: float = 100.0
    anneal_interval_strikes: int = 70
    anneal_temperature_c: float = 450.0
    anneal_duration_min: float = 10.0
    hammer_force_profile: str = "nanjing_wujin"
    strike_path: str = "center_out"

    def __post_init__(self):
        self.process_type = "ancient_forging"
        if not self.name:
            self.name = "古代锻制工艺"


@dataclass
class VacuumCoatingParams(ProcessParameters):
    """真空镀膜工艺参数"""
    deposition_rate_nm_s: float = 0.333
    base_pressure_pa: float = 1e-3
    substrate_temp_c: float = 150.0
    power_w: float = 5000.0
    argon_flow_sccm: float = 20.0
    target_thickness_um: float = 0.1
    deposition_rate_um_per_min: float = 0.02
    substrate_temperature_c: float = 150.0
    bias_voltage_v: float = -100.0
    argon_pressure_pa: float = 0.5
    power_kw: float = 5.0

    def __post_init__(self):
        self.process_type = "modern_vacuum_coating"
        if not self.name:
            self.name = "真空镀膜工艺"
        self.deposition_rate_um_per_min = self.deposition_rate_nm_s * 60 / 1000
        self.substrate_temperature_c = self.substrate_temp_c
        self.power_kw = self.power_w / 1000.0
        self.argon_pressure_pa = self.argon_flow_sccm * 0.025


@dataclass
class ProcessComparisonResult:
    """工艺对比结果"""
    ancient: dict
    modern_vacuum: dict
    modern_electroplating: dict
    recommendation: str = ""
    radar_chart_data: dict = field(default_factory=dict)


class ProcessComparisonEngine:
    """
    古代金箔锻制 vs 现代真空镀膜 vs 现代电镀 工艺对比分析引擎
    """

    def __init__(self, config_path: Optional[str] = None, config: Optional[Dict] = None):
        if config is not None:
            self.config = config
        elif config_path is not None and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
        else:
            self.config = self._default_config()

    @property
    def result_key_map(self) -> Dict[str, str]:
        """工艺键到结果键的映射"""
        return {
            "ancient_forging": "ancient",
            "modern_vacuum_coating": "modern_vacuum",
            "modern_electroplating": "modern_electroplating",
        }

    def get_process_metrics(self, process_key: str) -> dict:
        """获取单个工艺的指标"""
        if process_key not in self.result_key_map:
            raise KeyError(f"未知的工艺键: {process_key}")
        
        result_key = self.result_key_map[process_key]
        result = self.compare_processes(target_thickness_um=1.0, area_cm2=100.0)
        
        process_data = getattr(result, result_key)
        return {
            "uniformity_error_pct": process_data["uniformity_error_pct"],
            "total_energy_kwh": process_data["total_energy_kwh"],
            "total_time_h": process_data.get("total_labor_hours", 0),
            "estimated_cost_cny": process_data["estimated_total_cost_cny"],
            "environmental_impact_score": process_data["environmental_impact_score"],
            "surface_roughness_um": process_data["surface_roughness_um"],
            "material_utilization_pct": process_data["material_utilization_pct"],
            "overall_score": process_data["weighted_total_score"],
        }

    def validate_params(self, params: ProcessParameters) -> bool:
        """验证工艺参数的有效性"""
        if not isinstance(params, ProcessParameters):
            return False
        
        if isinstance(params, AncientForgingParams):
            if params.temperature_c < 0 or params.temperature_c > 2000:
                return False
            if params.hammer_force_n <= 0:
                return False
            if params.strike_count <= 0:
                return False
            if params.foil_thickness_um <= 0:
                return False
            if params.area_cm2 < 0:
                return False
            return True
        
        if isinstance(params, VacuumCoatingParams):
            if params.deposition_rate_nm_s <= 0:
                return False
            if params.base_pressure_pa < 0:
                return False
            if params.substrate_temp_c < -273.15 or params.substrate_temp_c > 2000:
                return False
            if params.power_w < 0:
                return False
            if params.argon_flow_sccm < 0:
                return False
            return True
        
        return True

    def _default_config(self) -> Dict:
        return {
            "ancient_forging": {
                "max_thickness_reduction": 0.999,
                "min_achievable_thickness_um": 0.08,
                "uniformity_error_pct": 5.0,
                "energy_consumption_kwh_per_m2": 8.5,
                "labor_hours_per_m2": 120,
                "environmental_impact_score": 3,
                "surface_roughness_um": 0.02,
                "material_utilization_pct": 98,
                "capital_cost_factor": 0.1,
                "maintenance_cost_factor": 0.05,
            },
            "modern_vacuum_coating": {
                "max_thickness_reduction": 1.0,
                "min_achievable_thickness_um": 0.01,
                "uniformity_error_pct": 0.5,
                "energy_consumption_kwh_per_m2": 45.0,
                "labor_hours_per_m2": 2.5,
                "environmental_impact_score": 7,
                "surface_roughness_um": 0.002,
                "material_utilization_pct": 85,
                "capital_cost_factor": 1.0,
                "maintenance_cost_factor": 0.3,
            },
            "modern_electroplating": {
                "max_thickness_reduction": 1.0,
                "min_achievable_thickness_um": 0.1,
                "uniformity_error_pct": 2.0,
                "energy_consumption_kwh_per_m2": 15.0,
                "labor_hours_per_m2": 8.0,
                "environmental_impact_score": 9,
                "surface_roughness_um": 0.01,
                "material_utilization_pct": 75,
                "capital_cost_factor": 0.4,
                "maintenance_cost_factor": 0.15,
            }
        }

    def _normalize_score(self, value: float, min_val: float, max_val: float, higher_is_better: bool = True) -> float:
        """归一化分数到 [0, 1]"""
        normalized = (value - min_val) / (max_val - min_val)
        if not higher_is_better:
            normalized = 1.0 - normalized
        return float(np.clip(normalized, 0, 1))

    def compare_processes(
        self,
        target_thickness_um: float = 0.2,
        area_cm2: Optional[float] = None,
        production_area_m2: Optional[float] = None,
        use_case: str = "buddha_gilding",
    ) -> ProcessComparisonResult:
        """
        对比三种工艺在特定应用场景下的表现

        参数:
            target_thickness_um: 目标金箔厚度 (μm)，必须为非负数
            area_cm2: 生产面积 (cm²)，必须为非负数。与 production_area_m2 二选一，优先使用 area_cm2
            production_area_m2: 生产面积 (m²)，与 area_cm2 二选一
            use_case: 应用场景 (buddha_gilding / decoration / jewelry / architecture)
        
        异常:
            ValueError: 当 target_thickness_um 或 area_cm2 为负数时抛出
        """
        if target_thickness_um < 0:
            raise ValueError(f"目标厚度不能为负数: {target_thickness_um}")
        
        if area_cm2 is not None:
            if area_cm2 < 0:
                raise ValueError(f"面积不能为负数: {area_cm2}")
            production_area_m2 = area_cm2 / 10000.0
        elif production_area_m2 is None:
            production_area_m2 = 10.0
        
        if production_area_m2 < 0:
            raise ValueError(f"生产面积不能为负数: {production_area_m2}")
        
        production_area_m2 = max(production_area_m2, 1e-10)
        use_case_weights = {
            "buddha_gilding": {
                "uniformity": 0.15,
                "min_thickness": 0.10,
                "energy_efficiency": 0.15,
                "labor_efficiency": 0.10,
                "environmental_impact": 0.15,
                "surface_quality": 0.15,
                "material_utilization": 0.10,
                "total_cost": 0.10,
            },
            "decoration": {
                "uniformity": 0.10,
                "min_thickness": 0.15,
                "energy_efficiency": 0.10,
                "labor_efficiency": 0.20,
                "environmental_impact": 0.10,
                "surface_quality": 0.20,
                "material_utilization": 0.05,
                "total_cost": 0.10,
            },
            "jewelry": {
                "uniformity": 0.20,
                "min_thickness": 0.15,
                "energy_efficiency": 0.05,
                "labor_efficiency": 0.10,
                "environmental_impact": 0.10,
                "surface_quality": 0.25,
                "material_utilization": 0.10,
                "total_cost": 0.05,
            },
            "architecture": {
                "uniformity": 0.10,
                "min_thickness": 0.10,
                "energy_efficiency": 0.20,
                "labor_efficiency": 0.20,
                "environmental_impact": 0.10,
                "surface_quality": 0.10,
                "material_utilization": 0.10,
                "total_cost": 0.10,
            },
        }
        weights = use_case_weights.get(use_case, use_case_weights["buddha_gilding"])

        results = {}
        for process_key in ["ancient_forging", "modern_vacuum_coating", "modern_electroplating"]:
            cfg = self.config[process_key]
            can_achieve = target_thickness_um >= cfg["min_achievable_thickness_um"]
            total_energy = cfg["energy_consumption_kwh_per_m2"] * production_area_m2
            total_labor = cfg["labor_hours_per_m2"] * production_area_m2
            total_cost = (
                cfg["capital_cost_factor"] * 10000
                + cfg["maintenance_cost_factor"] * 5000
                + total_energy * 0.8
                + total_labor * 50
            )

            scores = {
                "uniformity": self._normalize_score(
                    100 - cfg["uniformity_error_pct"], 0, 100, True
                ),
                "min_thickness": self._normalize_score(
                    1.0 / cfg["min_achievable_thickness_um"], 1, 100, True
                ) if can_achieve else 0,
                "energy_efficiency": self._normalize_score(
                    cfg["energy_consumption_kwh_per_m2"], 5, 50, False
                ),
                "labor_efficiency": self._normalize_score(
                    cfg["labor_hours_per_m2"], 1, 120, False
                ),
                "environmental_impact": self._normalize_score(
                    cfg["environmental_impact_score"], 1, 10, False
                ),
                "surface_quality": self._normalize_score(
                    1.0 / cfg["surface_roughness_um"], 10, 500, True
                ),
                "material_utilization": self._normalize_score(
                    cfg["material_utilization_pct"], 0, 100, True
                ),
                "total_cost": self._normalize_score(
                    total_cost, 1000, 100000, False
                ),
            }

            weighted_score = sum(scores[k] * weights[k] for k in weights) * 100

            result_key_map = {
                "ancient_forging": "ancient",
                "modern_vacuum_coating": "modern_vacuum",
                "modern_electroplating": "modern_electroplating",
            }
            result_key = result_key_map.get(process_key, process_key)

            results[result_key] = {
                "process_name": cfg.get("name", process_key.replace("_", " ").title()),
                "can_achieve_target": can_achieve,
                "target_thickness_um": target_thickness_um,
                "achievable_thickness_um": cfg["min_achievable_thickness_um"],
                "uniformity_error_pct": cfg["uniformity_error_pct"],
                "total_energy_kwh": float(total_energy),
                "total_labor_hours": float(total_labor),
                "total_time_h": float(total_labor),
                "estimated_total_cost_cny": float(total_cost),
                "estimated_cost_cny": float(total_cost),
                "environmental_impact_score": cfg["environmental_impact_score"],
                "surface_roughness_um": cfg["surface_roughness_um"],
                "material_utilization_pct": cfg["material_utilization_pct"],
                "individual_scores": scores,
                "weighted_total_score": float(weighted_score),
                "overall_score": float(weighted_score),
                "typical_defects": cfg.get("typical_defects", []),
                "quality_control_methods": cfg.get("quality_control", []),
            }

        ancient = results["ancient"]
        vacuum = results.get("modern", results.get("modern_vacuum", {"weighted_total_score": 0}))
        electroplating = results.get("modern_electroplating", {"weighted_total_score": 0})

        scores_dict = {
            "古代锻制": ancient.get("weighted_total_score", 0),
            "真空镀膜": vacuum.get("weighted_total_score", 0),
            "电镀工艺": electroplating.get("weighted_total_score", 0),
        }
        best_process = max(scores_dict, key=scores_dict.get)

        recommendation = f"针对 {use_case} 场景，推荐使用 {best_process}，综合得分 {scores_dict[best_process]:.1f}/100"
        if best_process == "古代锻制" and target_thickness_um < 0.1:
            recommendation += "（注意：厚度小于0.1μm时建议使用真空镀膜）"

        radar_data = {
            "labels": list(weights.keys()),
            "datasets": [
                {
                    "label": "古代锻制",
                    "data": [ancient["individual_scores"].get(k, 0) * 100 for k in weights],
                },
                {
                    "label": "真空镀膜",
                    "data": [vacuum["individual_scores"].get(k, 0) * 100 for k in weights],
                },
                {
                    "label": "电镀工艺",
                    "data": [electroplating["individual_scores"].get(k, 0) * 100 for k in weights],
                },
            ],
        }

        return ProcessComparisonResult(
            ancient=ancient,
            modern_vacuum=vacuum,
            modern_electroplating=electroplating,
            recommendation=recommendation,
            radar_chart_data=radar_data,
        )
