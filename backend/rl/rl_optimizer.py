"""
强化学习优化模块 v2 - 基于厚度分布反馈优化锤击路径和力度
实现: 启发式策略 + Q-Learning + 策略梯度 + 演示数据预训练(Behavior Cloning)

== v2 改进 ==
引入演示数据预训练，加速训练收敛：
- DemoBuffer: 存储专家(启发式)演示轨迹
- Behavior Cloning: 监督学习预训练Q表和策略网络
- Pretrain报告: 演示动作命中率、损失下降曲线
"""
import numpy as np
from dataclasses import dataclass, field
from typing import Tuple, List, Optional, Callable, Dict
from enum import Enum
import sys
import os
import pickle
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from physics.physics_model import (
    GoldFoilPhysicsModel,
    HammerParameters,
)


class ActionType(Enum):
    HEURISTIC = "heuristic"
    RANDOM = "random"
    POLICY_GRADIENT = "policy_gradient"
    Q_LEARNING = "q_learning"
    PRETRAINED = "pretrained"


@dataclass
class RLConfig:
    """强化学习配置"""
    grid_size: int = 8
    force_levels: int = 5
    min_force: float = 300.0
    max_force: float = 1500.0
    learning_rate: float = 0.01
    gamma: float = 0.99
    epsilon_start: float = 1.0
    epsilon_min: float = 0.05
    epsilon_decay: float = 0.995
    uniformity_weight: float = 0.6
    thickness_weight: float = 0.3
    fracture_penalty_weight: float = 10.0
    target_thickness_um: float = 0.5
    # === 预训练配置 ===
    pretrain_lr: float = 0.05
    pretrain_epochs: int = 50
    pretrain_batch_size: int = 64


@dataclass
class DemoTransition:
    """一条演示数据 (状态→动作) 对"""
    state_feature: np.ndarray  # (grid_size, grid_size) 厚度偏差特征
    action_gx: int
    action_gy: int
    action_force_level: int
    expert_reward: Optional[float] = None
    step_idx: int = 0


class DemoBuffer:
    """
    专家演示数据缓冲区
    存储启发式策略(乌兹铁匠经验)的 (s, a, r, s') 转换
    """

    def __init__(self, capacity: int = 5000):
        self.capacity = capacity
        self.transitions: List[DemoTransition] = []
        self.episode_returns: List[float] = []

    def add(self, transition: DemoTransition):
        """添加一条转换"""
        if len(self.transitions) >= self.capacity:
            self.transitions.pop(0)
        self.transitions.append(transition)

    def add_episode(self, transitions: List[DemoTransition], episode_return: float):
        """添加完整的一集演示"""
        for t in transitions:
            self.add(t)
        self.episode_returns.append(episode_return)
        if len(self.episode_returns) > 200:
            self.episode_returns = self.episode_returns[-200:]

    def sample(self, batch_size: int) -> List[DemoTransition]:
        """均匀采样一批数据"""
        if len(self.transitions) == 0:
            return []
        indices = np.random.choice(
            len(self.transitions),
            size=min(batch_size, len(self.transitions)),
            replace=False
        )
        return [self.transitions[i] for i in indices]

    def sample_weighted(self, batch_size: int) -> List[DemoTransition]:
        """按专家奖励加权采样 (优先采样高奖励转换)"""
        if len(self.transitions) == 0:
            return []

        rewards = np.array([
            t.expert_reward if t.expert_reward is not None else 0.0
            for t in self.transitions
        ])
        rewards = rewards - rewards.min() + 1e-6
        probs = rewards / rewards.sum()

        indices = np.random.choice(
            len(self.transitions),
            size=min(batch_size, len(self.transitions)),
            replace=False,
            p=probs
        )
        return [self.transitions[i] for i in indices]

    def __len__(self):
        return len(self.transitions)

    def save(self, path: str):
        """持久化演示数据"""
        data = {
            "transitions": [
                {
                    "state_feature": t.state_feature,
                    "action_gx": t.action_gx,
                    "action_gy": t.action_gy,
                    "action_force_level": t.action_force_level,
                    "expert_reward": t.expert_reward,
                    "step_idx": t.step_idx,
                }
                for t in self.transitions
            ],
            "episode_returns": self.episode_returns,
        }
        with open(path, "wb") as f:
            pickle.dump(data, f)

    def load(self, path: str):
        """加载演示数据"""
        with open(path, "rb") as f:
            data = pickle.load(f)
        self.transitions = [
            DemoTransition(
                state_feature=d["state_feature"],
                action_gx=d["action_gx"],
                action_gy=d["action_gy"],
                action_force_level=d["action_force_level"],
                expert_reward=d.get("expert_reward"),
                step_idx=d.get("step_idx", 0),
            )
            for d in data["transitions"]
        ]
        self.episode_returns = data.get("episode_returns", [])


class HammeringPolicy:
    """
    锤击策略 v2 - 支持演示预训练
    
    训练流程:
    1. 收集专家演示 (启发式策略)
    2. Behavior Cloning 预训练 Q表 + 策略网络
    3. 在线强化学习微调 (Q-Learning + Policy Gradient)
    """
    
    def __init__(self, foil_size_mm: float, config: Optional[RLConfig] = None):
        self.foil_size_mm = foil_size_mm
        self.config = config or RLConfig()
        self.epsilon = self.config.epsilon_start
        self.is_pretrained = False
        self.pretrain_stats: Dict = {}
        
        n_positions = self.config.grid_size ** 2
        n_actions = n_positions * self.config.force_levels
        self.q_table = np.zeros(
            (self.config.grid_size, self.config.grid_size, self.config.force_levels)
        )
        self.policy_network = np.random.normal(
            0, 0.01,
            (self.config.grid_size, self.config.grid_size, self.config.force_levels)
        )
        self.baseline = 0.0
        self.rewards_history: List[float] = []
        self.action_counts = np.zeros_like(self.q_table)
    
    def _discretize_position(
        self,
        x_mm: float,
        y_mm: float
    ) -> Tuple[int, int]:
        """将连续位置转换为网格索引"""
        half = self.foil_size_mm / 2
        gx = int((x_mm + half) / self.foil_size_mm * self.config.grid_size)
        gy = int((y_mm + half) / self.foil_size_mm * self.config.grid_size)
        gx = np.clip(gx, 0, self.config.grid_size - 1)
        gy = np.clip(gy, 0, self.config.grid_size - 1)
        return gx, gy
    
    def _undiscretize_position(
        self,
        gx: int,
        gy: int
    ) -> Tuple[float, float]:
        """将网格索引转换为连续位置"""
        cell_size = self.foil_size_mm / self.config.grid_size
        x_mm = (gx + 0.5) * cell_size - self.foil_size_mm / 2
        y_mm = (gy + 0.5) * cell_size - self.foil_size_mm / 2
        return x_mm, y_mm
    
    def _force_level_to_value(self, level: int) -> float:
        """力度等级转实际力度值"""
        level = int(np.clip(level, 0, self.config.force_levels - 1))
        force_range = self.config.max_force - self.config.min_force
        return self.config.min_force + (level / (self.config.force_levels - 1)) * force_range
    
    def _value_to_force_level(self, force_value: float) -> int:
        """实际力度值转力度等级"""
        force_range = self.config.max_force - self.config.min_force
        normalized = (force_value - self.config.min_force) / (force_range + 1e-8)
        return int(np.clip(
            round(normalized * (self.config.force_levels - 1)),
            0,
            self.config.force_levels - 1
        ))
    
    def _select_action_heuristic(
        self,
        thickness_matrix: np.ndarray,
        temperature: np.ndarray
    ) -> Tuple[int, int, int]:
        """
        基于启发式规则选择动作 - 厚的地方打重锤
        
        策略:
        1. 找到最厚的区域
        2. 厚度偏差越大，力度越大
        """
        h_mean = thickness_matrix.mean()
        h_deviation = thickness_matrix - h_mean
        
        downsampled = self._downsample(h_deviation)
        
        max_val = downsampled.max()
        uniform_threshold = 1e-4 * h_mean
        
        if max_val <= uniform_threshold:
            gs = self.config.grid_size
            best_gx = np.random.randint(0, gs)
            best_gy = np.random.randint(0, gs)
            intensity_ratio = 1.0
        else:
            noise = np.random.normal(0, max_val * 0.01, downsampled.shape)
            candidates = np.where((downsampled + noise) >= max_val * 0.95)
            if len(candidates[0]) == 0:
                best_gx, best_gy = np.unravel_index(
                    np.argmax(downsampled), downsampled.shape
                )
            else:
                pick_idx = np.random.randint(0, len(candidates[0]))
                best_gx = int(candidates[0][pick_idx])
                best_gy = int(candidates[1][pick_idx])
            
            avg_dev = np.abs(downsampled).mean()
            if avg_dev > 0:
                intensity_ratio = np.clip(max_val / (avg_dev + 1e-8), 0, 3)
            else:
                intensity_ratio = 1.0
        
        force_level = int(np.clip(
            (intensity_ratio / 3.0) * (self.config.force_levels - 1)))
        force_level = int(np.clip(force_level, 0, self.config.force_levels - 1))
        
        return int(best_gx), int(best_gy), force_level
    
    def _downsample(self, matrix: np.ndarray) -> np.ndarray:
        """下采样厚度矩阵到策略网格大小"""
        h, w = matrix.shape
        block_h = max(1, h // self.config.grid_size)
        block_w = max(1, w // self.config.grid_size)
        
        result = np.zeros((self.config.grid_size, self.config.grid_size))
        
        for i in range(self.config.grid_size):
            for j in range(self.config.grid_size):
                start_h = i * block_h
                end_h = min((i + 1) * block_h, h)
                start_w = j * block_w
                end_w = min((j + 1) * block_w, w)
                block = matrix[start_h:end_h, start_w:end_w]
                if block.size > 0:
                    result[i, j] = block.mean()
        
        return result
    
    def _extract_state_feature(self, thickness_matrix: np.ndarray) -> np.ndarray:
        """提取归一化的状态特征用于预训练"""
        h_mean = thickness_matrix.mean()
        h_deviation = thickness_matrix - h_mean
        h_std = thickness_matrix.std() + 1e-8
        normalized = h_deviation / h_std
        return self._downsample(normalized)
    
    def select_action(
        self,
        thickness_matrix: np.ndarray,
        temperature: np.ndarray,
        mode: ActionType = ActionType.HEURISTIC,
        use_epsilon_greedy: bool = True
    ) -> HammerParameters:
        """
        选择锤击动作
        """
        if use_epsilon_greedy and np.random.random() < self.epsilon:
            gx = np.random.randint(0, self.config.grid_size)
            gy = np.random.randint(0, self.config.grid_size)
            force_level = np.random.randint(0, self.config.force_levels)
        else:
            if mode in (ActionType.HEURISTIC,):
                gx, gy, force_level = self._select_action_heuristic(
                    thickness_matrix, temperature
                )
            elif mode in (ActionType.Q_LEARNING, ActionType.PRETRAINED, ActionType.POLICY_GRADIENT):
                state_repr = self._extract_state_feature(thickness_matrix)
                combined = self.q_table + self.policy_network
                values = combined  # (grid, grid, force_levels)
                
                state_weights = np.abs(state_repr) + 0.1
                weighted = values * state_weights[:, :, np.newaxis]
                flat_idx = np.argmax(weighted.reshape(-1))
                gx, gy, force_level = np.unravel_index(
                    int(flat_idx), values.shape
                )
                gx, gy, force_level = int(gx), int(gy), int(force_level)
            else:
                gx, gy, force_level = self._select_action_heuristic(
                    thickness_matrix, temperature
                )
        
        x_mm, y_mm = self._undiscretize_position(gx, gy)
        force = self._force_level_to_value(force_level)
        
        return HammerParameters(
            force=force,
            position=(x_mm, y_mm),
            radius_mm=15.0,
        )
    
    def compute_reward(
        self,
        prev_metrics: dict,
        curr_metrics: dict,
        fracture_risk: dict,
        target_thickness_um: Optional[float] = None
    ) -> float:
        """
        计算奖励函数
        """
        target = target_thickness_um or self.config.target_thickness_um
        
        uniformity_prev = prev_metrics.get("coefficient_of_variation", 0.1)
        uniformity_curr = curr_metrics["coefficient_of_variation"]
        
        uniformity_reward = (uniformity_prev - uniformity_curr) * 100.0
        
        thickness_curr = curr_metrics["mean_thickness_um"]
        thickness_error = abs(thickness_curr - target) / max(target, 1e-8)
        thickness_reward = -thickness_error * 50.0
        
        fracture_penalty = 0.0
        if fracture_risk["risk_level"] != "none":
            risk_scores = {"low": 1, "medium": 3, "high": 10}
            fracture_penalty = -risk_scores.get(
                fracture_risk["risk_level"], 5
            ) * self.config.fracture_penalty_weight
        
        min_thick = curr_metrics["min_thickness_um"]
        if min_thick < 0.1:
            fracture_penalty -= 50.0 * (0.1 - min_thick) / 0.1
        
        total_reward = (
            self.config.uniformity_weight * uniformity_reward
            + self.config.thickness_weight * thickness_reward
            + fracture_penalty
        )
        
        return float(total_reward)
    
    # ===== 演示数据预训练 (Behavior Cloning) =====
    
    def generate_expert_demos(
        self,
        demo_buffer: DemoBuffer,
        num_episodes: int = 20,
        steps_per_episode: int = 40,
        base_grid_size: int = 32,
        verbose: bool = True,
    ) -> dict:
        """
        使用启发式策略(乌兹铁匠经验)生成专家演示数据
        
        对每个episode:
        1. 初始化新的物理模型
        2. 逐步运行启发式策略
        3. 记录每一步 (s_feature, a_gx, a_gy, a_force, r)
        4. 存入DemoBuffer
        """
        if verbose:
            print(f"[DemoGen] 生成 {num_episodes} 集专家演示 (每集{steps_per_episode}步)...")
        
        episode_rewards_list = []
        total_steps = 0
        start_time = time.time()
        
        for ep in range(num_episodes):
            physics = GoldFoilPhysicsModel(grid_size=base_grid_size)
            prev_metrics = physics.get_uniformity_metrics()
            episode_transitions: List[DemoTransition] = []
            episode_return = 0.0
            
            for step in range(steps_per_episode):
                state_feature = self._extract_state_feature(physics.thickness_um)
                
                action = self.select_action(
                    thickness_matrix=physics.thickness_um,
                    temperature=physics.temperature_c,
                    mode=ActionType.HEURISTIC,
                    use_epsilon_greedy=False,
                )
                
                gx, gy = self._discretize_position(*action.position)
                force_level = self._value_to_force_level(action.force)
                
                strike_result = physics.apply_hammer_strike(action)
                curr_metrics = physics.get_uniformity_metrics()
                fracture_risk = physics.check_fracture_risk()
                
                reward = self.compute_reward(prev_metrics, curr_metrics, fracture_risk)
                
                transition = DemoTransition(
                    state_feature=state_feature,
                    action_gx=gx,
                    action_gy=gy,
                    action_force_level=force_level,
                    expert_reward=reward,
                    step_idx=step,
                )
                episode_transitions.append(transition)
                episode_return += reward
                prev_metrics = curr_metrics
                total_steps += 1
                
                if strike_result["avg_thickness_um"] < 0.2:
                    break
            
            demo_buffer.add_episode(episode_transitions, episode_return)
            episode_rewards_list.append(episode_return)
            
            if verbose and (ep + 1) % max(1, num_episodes // 5) == 0:
                avg_r = np.mean(episode_rewards_list[-max(1, num_episodes // 5):])
                print(f"  Episode {ep+1}/{num_episodes} | "
                      f"Buffer={len(demo_buffer)} | "
                      f"AvgReturn={avg_r:.2f} | "
                      f"LastCV={prev_metrics['coefficient_of_variation']:.4f}")
        
        elapsed = time.time() - start_time
        report = {
            "episodes_collected": num_episodes,
            "total_transitions": total_steps,
            "buffer_size": len(demo_buffer),
            "avg_episode_return": float(np.mean(episode_rewards_list)) if episode_rewards_list else 0.0,
            "max_episode_return": float(np.max(episode_rewards_list)) if episode_rewards_list else 0.0,
            "elapsed_seconds": elapsed,
        }
        
        if verbose:
            print(f"[DemoGen] 完成! 共{total_steps}条转换, 用时{elapsed:.1f}s, "
                  f"平均回报{report['avg_episode_return']:.2f}")
        
        return report
    
    def pretrain_behavior_cloning(
        self,
        demo_buffer: DemoBuffer,
        epochs: Optional[int] = None,
        batch_size: Optional[int] = None,
        verbose: bool = True,
    ) -> dict:
        """
        行为克隆预训练: 用监督学习拟合专家动作
        
        损失:
        - 分类损失: 最大化专家动作 (gx, gy, force) 的 Q 值
        - 回归损失: policy_network 输出逼近专家动作
        
        训练后:
        - Q表 + policy_network 初始化到 "接近专家" 的水平
        - epsilon 初始值降低到 0.3 (减少不必要的探索)
        """
        if len(demo_buffer) < 10:
            return {
                "success": False,
                "message": f"演示数据不足 (需要>=10, 当前{len(demo_buffer)})",
            }
        
        epochs = epochs or self.config.pretrain_epochs
        batch_size = batch_size or self.config.pretrain_batch_size
        lr = self.config.pretrain_lr
        
        if verbose:
            print(f"[Pretrain] 开始行为克隆预训练 | "
                  f"epochs={epochs}, batch={batch_size}, lr={lr}, "
                  f"demos={len(demo_buffer)}")
        
        # --- 统计专家动作分布用于归一化 ---
        all_gx = np.array([t.action_gx for t in demo_buffer.transitions])
        all_gy = np.array([t.action_gy for t in demo_buffer.transitions])
        all_fl = np.array([t.action_force_level for t in demo_buffer.transitions])
        
        expert_prior = np.zeros((
            self.config.grid_size, self.config.grid_size, self.config.force_levels
        ))
        for t in demo_buffer.transitions:
            expert_prior[t.action_gx, t.action_gy, t.action_force_level] += 1
        expert_prior = expert_prior / (expert_prior.sum() + 1e-8)
        
        # --- 初始化: Q表从专家先验的对数开始 ---
        self.q_table = np.log(expert_prior + 1e-8) * 2.0
        self.q_table = self.q_table - self.q_table.mean()
        self.policy_network = np.random.normal(0, 0.001, self.q_table.shape)
        
        loss_history = []
        accuracy_history = []
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            epoch_correct_pos = 0
            epoch_correct_force = 0
            epoch_total = 0
            num_batches = max(1, len(demo_buffer) // batch_size)
            
            for _ in range(num_batches):
                batch = demo_buffer.sample_weighted(batch_size)
                if not batch:
                    continue
                
                batch_loss = 0.0
                batch_total = len(batch)
                
                for t in batch:
                    s = t.state_feature  # (grid, grid)
                    agx, agy, afl = t.action_gx, t.action_gy, t.action_force_level
                    
                    combined = self.q_table + self.policy_network
                    
                    state_gain = np.abs(s[agx, agy]) + 0.5
                    
                    target_q = 10.0 * state_gain
                    current_q = combined[agx, agy, afl]
                    td_error = target_q - current_q
                    
                    self.q_table[agx, agy, afl] += lr * td_error
                    self.policy_network[agx, agy, afl] += lr * td_error * 0.5
                    
                    # 抑制非专家动作: 对最大的非专家动作做轻微降低
                    flat_idx = np.argmax(combined.reshape(-1))
                    pgx, pgy, pfl = np.unravel_index(int(flat_idx), combined.shape)
                    pgx, pgy, pfl = int(pgx), int(pgy), int(pfl)
                    if (pgx, pgy, pfl) != (agx, agy, afl):
                        self.q_table[pgx, pgy, pfl] -= lr * 0.2
                    
                    batch_loss += abs(td_error)
                    epoch_total += 1
                    
                    if (pgx, pgy) == (agx, agy):
                        epoch_correct_pos += 1
                    if pfl == afl:
                        epoch_correct_force += 1
                
                epoch_loss += batch_loss / max(1, batch_total)
            
            avg_loss = epoch_loss / max(1, num_batches)
            pos_acc = epoch_correct_pos / max(1, epoch_total)
            force_acc = epoch_correct_force / max(1, epoch_total)
            loss_history.append(avg_loss)
            accuracy_history.append({"pos": pos_acc, "force": force_acc})
            
            if verbose and (epoch + 1) % max(1, epochs // 5) == 0:
                print(f"  Epoch {epoch+1}/{epochs} | "
                      f"Loss={avg_loss:.4f} | "
                      f"PosAcc={pos_acc*100:.1f}% | "
                      f"ForceAcc={force_acc*100:.1f}%")
        
        # --- 预训练后降低探索率 ---
        self.epsilon = max(self.config.epsilon_min, 0.3)
        self.is_pretrained = True
        
        # --- 归一化Q表到合理范围 ---
        q_std = self.q_table.std() + 1e-8
        self.q_table = (self.q_table - self.q_table.mean()) / q_std * 5.0
        
        report = {
            "success": True,
            "epochs": epochs,
            "demos_used": len(demo_buffer),
            "final_loss": float(loss_history[-1]) if loss_history else 0.0,
            "loss_reduction_pct": float(
                (loss_history[0] - loss_history[-1]) / (abs(loss_history[0]) + 1e-8) * 100
            ) if len(loss_history) >= 2 else 0.0,
            "final_position_accuracy": float(accuracy_history[-1]["pos"]) if accuracy_history else 0.0,
            "final_force_accuracy": float(accuracy_history[-1]["force"]) if accuracy_history else 0.0,
            "initial_epsilon": float(self.epsilon),
            "expert_action_distribution": {
                "gx_mean": float(all_gx.mean()),
                "gy_mean": float(all_gy.mean()),
                "force_level_mean": float(all_fl.mean()),
            },
            "loss_history": loss_history,
        }
        self.pretrain_stats = report
        
        if verbose:
            print(f"[Pretrain] 完成! Loss↓{report['loss_reduction_pct']:.1f}%, "
                  f"位置准确率{report['final_position_accuracy']*100:.1f}%, "
                  f"力度准确率{report['final_force_accuracy']*100:.1f}%")
        
        return report
    
    def update(
        self,
        state: np.ndarray,
        action: HammerParameters,
        reward: float,
        next_state: np.ndarray,
        done: bool = False
    ):
        """
        更新策略参数 (Q-Learning TD + 策略梯度)
        """
        gx, gy = self._discretize_position(*action.position)
        
        force_level = self._value_to_force_level(action.force)
        
        self.action_counts[gx, gy, force_level] += 1
        
        advantage = reward - self.baseline
        self.baseline += 0.01 * advantage
        
        lr = self.config.learning_rate
        self.policy_network[gx, gy, force_level] += lr * advantage
        
        state_feat = self._extract_state_feature(state)
        next_feat = self._extract_state_feature(next_state)
        
        td_target = reward + (0 if done else self.config.gamma * np.max(self.q_table[gx, gy, :]))
        td_error = td_target - self.q_table[gx, gy, force_level]
        self.q_table[gx, gy, force_level] += lr * td_error
        
        self.epsilon = max(
            self.config.epsilon_min,
            self.epsilon * self.config.epsilon_decay
        )
        
        self.rewards_history.append(reward)
    
    def get_policy_stats(self) -> dict:
        """获取策略统计信息"""
        return {
            "epsilon": float(self.epsilon),
            "is_pretrained": self.is_pretrained,
            "total_actions_taken": int(self.action_counts.sum()),
            "avg_reward": float(np.mean(self.rewards_history[-100:]) if self.rewards_history else 0.0),
            "baseline": float(self.baseline),
            "exploration_rate": float(self.epsilon),
            "pretrain": self.pretrain_stats if self.is_pretrained else None,
        }


class RLSession:
    """强化学习会话管理 - 支持预训练流程"""
    
    def __init__(
        self,
        physics_model: GoldFoilPhysicsModel,
        config: Optional[RLConfig] = None,
    ):
        self.physics = physics_model
        self.policy = HammeringPolicy(
            foil_size_mm=physics_model.foil_size_mm,
            config=config
        )
        self.demo_buffer = DemoBuffer(capacity=8000)
        self.prev_metrics = None
        self.prev_state = None
        self.episode_rewards: List[float] = []
        self.current_episode_reward = 0.0
        self.step_count = 0
    
    def generate_and_pretrain(
        self,
        num_demos: int = 25,
        steps_per_demo: int = 50,
        pretrain_epochs: int = 60,
        verbose: bool = True,
    ) -> dict:
        """
        一键执行: 生成演示 + 预训练
        
        这是推荐的训练入口:
        1. 先用启发式生成专家演示
        2. 用Behavior Cloning预训练策略网络
        3. 之后进入在线RL微调
        """
        if verbose:
            print("=" * 60)
            print("🚀 强化学习预训练流程 (演示数据 + Behavior Cloning)")
            print("=" * 60)
        
        demo_report = self.policy.generate_expert_demos(
            demo_buffer=self.demo_buffer,
            num_episodes=num_demos,
            steps_per_episode=steps_per_demo,
            base_grid_size=self.physics.initial_grid_size,
            verbose=verbose,
        )
        
        pretrain_report = self.policy.pretrain_behavior_cloning(
            demo_buffer=self.demo_buffer,
            epochs=pretrain_epochs,
            verbose=verbose,
        )
        
        return {
            "demo_generation": demo_report,
            "behavior_cloning": pretrain_report,
            "buffer_size": len(self.demo_buffer),
        }
    
    def step(
        self,
        mode: ActionType = ActionType.HEURISTIC
    ) -> Tuple[HammerParameters, dict, float, dict]:
        """
        执行一步强化学习
        """
        current_state = self.physics.thickness_um.copy()
        current_metrics = self.physics.get_uniformity_metrics()
        
        if self.prev_metrics is None:
            self.prev_metrics = current_metrics
            self.prev_state = current_state
        
        actual_mode = mode
        if mode == ActionType.PRETRAINED and not self.policy.is_pretrained:
            actual_mode = ActionType.HEURISTIC
        
        action = self.policy.select_action(
            thickness_matrix=current_state,
            temperature=self.physics.temperature_c,
            mode=actual_mode,
        )
        
        strike_result = self.physics.apply_hammer_strike(action)
        
        new_metrics = self.physics.get_uniformity_metrics()
        fracture_risk = self.physics.check_fracture_risk()
        
        reward = self.policy.compute_reward(
            prev_metrics=self.prev_metrics,
            curr_metrics=new_metrics,
            fracture_risk=fracture_risk,
        )
        
        self.policy.update(
            state=self.prev_state,
            action=action,
            reward=reward,
            next_state=current_state,
        )
        
        self.prev_metrics = new_metrics
        self.prev_state = current_state
        self.current_episode_reward += reward
        self.step_count += 1
        
        return action, strike_result, reward, fracture_risk
    
    def run_episode(
        self,
        max_steps: int = 50,
        mode: ActionType = ActionType.HEURISTIC
    ) -> dict:
        """运行完整的一集训练"""
        self.physics.reset()
        self.prev_metrics = None
        self.prev_state = None
        self.current_episode_reward = 0.0
        
        actions_taken = []
        rewards_per_step = []
        
        for step in range(max_steps):
            action, strike_result, reward, fracture_risk = self.step(mode=mode)
            actions_taken.append({
                "step": step,
                "action": {
                    "force_N": action.force,
                    "position_mm": list(action.position),
                },
                "reward": reward,
                "avg_thickness_um": strike_result["avg_thickness_um"],
                "cv": strike_result["thickness_std_um"] / strike_result["avg_thickness_um"] if strike_result["avg_thickness_um"] > 0 else 0,
                "remesh": strike_result.get("remesh"),
            })
            rewards_per_step.append(reward)
            
            if strike_result["avg_thickness_um"] < 0.15:
                break
        
        self.episode_rewards.append(self.current_episode_reward)
        
        final_metrics = self.physics.get_uniformity_metrics()
        final_risk = self.physics.check_fracture_risk()
        
        return {
            "steps_completed": len(actions_taken),
            "total_reward": self.current_episode_reward,
            "avg_reward_per_step": float(np.mean(rewards_per_step)) if rewards_per_step else 0.0,
            "final_metrics": final_metrics,
            "final_fracture_risk": final_risk,
            "actions_taken": actions_taken,
            "policy_stats": self.policy.get_policy_stats(),
        }
