"""
金箔锻制工艺模型 - 基于塑性力学和乌兹铁匠经验
模拟金箔在反复锤击下的延展和厚度变化

== v2 改进 ==
引入自适应网格重划 (Adaptive Remeshing)：
- 基于厚度梯度 + 应变梯度评估网格质量
- 双三次插值进行网格细分/合并，保持物理量守恒
- 自动规避大变形时的网格畸变问题
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, List, Optional
from scipy.ndimage import map_coordinates


@dataclass
class MaterialProperties:
    """金的材料力学参数"""
    youngs_modulus: float = 79.0
    poisson_ratio: float = 0.42
    yield_strength: float = 120.0
    ultimate_strength: float = 210.0
    density: float = 19300.0
    initial_thickness_um: float = 500.0
    work_hardening_coeff: float = 0.45
    work_hardening_exp: float = 0.35
    recrystallization_temp: float = 200.0
    melting_point: float = 1064.0


@dataclass
class HammerParameters:
    """锤击参数"""
    force: float = 500.0
    position: Tuple[float, float] = (0.0, 0.0)
    radius_mm: float = 15.0
    strike_duration_ms: float = 50.0


@dataclass
class RemeshConfig:
    """自适应网格重划配置"""
    enable: bool = True
    check_interval_strikes: int = 8
    min_grid_size: int = 32
    max_grid_size: int = 128
    gradient_threshold: float = 0.15
    strain_gradient_threshold: float = 0.08
    upscale_trigger_ratio: float = 0.08
    downscale_trigger_ratio: float = 0.02


class GoldFoilPhysicsModel:
    """
    金箔锻制物理模型 v2 - 含自适应网格重划
    
    核心方程:
    1. 塑性应变: ε_p = σ_y / E * (σ/σ_y)^n  (Ludwik硬化法则)
    2. 体积不变: h * A = constant
    3. 延展率: λ = sqrt(A_new / A_old)
    4. 厚度分布: 锤击点产生高斯形变核
    5. 自适应网格重划: 基于场梯度评估 + 双三次插值重采样
    """
    
    def __init__(
        self,
        grid_size: int = 64,
        foil_size_mm: float = 150.0,
        material: Optional[MaterialProperties] = None,
        remesh_config: Optional[RemeshConfig] = None,
    ):
        self.initial_grid_size = grid_size
        self.grid_size = grid_size
        self.foil_size_mm = foil_size_mm
        self.material = material or MaterialProperties()
        self.remesh_config = remesh_config or RemeshConfig()
        self.dx = foil_size_mm / grid_size
        self.dy = foil_size_mm / grid_size
        
        self.thickness_um = np.full(
            (grid_size, grid_size),
            self.material.initial_thickness_um,
            dtype=np.float64
        )
        
        self.plastic_strain = np.zeros(
            (grid_size, grid_size),
            dtype=np.float64
        )
        
        self.temperature_c = np.full(
            (grid_size, grid_size),
            25.0,
            dtype=np.float64
        )
        
        self.strike_count = 0
        self.total_elongation = 1.0
        self.hammer_history: List[dict] = []
        self.remesh_history: List[dict] = []
        self.last_remesh_check = 0
    
    def _gaussian_kernel(
        self,
        cx: float,
        cy: float,
        sigma: float
    ) -> np.ndarray:
        """生成2D高斯核，用于模拟锤击形变分布"""
        x = np.linspace(-self.foil_size_mm/2, self.foil_size_mm/2, self.grid_size)
        y = np.linspace(-self.foil_size_mm/2, self.foil_size_mm/2, self.grid_size)
        X, Y = np.meshgrid(x, y)
        
        dist_sq = (X - cx) ** 2 + (Y - cy) ** 2
        kernel = np.exp(-dist_sq / (2 * sigma ** 2))
        return kernel / kernel.max()
    
    def _calc_effective_stress(
        self,
        force: float,
        radius: float,
        local_thickness: float
    ) -> float:
        """计算等效应力 (MPa)"""
        contact_area_m2 = np.pi * (radius * 1e-3) ** 2
        contact_pressure_pa = force / contact_area_m2
        
        dynamic_load_factor = 180.0
        
        thickness_factor = np.clip(
            self.material.initial_thickness_um / local_thickness,
            1.0,
            5.0
        )
        
        effective_stress_mpa = (contact_pressure_pa * dynamic_load_factor) * 1e-6
        effective_stress_mpa *= (0.7 + 0.3 * thickness_factor)
        
        return effective_stress_mpa
    
    def _calc_plastic_strain_increment(
        self,
        effective_stress: float,
        accumulated_strain: float
    ) -> float:
        """根据Ludwik-Hollomon方程计算塑性应变增量"""
        if effective_stress <= self.material.yield_strength:
            return 0.0
        
        strain_ratio = effective_stress / self.material.yield_strength
        target_strain = (strain_ratio ** (1.0 / self.material.work_hardening_exp) - 1.0)
        target_strain *= self.material.work_hardening_coeff
        
        strain_increment = max(0.0, target_strain - accumulated_strain)
        return strain_increment
    
    def _calc_thickness_reduction(
        self,
        plastic_strain_inc: float,
        temp_c: float
    ) -> float:
        """根据塑性应变和温度计算厚度减薄率"""
        temp_factor = 1.0
        
        if temp_c >= self.material.recrystallization_temp:
            temp_ratio = (temp_c - self.material.recrystallization_temp) / \
                         (self.material.melting_point - self.material.recrystallization_temp)
            temp_factor = 1.0 + 0.8 * np.clip(temp_ratio, 0.0, 1.0)
        
        reduction = 1.0 - np.exp(-plastic_strain_inc * temp_factor * 0.7)
        return reduction
    
    # ====== 自适应网格重划核心逻辑 ======
    
    def _compute_field_gradients(self, field: np.ndarray) -> np.ndarray:
        """计算2D标量场的梯度模长 (Sobel算子)"""
        gy, gx = np.gradient(field)
        return np.sqrt(gx ** 2 + gy ** 2)
    
    def _evaluate_mesh_quality(self) -> dict:
        """
        评估当前网格质量，判断是否需要重划
        
        检查:
        1. 厚度梯度异常的像素比例 (太薄/太厚的交界)
        2. 塑性应变梯度异常的像素比例
        3. 网格纵横比（当前是结构化网格，主要看分辨率够不够）
        """
        h_grad = self._compute_field_gradients(self.thickness_um)
        e_grad = self._compute_field_gradients(self.plastic_strain)
        
        h_mean = self.thickness_um.mean() + 1e-8
        e_mean = self.plastic_strain.mean() + 1e-8
        
        h_grad_norm = h_grad / h_mean * self.dx
        e_grad_norm = e_grad / (e_mean + 1e-4) * self.dx
        
        high_h_grad_fraction = float(
            np.sum(h_grad_norm > self.remesh_config.gradient_threshold) / h_grad_norm.size
        )
        high_e_grad_fraction = float(
            np.sum(e_grad_norm > self.remesh_config.strain_gradient_threshold) / e_grad_norm.size
        )
        
        need_upscale = (
            high_h_grad_fraction > self.remesh_config.upscale_trigger_ratio or
            high_e_grad_fraction > self.remesh_config.upscale_trigger_ratio
        )
        
        need_downscale = (
            self.grid_size > self.remesh_config.min_grid_size and
            high_h_grad_fraction < self.remesh_config.downscale_trigger_ratio and
            high_e_grad_fraction < self.remesh_config.downscale_trigger_ratio * 0.5 and
            self.strike_count - self.last_remesh_check > 30
        )
        
        return {
            "high_thickness_gradient_fraction": high_h_grad_fraction,
            "high_strain_gradient_fraction": high_e_grad_fraction,
            "h_grad_max": float(h_grad_norm.max()),
            "e_grad_max": float(e_grad_norm.max()),
            "current_grid_size": self.grid_size,
            "need_upscale": need_upscale,
            "need_downscale": need_downscale,
        }
    
    def _bicubic_resample(
        self,
        field: np.ndarray,
        target_size: int
    ) -> np.ndarray:
        """
        使用双三次插值对2D场进行重采样
        
        保持物理量守恒:
        - 对于厚度场: 保持积分（体积）守恒
        - 对于应变和温度: 保持加权平均
        """
        src_size = field.shape[0]
        if src_size == target_size:
            return field.copy()
        
        src_coords_y = np.linspace(0, src_size - 1, src_size)
        src_coords_x = np.linspace(0, src_size - 1, src_size)
        
        dst_coords_y = np.linspace(0, src_size - 1, target_size)
        dst_coords_x = np.linspace(0, src_size - 1, target_size)
        
        DST_Y, DST_X = np.meshgrid(dst_coords_y, dst_coords_x, indexing='ij')
        
        coords = np.vstack([DST_Y.ravel(), DST_X.ravel()])
        
        resampled = map_coordinates(
            field,
            coords,
            order=3,
            mode='nearest'
        ).reshape(target_size, target_size)
        
        if target_size > src_size:
            src_sum = field.sum()
            dst_sum = resampled.sum()
            if dst_sum > 0:
                resampled *= src_sum / dst_sum
        
        return resampled
    
    def _remesh(self, target_size: int) -> dict:
        """
        执行网格重划，更新所有场量
        
        守恒量:
        - 总体积 = Σ(h_ij * dx * dy)
        - 总内能 (通过温度×厚度加权)
        - 总塑性功 (通过应变×厚度加权)
        """
        target_size = np.clip(
            target_size,
            self.remesh_config.min_grid_size,
            self.remesh_config.max_grid_size
        )
        
        if target_size == self.grid_size:
            return {"action": "noop", "grid_size": self.grid_size}
        
        old_size = self.grid_size
        old_dx = self.dx
        old_volume = float(np.sum(self.thickness_um) * old_dx * self.dy)
        
        old_temp_weighted = float(np.sum(self.temperature_c * self.thickness_um))
        old_strain_weighted = float(np.sum(self.plastic_strain * self.thickness_um))
        
        new_thickness = self._bicubic_resample(self.thickness_um, target_size)
        new_strain = self._bicubic_resample(self.plastic_strain, target_size)
        new_temp = self._bicubic_resample(self.temperature_c, target_size)
        
        new_dx = self.foil_size_mm / target_size
        new_dy = self.foil_size_mm / target_size
        
        new_volume = float(np.sum(new_thickness) * new_dx * new_dy)
        if new_volume > 0:
            volume_correction = old_volume / new_volume
            new_thickness *= volume_correction
        
        new_temp_sum = float(np.sum(new_temp * new_thickness))
        if new_temp_sum > 0:
            temp_correction = old_temp_weighted / new_temp_sum
            new_temp *= temp_correction
        
        new_strain_sum = float(np.sum(new_strain * new_thickness))
        if new_strain_sum > 0:
            strain_correction = old_strain_weighted / new_strain_sum
            new_strain *= strain_correction
        
        record = {
            "strike_num": self.strike_count,
            "action": "upscale" if target_size > old_size else "downscale",
            "old_size": old_size,
            "new_size": target_size,
            "old_volume_um3": old_volume,
            "new_volume_um3": float(np.sum(new_thickness) * new_dx * new_dy),
            "volume_error_pct": float(
                abs(np.sum(new_thickness) * new_dx * new_dy - old_volume) / old_volume * 100
            ),
        }
        
        self.grid_size = target_size
        self.dx = new_dx
        self.dy = new_dy
        self.thickness_um = new_thickness
        self.plastic_strain = new_strain
        self.temperature_c = new_temp
        self.last_remesh_check = self.strike_count
        self.remesh_history.append(record)
        
        return record
    
    def _check_and_remesh(self) -> Optional[dict]:
        """检查网格质量，必要时执行重划"""
        if not self.remesh_config.enable:
            return None
        
        if (self.strike_count - self.last_remesh_check) < self.remesh_config.check_interval_strikes:
            return None
        
        quality = self._evaluate_mesh_quality()
        
        if quality["need_upscale"] and self.grid_size < self.remesh_config.max_grid_size:
            target_size = min(self.grid_size * 2, self.remesh_config.max_grid_size)
            result = self._remesh(target_size)
            result["quality_metrics"] = quality
            return result
        
        if quality["need_downscale"] and self.grid_size > self.remesh_config.min_grid_size:
            target_size = max(self.grid_size // 2, self.remesh_config.min_grid_size)
            if target_size >= self.initial_grid_size // 2:
                result = self._remesh(target_size)
                result["quality_metrics"] = quality
                return result
        
        self.last_remesh_check = self.strike_count
        return None
    
    # ====== 核心物理过程 ======
    
    def apply_hammer_strike(
        self,
        hammer: HammerParameters,
        ambient_temp_c: float = 25.0,
        enable_work_hardening: bool = True
    ) -> dict:
        """
        执行一次锤击，更新厚度分布、应变和温度，
        并在必要时触发自适应网格重划
        """
        cx_mm, cy_mm = hammer.position
        sigma = hammer.radius_mm * 0.8
        
        kernel = self._gaussian_kernel(cx_mm, cy_mm, sigma)
        
        avg_stress = self._calc_effective_stress(
            hammer.force,
            hammer.radius_mm,
            self.thickness_um.mean()
        )
        
        temperature_effect = np.exp(
            -(self.temperature_c - ambient_temp_c) / 300.0
        )
        
        strain_increments = np.zeros_like(self.thickness_um)
        thickness_reductions = np.zeros_like(self.thickness_um)
        
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                local_k = kernel[i, j]
                if local_k < 0.05:
                    continue
                
                local_stress = avg_stress * local_k
                local_strain_inc = self._calc_plastic_strain_increment(
                    local_stress,
                    self.plastic_strain[i, j]
                )
                local_strain_inc *= temperature_effect[i, j]
                
                strain_increments[i, j] = local_strain_inc
                
                thickness_red = self._calc_thickness_reduction(
                    local_strain_inc,
                    self.temperature_c[i, j]
                )
                thickness_reductions[i, j] = thickness_red
        
        new_thickness = self.thickness_um * (1.0 - thickness_reductions)
        
        initial_volume = (self.thickness_um.sum() * self.dx * self.dy)
        new_volume = (new_thickness.sum() * self.dx * self.dy)
        
        volume_correction = initial_volume / new_volume if new_volume > 0 else 1.0
        new_thickness *= volume_correction
        
        new_thickness = np.clip(new_thickness, 0.01, self.material.initial_thickness_um)
        
        self.plastic_strain += strain_increments
        
        heat_generated = thickness_reductions * 150.0
        self.temperature_c = self.temperature_c * 0.95 + (ambient_temp_c + heat_generated) * 0.05
        
        old_area = (self.foil_size_mm) ** 2
        avg_thickness_old = self.thickness_um.mean()
        avg_thickness_new = new_thickness.mean()
        new_area = old_area * (avg_thickness_old / avg_thickness_new)
        
        strike_elongation = np.sqrt(new_area / old_area)
        self.total_elongation *= strike_elongation
        
        self.thickness_um = new_thickness
        self.strike_count += 1
        
        remesh_result = self._check_and_remesh()
        
        record = {
            "strike_num": self.strike_count,
            "hammer_force_N": hammer.force,
            "hammer_position": (cx_mm, cy_mm),
            "hammer_radius_mm": hammer.radius_mm,
            "avg_thickness_um": float(self.thickness_um.mean()),
            "min_thickness_um": float(self.thickness_um.min()),
            "max_thickness_um": float(self.thickness_um.max()),
            "thickness_std_um": float(self.thickness_um.std()),
            "elongation_rate": float(strike_elongation),
            "total_elongation": float(self.total_elongation),
            "avg_plastic_strain": float(self.plastic_strain.mean()),
            "avg_temperature_c": float(self.temperature_c.mean()),
            "grid_size": self.grid_size,
            "remesh": remesh_result,
        }
        self.hammer_history.append(record)
        
        return record
    
    def apply_annealing(
        self,
        temp_c: float = 400.0,
        duration_min: float = 10.0
    ) -> dict:
        """模拟退火处理 - 消除加工硬化，恢复塑性"""
        if temp_c < self.material.recrystallization_temp:
            return {
                "message": "温度低于再结晶温度，退火效果不明显",
                "temp_c": temp_c,
                "residual_strain_ratio": 1.0
            }
        
        temp_ratio = (temp_c - self.material.recrystallization_temp) / \
                     (self.material.melting_point - self.material.recrystallization_temp)
        temp_ratio = np.clip(temp_ratio, 0.0, 1.0)
        
        recrystallization_fraction = 1.0 - np.exp(
            -0.1 * duration_min * temp_ratio ** 2
        )
        
        self.plastic_strain *= (1.0 - recrystallization_fraction * 0.95)
        
        self.temperature_c = np.full_like(self.temperature_c, temp_c)
        
        return {
            "message": f"退火完成，再结晶率: {recrystallization_fraction*100:.1f}%",
            "temp_c": temp_c,
            "duration_min": duration_min,
            "recrystallization_fraction": float(recrystallization_fraction),
            "residual_strain_ratio": float(1.0 - recrystallization_fraction * 0.95),
            "current_grid_size": self.grid_size,
        }
    
    def get_uniformity_metrics(self) -> dict:
        """计算厚度均匀性指标"""
        h = self.thickness_um
        h_mean = h.mean()
        h_std = h.std()
        h_min = h.min()
        h_max = h.max()
        
        cv = h_std / h_mean if h_mean > 0 else 0
        
        within_5pct = np.sum(np.abs(h - h_mean) <= 0.05 * h_mean) / h.size
        within_10pct = np.sum(np.abs(h - h_mean) <= 0.10 * h_mean) / h.size
        
        gs = self.grid_size
        diff_central = np.abs(h[gs//2, gs//2] - h_mean) / h_mean
        diff_edge = np.abs(h[0, 0] - h_mean) / h_mean
        
        return {
            "mean_thickness_um": float(h_mean),
            "std_thickness_um": float(h_std),
            "min_thickness_um": float(h_min),
            "max_thickness_um": float(h_max),
            "coefficient_of_variation": float(cv),
            "uniformity_within_5pct": float(within_5pct),
            "uniformity_within_10pct": float(within_10pct),
            "center_deviation_ratio": float(diff_central),
            "edge_deviation_ratio": float(diff_edge),
            "range_ratio": float((h_max - h_min) / h_mean) if h_mean > 0 else 0,
            "grid_size": self.grid_size,
        }
    
    def check_fracture_risk(self, threshold_um: float = 0.1) -> dict:
        """检查破裂风险 - 厚度低于阈值触发预警"""
        below_threshold = self.thickness_um < threshold_um
        risk_count = int(np.sum(below_threshold))
        risk_fraction = risk_count / self.thickness_um.size
        
        risk_level = "none"
        if risk_fraction > 0:
            if risk_fraction < 0.01:
                risk_level = "low"
            elif risk_fraction < 0.05:
                risk_level = "medium"
            else:
                risk_level = "high"
        
        positions = []
        if risk_count > 0:
            coords = np.where(below_threshold)
            for i in range(min(risk_count, 10)):
                px_mm = (coords[1][i] / self.grid_size - 0.5) * self.foil_size_mm
                py_mm = (coords[0][i] / self.grid_size - 0.5) * self.foil_size_mm
                positions.append({
                    "x_mm": float(px_mm),
                    "y_mm": float(py_mm),
                    "thickness_um": float(self.thickness_um[coords[0][i], coords[1][i]])
                })
        
        return {
            "threshold_um": threshold_um,
            "risk_level": risk_level,
            "risk_count": risk_count,
            "risk_fraction": float(risk_fraction),
            "risk_positions": positions,
            "min_thickness_um": float(self.thickness_um.min()),
            "grid_size": self.grid_size,
        }
    
    def get_thickness_distribution(self) -> dict:
        """获取厚度分布数据用于可视化"""
        h = self.thickness_um
        h_flat = h.flatten()
        
        histogram, bin_edges = np.histogram(
            h_flat,
            bins=32,
            range=(h_flat.min(), h_flat.max())
        )
        
        return {
            "grid_size": self.grid_size,
            "foil_size_mm": self.foil_size_mm,
            "thickness_matrix_um": self.thickness_um.tolist(),
            "histogram": histogram.tolist(),
            "bin_edges": bin_edges.tolist(),
            "metrics": self.get_uniformity_metrics(),
            "remesh_count": len(self.remesh_history),
            "remesh_history": self.remesh_history[-5:],
        }
    
    def get_mesh_quality_report(self) -> dict:
        """获取网格质量诊断报告"""
        quality = self._evaluate_mesh_quality()
        return {
            "strike_count": self.strike_count,
            "current_grid_size": self.grid_size,
            "initial_grid_size": self.initial_grid_size,
            "quality_metrics": quality,
            "remesh_history": self.remesh_history[-10:],
            "total_remeshes": len(self.remesh_history),
            "remesh_config": {
                "enable": self.remesh_config.enable,
                "min_grid_size": self.remesh_config.min_grid_size,
                "max_grid_size": self.remesh_config.max_grid_size,
                "gradient_threshold": self.remesh_config.gradient_threshold,
            }
        }
    
    def reset(self):
        """重置金箔到初始状态"""
        self.grid_size = self.initial_grid_size
        self.dx = self.foil_size_mm / self.grid_size
        self.dy = self.foil_size_mm / self.grid_size
        
        self.thickness_um = np.full(
            (self.grid_size, self.grid_size),
            self.material.initial_thickness_um,
            dtype=np.float64
        )
        self.plastic_strain = np.zeros(
            (self.grid_size, self.grid_size),
            dtype=np.float64
        )
        self.temperature_c = np.full(
            (self.grid_size, self.grid_size),
            25.0,
            dtype=np.float64
        )
        self.strike_count = 0
        self.total_elongation = 1.0
        self.hammer_history = []
        self.remesh_history = []
        self.last_remesh_check = 0
        self._alloy_composition = None
        self._process_mode = "ancient_forging"


# =============================================================
# 新功能扩展：合金配比、工艺对比、佛像贴金、虚拟打金体验
# =============================================================


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


@dataclass
class ProcessParameters:
    """工艺参数基类"""
    name: str
    process_type: str


@dataclass
class AncientForgingParams(ProcessParameters):
    """古代锻制工艺参数"""
    anneal_interval_strikes: int = 70
    anneal_temperature_c: float = 450.0
    anneal_duration_min: float = 10.0
    hammer_force_profile: str = "nanjing_wujin"
    strike_path: str = "center_out"

    def __post_init__(self):
        self.process_type = "ancient_forging"


@dataclass
class VacuumCoatingParams(ProcessParameters):
    """真空镀膜工艺参数"""
    target_thickness_um: float = 0.1
    deposition_rate_um_per_min: float = 0.02
    base_pressure_pa: float = 1e-3
    substrate_temperature_c: float = 150.0
    bias_voltage_v: float = -100.0
    argon_pressure_pa: float = 0.5
    power_kw: float = 5.0

    def __post_init__(self):
        self.process_type = "modern_vacuum_coating"


@dataclass
class ProcessComparisonResult:
    """工艺对比结果"""
    ancient: dict
    modern_vacuum: dict
    modern_electroplating: dict
    recommendation: str
    radar_chart_data: dict


class ProcessComparisonEngine:
    """
    古代金箔锻制 vs 现代真空镀膜 vs 现代电镀 工艺对比分析引擎
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or self._default_config()

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
        production_area_m2: float = 10.0,
        use_case: str = "buddha_gilding",
    ) -> ProcessComparisonResult:
        """
        对比三种工艺在特定应用场景下的表现

        参数:
            target_thickness_um: 目标金箔厚度
            production_area_m2: 生产面积
            use_case: 应用场景 (buddha_gilding / decoration / jewelry / architecture)
        """
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
                "estimated_total_cost_cny": float(total_cost),
                "environmental_impact_score": cfg["environmental_impact_score"],
                "surface_roughness_um": cfg["surface_roughness_um"],
                "material_utilization_pct": cfg["material_utilization_pct"],
                "individual_scores": scores,
                "weighted_total_score": float(weighted_score),
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


@dataclass
class BuddhaGildingConfig:
    """佛像贴金仿真配置"""
    buddha_type: str = "meditation"
    surface_complexity: str = "gentle_curve"
    adhesive_type: str = "gold_leaf_size"
    foil_size_mm: int = 100
    foil_thickness_um: float = 0.2
    skill_level: float = 0.7
    foil_roughness_um: float = 0.02
    polishing_level: float = 0.5


class BuddhaGildingSimulator:
    """
    佛像贴金效果仿真器
    模拟金箔在不同曲面上的贴合效果、褶皱风险、覆盖效率
    """

    def __init__(self):
        self.adhesive_types = self._default_adhesives()
        self.curvature_effects = self._default_curvature_effects()
        self.buddha_geometries = self._default_buddha_geometries()

    def _default_adhesives(self) -> Dict:
        return {
            "traditional_animal_glue": {
                "name": "传统动物胶",
                "components": ["牛骨胶", "明矾", "水"],
                "drying_time_hours": 12,
                "durability_years": 50,
                "surface_finish": "哑光温润",
                "adhesion_strength_mpa": 3.0,
                "water_resistance": 0.7,
                "uv_resistance": 0.6,
                "ease_of_use": 0.6,
                "roughness_contribution_um": 0.005,
            },
            "modern_acrylic": {
                "name": "现代丙烯酸胶",
                "components": ["丙烯酸树脂", "固化剂", "溶剂"],
                "drying_time_hours": 4,
                "durability_years": 15,
                "surface_finish": "光亮平滑",
                "adhesion_strength_mpa": 2.5,
                "water_resistance": 0.9,
                "uv_resistance": 0.85,
                "ease_of_use": 0.9,
                "roughness_contribution_um": 0.001,
            },
            "gold_leaf_size": {
                "name": "金箔专用胶 (柿漆)",
                "components": ["柿漆", "糯米胶", "明矾"],
                "drying_time_hours": 24,
                "durability_years": 80,
                "surface_finish": "半哑光",
                "adhesion_strength_mpa": 1.8,
                "water_resistance": 0.8,
                "uv_resistance": 0.95,
                "ease_of_use": 0.5,
                "roughness_contribution_um": 0.003,
            },
        }

    def _default_curvature_effects(self) -> Dict:
        return {
            "flat_surface": {
                "name": "平面",
                "coverage_efficiency_pct": 95,
                "wrinkle_risk_pct": 5,
                "difficulty_level": 1,
                "tear_risk_pct": 2,
            },
            "gentle_curve": {
                "name": "平缓曲面",
                "coverage_efficiency_pct": 85,
                "wrinkle_risk_pct": 15,
                "difficulty_level": 2,
                "tear_risk_pct": 8,
            },
            "sharp_curve": {
                "name": "急剧曲面",
                "coverage_efficiency_pct": 70,
                "wrinkle_risk_pct": 30,
                "difficulty_level": 3,
                "tear_risk_pct": 20,
            },
            "complex_3d": {
                "name": "复杂3D造型",
                "coverage_efficiency_pct": 50,
                "wrinkle_risk_pct": 50,
                "difficulty_level": 4,
                "tear_risk_pct": 35,
            },
        }

    def _default_buddha_geometries(self) -> Dict:
        return {
            "meditation": {
                "name": "禅定印佛像",
                "total_surface_area_m2": 2.5,
                "flat_area_pct": 40,
                "gentle_curve_pct": 45,
                "sharp_curve_pct": 12,
                "complex_3d_pct": 3,
                "detail_features": ["螺发", "眉间白毫", "手印"],
            },
            "teaching": {
                "name": "说法印佛像",
                "total_surface_area_m2": 3.2,
                "flat_area_pct": 30,
                "gentle_curve_pct": 45,
                "sharp_curve_pct": 20,
                "complex_3d_pct": 5,
                "detail_features": ["手印", "头光", "衣纹"],
            },
            "abhayamudra": {
                "name": "施无畏印佛像",
                "total_surface_area_m2": 3.8,
                "flat_area_pct": 25,
                "gentle_curve_pct": 40,
                "sharp_curve_pct": 25,
                "complex_3d_pct": 10,
                "detail_features": ["手掌", "手指", "衣纹褶皱"],
            },
            "guanyin": {
                "name": "观音像",
                "total_surface_area_m2": 4.5,
                "flat_area_pct": 20,
                "gentle_curve_pct": 45,
                "sharp_curve_pct": 25,
                "complex_3d_pct": 10,
                "detail_features": ["头冠", "璎珞", "净瓶", "柳枝"],
            },
        }

    def _generate_gilding_surface(
        self,
        geometry_key: str,
        grid_size: int = 64,
    ) -> Dict[str, Any]:
        """生成贴金表面的高度场和曲率场"""
        geometry = self.buddha_geometries.get(geometry_key, self.buddha_geometries["meditation"])
        surf_area = geometry["total_surface_area_m2"]

        scale = np.sqrt(surf_area) * 1000 / grid_size

        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        X, Y = np.meshgrid(x, y)

        height = np.zeros_like(X)

        height += 1.0 * np.exp(-(X**2 + Y**2) / 0.5)
        height += 0.3 * np.sin(4 * X) * np.cos(4 * Y)
        height += 0.15 * np.sin(8 * X) * np.sin(8 * Y)

        gy, gx = np.gradient(height)
        curvature_magnitude = np.sqrt(gx**2 + gy**2)

        curvature_map = np.full((grid_size, grid_size), "flat_surface", dtype=object)
        curvature_map[curvature_magnitude > 0.02] = "gentle_curve"
        curvature_map[curvature_magnitude > 0.06] = "sharp_curve"
        curvature_map[curvature_magnitude > 0.12] = "complex_3d"

        return {
            "height_field": height.tolist(),
            "curvature_magnitude": curvature_magnitude.tolist(),
            "curvature_map": curvature_map.tolist(),
            "surface_area_m2": surf_area,
            "geometry": geometry,
            "scale_mm_per_pixel": float(scale),
        }

    def simulate_gilding(
        self,
        config: BuddhaGildingConfig,
        thickness_distribution: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        模拟佛像贴金过程

        参数:
            config: 贴金配置
            thickness_distribution: 金箔厚度分布（可选，来自物理模型）

        返回:
            贴金效果仿真结果
        """
        surface = self._generate_gilding_surface(config.buddha_type)
        curvature_map = np.array(surface["curvature_map"])
        adhesive = self.adhesive_types.get(
            config.adhesive_type, self.adhesive_types["gold_leaf_size"]
        )

        if thickness_distribution is not None:
            foil_thickness = thickness_distribution
            avg_thickness = float(np.mean(thickness_distribution))
            thickness_std = float(np.std(thickness_distribution))
            uniformity = 1.0 - (thickness_std / (avg_thickness + 1e-8))
        else:
            avg_thickness = config.foil_thickness_um
            uniformity = 0.95
            foil_thickness = np.full_like(
                np.array(surface["height_field"]),
                config.foil_thickness_um
            )

        coverage = np.zeros_like(foil_thickness, dtype=float)
        wrinkles = np.zeros_like(foil_thickness, dtype=float)
        tears = np.zeros_like(foil_thickness, dtype=bool)

        total_foil_used = 0
        total_coverage_area = 0

        grid_size = foil_thickness.shape[0]

        for i in range(grid_size):
            for j in range(grid_size):
                curv = curvature_map[i, j]
                curv_effect = self.curvature_effects[curv]

                coverage_eff = curv_effect["coverage_efficiency_pct"] / 100.0
                wrinkle_risk = curv_effect["wrinkle_risk_pct"] / 100.0
                tear_risk = curv_effect["tear_risk_pct"] / 100.0

                skill_factor = config.skill_level
                foil_condition = uniformity

                local_coverage = (
                    coverage_eff
                    * skill_factor
                    * foil_condition
                    * adhesive["ease_of_use"]
                )

                wrinkle_intensity = (
                    wrinkle_risk
                    * (1.0 - skill_factor)
                    * (1.0 - foil_condition * 0.5)
                )

                tear_probability = (
                    tear_risk
                    * (1.0 - skill_factor * 0.7)
                    * (1.0 - uniformity * 0.8)
                )

                if np.random.random() < tear_probability:
                    tears[i, j] = True
                    local_coverage *= 0.3
                    wrinkle_intensity *= 1.5

                coverage[i, j] = np.clip(local_coverage, 0, 1)
                wrinkles[i, j] = np.clip(wrinkle_intensity, 0, 1)

                total_foil_used += config.foil_size_mm ** 2 / 1e6
                total_coverage_area += coverage[i, j] * (surface["scale_mm_per_pixel"] ** 2) / 1e6

        avg_coverage = float(np.mean(coverage))
        wrinkle_area_pct = float(np.sum(wrinkles > 0.3) / wrinkles.size * 100)
        tear_count = int(np.sum(tears))
        material_efficiency = total_coverage_area / max(total_foil_used, 1e-8) * 100

        lighting_effect = self._simulate_lighting(coverage, wrinkles, foil_thickness, adhesive)

        surface_roughness = self._calculate_surface_roughness(
            coverage, wrinkles, curvature_map, adhesive, config
        )

        quality_score = (
            avg_coverage * 30
            + (1.0 - wrinkle_area_pct / 100) * 20
            + uniformity * 20
            + adhesive["durability_years"] / 80 * 15
            + surface_roughness["glossiness_gu"] / 100 * 15
        )

        return {
            "buddha_type": config.buddha_type,
            "buddha_name": surface["geometry"]["name"],
            "surface_area_m2": surface["surface_area_m2"],
            "adhesive": adhesive,
            "avg_foil_thickness_um": avg_thickness,
            "foil_uniformity": float(uniformity),
            "coverage_map": coverage.tolist(),
            "wrinkle_map": wrinkles.tolist(),
            "tear_map": tears.tolist(),
            "lighting_simulation": lighting_effect,
            "surface_roughness": surface_roughness,
            "metrics": {
                "average_coverage_pct": float(avg_coverage * 100),
                "wrinkle_area_pct": wrinkle_area_pct,
                "tear_count": tear_count,
                "tear_density_pct": float(tear_count / tears.size * 100),
                "material_efficiency_pct": float(material_efficiency),
                "total_foil_used_m2": float(total_foil_used),
                "total_covered_area_m2": float(total_coverage_area),
                "estimated_foil_sheets": int(np.ceil(total_coverage_area / max(config.foil_size_mm ** 2 / 1e6, 1e-12))),
                "estimated_drying_time_hours": adhesive["drying_time_hours"],
                "durability_years": adhesive["durability_years"],
                "quality_score": float(quality_score),
                "surface_roughness_ra_um": surface_roughness["ra_um"],
                "glossiness_gu": surface_roughness["glossiness_gu"],
            },
            "difficulty_assessment": {
                "overall_difficulty": max(
                    self.curvature_effects[c]["difficulty_level"]
                    for c in np.unique(curvature_map)
                ),
                "recommended_skill_level": (
                    "beginner" if quality_score > 85
                    else "intermediate" if quality_score > 65
                    else "master"
                ),
                "tips": self._generate_tips(config, quality_score),
            },
            "height_field_preview": surface["height_field"],
            "curvature_map_preview": curvature_map.tolist(),
        }

    def _calculate_surface_roughness(
        self,
        coverage: np.ndarray,
        wrinkles: np.ndarray,
        curvature_map: np.ndarray,
        adhesive: Dict,
        config: BuddhaGildingConfig,
    ) -> Dict[str, Any]:
        """
        计算贴金后的表面粗糙度分布
        粗糙度模型：
        Ra = sqrt(foil_roughness^2 + adhesive_roughness^2 + wrinkle_roughness^2 + curvature_roughness^2)

        返回包含完整粗糙度参数的结果
        """
        grid_size = coverage.shape[0]

        foil_roughness = np.full((grid_size, grid_size), config.foil_roughness_um)

        adhesive_roughness = np.full_like(foil_roughness, adhesive.get("roughness_contribution_um", 0.003))
        adhesive_roughness *= (1.0 + (1.0 - coverage) * 0.5)

        wrinkle_roughness = wrinkles * 0.05

        curvature_roughness = np.zeros_like(foil_roughness)
        for i in range(grid_size):
            for j in range(grid_size):
                curv = curvature_map[i, j]
                if curv == "flat_surface":
                    curvature_roughness[i, j] = 0.0
                elif curv == "gentle_curve":
                    curvature_roughness[i, j] = 0.002
                elif curv == "sharp_curve":
                    curvature_roughness[i, j] = 0.008
                elif curv == "complex_3d":
                    curvature_roughness[i, j] = 0.015
                else:
                    curvature_roughness[i, j] = 0.005

        total_roughness = np.sqrt(
            foil_roughness ** 2
            + adhesive_roughness ** 2
            + wrinkle_roughness ** 2
            + curvature_roughness ** 2
        )

        polishing_factor = 1.0 - config.polishing_level * 0.4
        total_roughness *= polishing_factor

        ra_value = float(np.mean(total_roughness))
        rq_value = float(np.sqrt(np.mean(total_roughness ** 2)))
        rz_value = float(np.mean(np.sort(total_roughness, axis=None)[-int(grid_size * grid_size * 0.1):]))
        rt_value = float(np.max(total_roughness))

        roughness_profile = total_roughness[grid_size // 2, :].tolist()

        glossiness = self._calculate_glossiness(ra_value, adhesive)

        return {
            "ra_um": ra_value,
            "rq_um": rq_value,
            "rz_um": rz_value,
            "rt_um": rt_value,
            "rq_over_ra": rq_value / max(ra_value, 1e-9),
            "glossiness_gu": glossiness,
            "roughness_map": total_roughness.tolist(),
            "profile_cross_section": roughness_profile,
            "components": {
                "foil_roughness_um": float(np.mean(foil_roughness)),
                "adhesive_roughness_um": float(np.mean(adhesive_roughness)),
                "wrinkle_roughness_um": float(np.mean(wrinkle_roughness)),
                "curvature_roughness_um": float(np.mean(curvature_roughness)),
            },
            "polishing_factor": polishing_factor,
            "surface_classification": self._classify_roughness(ra_value),
        }

    def _calculate_glossiness(self, ra_um: float, adhesive: Dict) -> float:
        """根据粗糙度计算光泽度（GU单位）"""
        base_gloss = {
            "哑光温润": 30.0,
            "半哑光": 60.0,
            "光亮平滑": 95.0,
        }.get(adhesive.get("surface_finish", "半哑光"), 60.0)

        roughness_factor = np.exp(-ra_um * 50)

        return float(base_gloss * roughness_factor)

    def _classify_roughness(self, ra_um: float) -> str:
        """根据Ra值对表面粗糙度进行分级"""
        if ra_um < 0.005:
            return "超光滑 (镜面级)"
        elif ra_um < 0.01:
            return "极光滑 (装饰级)"
        elif ra_um < 0.03:
            return "光滑 (贴金级)"
        elif ra_um < 0.08:
            return "半光滑"
        elif ra_um < 0.2:
            return "微粗糙"
        else:
            return "粗糙"

    def _simulate_lighting(
        self,
        coverage: np.ndarray,
        wrinkles: np.ndarray,
        thickness: np.ndarray,
        adhesive: Dict,
    ) -> Dict[str, Any]:
        """模拟贴金后的光照效果"""
        grid_size = coverage.shape[0]

        light_dir = np.array([0.5, 0.7, 0.5])
        light_dir = light_dir / np.linalg.norm(light_dir)

        x = np.linspace(-1, 1, grid_size)
        y = np.linspace(-1, 1, grid_size)
        X, Y = np.meshgrid(x, y)

        Z = np.zeros_like(X)
        Z += coverage * 0.5
        Z += (1.0 - wrinkles) * 0.3

        gy, gx = np.gradient(Z)
        normal = np.dstack([-gx, -gy, np.ones_like(gx)])
        norm_mag = np.linalg.norm(normal, axis=2, keepdims=True)
        normal = normal / (norm_mag + 1e-8)

        diffuse = np.sum(normal * light_dir, axis=2)
        diffuse = np.clip(diffuse, 0, 1)

        view_dir = np.array([0, 0, 1])
        half_dir = (light_dir + view_dir) / 2
        specular = np.sum(normal * half_dir, axis=2) ** 32
        specular = np.clip(specular, 0, 1)

        finish_adjust = {
            "哑光温润": 0.2,
            "光亮平滑": 0.8,
            "半哑光": 0.5,
        }
        specular_strength = finish_adjust.get(adhesive["surface_finish"], 0.5)

        ambient = 0.15
        total_light = ambient + 0.6 * diffuse + specular_strength * specular

        reflection_map = total_light * coverage

        color_temp = 5500 if "光亮" in adhesive["surface_finish"] else 4500

        return {
            "diffuse_map": diffuse.tolist(),
            "specular_map": specular.tolist(),
            "total_reflection": reflection_map.tolist(),
            "brightness_distribution": {
                "mean": float(np.mean(reflection_map)),
                "std": float(np.std(reflection_map)),
                "min": float(np.min(reflection_map)),
                "max": float(np.max(reflection_map)),
            },
            "color_temperature_k": color_temp,
            "surface_finish": adhesive["surface_finish"],
            "luster_description": (
                "内敛温润，有岁月沉淀感" if specular_strength < 0.3
                else "金碧辉煌，耀眼夺目" if specular_strength > 0.7
                else "光泽柔和，典雅高贵"
            ),
        }

    def _generate_tips(self, config: BuddhaGildingConfig, quality_score: float) -> List[str]:
        """生成贴金建议"""
        tips = []
        if quality_score < 70:
            tips.append("建议选择平整度更好的区域开始练习，逐步挑战复杂曲面")
        if config.skill_level < 0.6:
            tips.append("使用柿漆（金箔专用胶）可以获得更好的耐久性和传统质感")
            tips.append("复杂部位建议使用更小尺寸的金箔（50×50mm）以降低褶皱风险")
        if config.foil_thickness_um < 0.15:
            tips.append("薄金箔透光性更好但更易破损，建议搭配动物胶使用")
        if config.buddha_type in ["abhayamudra", "guanyin"]:
            tips.append("手印、璎珞等细节部位需用竹刀轻压贴合，避免产生气泡")
        tips.append("贴金完成后建议用玛瑙刀压光，可大幅提升表面光泽度")
        return tips


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
