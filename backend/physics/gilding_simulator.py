"""
佛像贴金效果仿真器 - 独立模块

本模块提供佛像贴金工艺的数字仿真功能，包括：
- 金箔在不同佛像曲面上的贴合效果模拟
- 表面粗糙度的四分量合成模型计算
- 基于Phong光照模型的视觉效果渲染
- 贴金质量评估与工艺建议生成

主要特性：
1. 支持多种佛像造型（禅定印、说法印、施无畏印、观音像）
2. 支持多种胶粘剂类型（传统动物胶、现代丙烯酸胶、金箔专用胶）
3. 四分量粗糙度合成模型：金箔本身粗糙度 + 胶粘剂贡献 + 褶皱贡献 + 曲面曲率贡献
4. 完整的表面粗糙度分级体系
5. Phong光照模型模拟真实光照效果
6. 智能工艺建议生成
"""
import numpy as np
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


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
