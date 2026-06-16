"""
塑性仿真独立Worker进程

使用 multiprocessing 实现真正的独立进程，避免GIL限制，
将塑性仿真计算从主API进程中分离出来，提高系统响应性和稳定性。

进程间通信 (IPC)：
- 使用 multiprocessing.Queue 传递命令和结果
- 支持异步命令执行
- 支持状态查询

消息协议：
命令消息:
    {
        "cmd": "strike" | "reset" | "anneal" | "get_state" | "get_thickness" | "get_mesh_quality" | "stop",
        "request_id": str,
        "data": dict
    }

结果消息:
    {
        "request_id": str,
        "type": "strike_result" | "state" | "thickness" | "mesh_quality" | "event" | "error",
        "data": dict,
        "timestamp": float
    }
"""
import os
import sys
import time
import json
import multiprocessing
from multiprocessing import Process, Queue, Event
from typing import Dict, Any, Optional, Callable

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from modules.common import RedisBus, REDIS_CHANNELS, load_material_config
from physics.physics_model import (
    GoldFoilPhysicsModel,
    HammerParameters,
    MaterialProperties,
    RemeshConfig,
)


class SimulationWorkerProcess:
    """
    塑性仿真独立Worker进程管理器
    
    在独立进程中运行塑性仿真计算，通过队列与主进程通信。
    """

    def __init__(self, grid_size: int = None, use_redis: bool = True):
        self._cmd_queue: Queue = Queue(maxsize=100)
        self._result_queue: Queue = Queue(maxsize=200)
        self._stop_event: Event = Event()
        self._process: Optional[Process] = None
        self._grid_size = grid_size
        self._use_redis = use_redis
        self._request_callbacks: Dict[str, Callable] = {}
        self._running = False

    def start(self) -> None:
        """启动独立仿真进程"""
        if self._process and self._process.is_alive():
            print(f"[SimulationWorker] 进程已在运行，PID: {self._process.pid}")
            return

        self._stop_event.clear()
        self._process = Process(
            target=self._worker_loop,
            args=(
                self._cmd_queue,
                self._result_queue,
                self._stop_event,
                self._grid_size,
                self._use_redis,
            ),
            name="PlasticitySimulationWorker",
            daemon=True,
        )
        self._process.start()
        self._running = True
        print(f"[SimulationWorker] 进程已启动，PID: {self._process.pid}")

    def stop(self, timeout: float = 5.0) -> None:
        """停止仿真进程"""
        if not self._process or not self._process.is_alive():
            return

        print(f"[SimulationWorker] 正在停止进程，PID: {self._process.pid}")
        self._stop_event.set()
        
        try:
            self._cmd_queue.put({"cmd": "stop", "request_id": "stop_internal", "data": {}})
        except Exception:
            pass

        self._process.join(timeout=timeout)
        if self._process.is_alive():
            print(f"[SimulationWorker] 进程未正常退出，强制终止")
            self._process.terminate()
            self._process.join(timeout=2.0)

        self._running = False
        print("[SimulationWorker] 进程已停止")

    def restart(self) -> None:
        """重启仿真进程"""
        self.stop()
        time.sleep(0.5)
        self.start()

    def is_alive(self) -> bool:
        """检查进程是否存活"""
        return self._process is not None and self._process.is_alive()

    def send_command(self, cmd: str, data: Dict[str, Any] = None, callback: Callable = None) -> str:
        """
        向Worker进程发送命令
        
        参数:
            cmd: 命令类型
            data: 命令数据
            callback: 结果回调函数（可选）
            
        返回:
            request_id: 请求ID
        """
        if not self.is_alive():
            raise RuntimeError("仿真进程未运行，请先调用 start()")

        request_id = f"req_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
        
        message = {
            "cmd": cmd,
            "request_id": request_id,
            "data": data or {},
        }

        if callback:
            self._request_callbacks[request_id] = callback

        self._cmd_queue.put(message)
        return request_id

    def get_result(self, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        从结果队列获取结果（非阻塞）
        
        参数:
            timeout: 等待超时时间（秒）
            
        返回:
            结果字典，或None（队列为空时）
        """
        try:
            result = self._result_queue.get(timeout=timeout)
            return result
        except Exception:
            return None

    def process_results(self, max_count: int = 10) -> int:
        """
        处理所有待处理的结果，调用对应的回调函数
        
        参数:
            max_count: 最大处理数量
            
        返回:
            处理的结果数量
        """
        count = 0
        for _ in range(max_count):
            result = self.get_result(timeout=0.01)
            if result is None:
                break

            request_id = result.get("request_id")
            if request_id and request_id in self._request_callbacks:
                try:
                    callback = self._request_callbacks.pop(request_id)
                    callback(result)
                except Exception as e:
                    print(f"[SimulationWorker] 回调执行失败: {e}")

            count += 1

        return count

    @staticmethod
    def _worker_loop(
        cmd_queue: Queue,
        result_queue: Queue,
        stop_event: Event,
        grid_size: Optional[int],
        use_redis: bool,
    ) -> None:
        """
        Worker进程主循环（在独立进程中运行）
        """
        print(f"[SimulationWorker] 子进程已启动，PID: {os.getpid()}")

        config = load_material_config()
        physics_cfg = config.get("physics", {})
        mat_cfg = config.get("material", {})
        remesh_cfg = config.get("remesh", {})

        foil_size = physics_cfg.get("foil_size_mm", 150.0)
        initial_grid = grid_size or physics_cfg.get("default_grid_size", 48)

        material = MaterialProperties(**mat_cfg)
        remesh_config = RemeshConfig(**remesh_cfg) if remesh_cfg.get("enable", True) else None

        physics = GoldFoilPhysicsModel(
            grid_size=initial_grid,
            foil_size_mm=foil_size,
            material=material,
            remesh_config=remesh_config,
        )

        bus: Optional[RedisBus] = None
        if use_redis:
            try:
                bus = RedisBus()
                print(f"[SimulationWorker] Redis 连接状态: {bus.available}")
            except Exception as e:
                print(f"[SimulationWorker] Redis 连接失败: {e}")

        foil_id = "NF-WORKER-001"
        session_id = f"session-{int(time.time())}"
        strike_history = []

        def publish(channel: str, data: Dict[str, Any]):
            if bus and bus.available:
                bus.publish(channel, data)
            result_queue.put({
                "request_id": data.get("request_id", ""),
                "type": channel.replace(":", "_"),
                "data": data,
                "timestamp": time.time(),
            })

        while not stop_event.is_set():
            try:
                message = cmd_queue.get(timeout=0.1)
                if not isinstance(message, dict):
                    continue

                cmd = message.get("cmd")
                request_id = message.get("request_id", "")
                data = message.get("data", {})

                if cmd == "stop":
                    print("[SimulationWorker] 收到停止命令")
                    break

                elif cmd == "strike":
                    hammer = HammerParameters(
                        force=data.get("force", 500.0),
                        position=tuple(data.get("position", [0.0, 0.0])),
                        radius_mm=data.get("radius_mm", 15.0),
                        strike_duration_ms=data.get("strike_duration_ms", 50.0),
                    )
                    ambient_temp = data.get("ambient_temp_c", 25.0)
                    result = physics.apply_hammer_strike(hammer, ambient_temp_c=ambient_temp)

                    record = {"request_id": request_id, "source": "worker", **result}
                    strike_history.append(record)
                    if len(strike_history) > 1000:
                        strike_history = strike_history[-1000:]

                    publish(REDIS_CHANNELS["strike_result"], {
                        "request_id": request_id,
                        "strike": result,
                        "foil_id": foil_id,
                        "session_id": session_id,
                        "timestamp": time.time(),
                    })

                    thickness_dist = physics.get_thickness_distribution()
                    publish(REDIS_CHANNELS["thickness_updated"], {
                        "thickness_distribution": thickness_dist,
                        "metrics": thickness_dist["metrics"],
                        "foil_id": foil_id,
                        "session_id": session_id,
                        "strike_num": result["strike_num"],
                        "timestamp": time.time(),
                    })

                    if result.get("remesh") and result["remesh"].get("action") != "noop":
                        publish(REDIS_CHANNELS["mesh_quality"], {
                            "remesh_event": result["remesh"],
                            "quality_report": physics.get_mesh_quality_report(),
                            "timestamp": time.time(),
                        })

                elif cmd == "reset":
                    physics.reset()
                    session_id = f"session-{int(time.time())}"
                    strike_history = []
                    publish(REDIS_CHANNELS["system_event"], {
                        "type": "reset_complete",
                        "session_id": session_id,
                        "request_id": request_id,
                        "timestamp": time.time(),
                    })

                elif cmd == "anneal":
                    temp_c = data.get("temperature_c", 400.0)
                    duration_min = data.get("duration_min", 10.0)
                    result = physics.apply_annealing(temp_c, duration_min)
                    publish(REDIS_CHANNELS["system_event"], {
                        "type": "anneal_complete",
                        "result": result,
                        "metrics": physics.get_uniformity_metrics(),
                        "request_id": request_id,
                        "timestamp": time.time(),
                    })

                elif cmd == "get_state":
                    thickness_data = physics.get_thickness_distribution()
                    result_queue.put({
                        "request_id": request_id,
                        "type": "state",
                        "data": {
                            "foil_id": foil_id,
                            "session_id": session_id,
                            "total_strikes": physics.strike_count,
                            "total_elongation": physics.total_elongation,
                            "thickness_distribution": thickness_data,
                            "fracture_risk": physics.check_fracture_risk(0.1),
                            "temperature_c": float(physics.temperature_c.mean()),
                            "plastic_strain": float(physics.plastic_strain.mean()),
                            "grid_size": physics.grid_size,
                        },
                        "timestamp": time.time(),
                    })

                elif cmd == "get_thickness":
                    h = physics.thickness_um
                    h_norm = (h - h.min()) / (h.max() - h.min() + 1e-8)
                    result_queue.put({
                        "request_id": request_id,
                        "type": "thickness",
                        "data": {
                            "grid_size": physics.grid_size,
                            "foil_size_mm": foil_size,
                            "thickness_um": h.tolist(),
                            "normalized": h_norm.tolist(),
                            "min_um": float(h.min()),
                            "max_um": float(h.max()),
                            "mean_um": float(h.mean()),
                            "std_um": float(h.std()),
                        },
                        "timestamp": time.time(),
                    })

                elif cmd == "get_mesh_quality":
                    result_queue.put({
                        "request_id": request_id,
                        "type": "mesh_quality",
                        "data": physics.get_mesh_quality_report(),
                        "timestamp": time.time(),
                    })

                elif cmd == "ping":
                    result_queue.put({
                        "request_id": request_id,
                        "type": "pong",
                        "data": {"pid": os.getpid(), "alive": True},
                        "timestamp": time.time(),
                    })

            except Exception as e:
                print(f"[SimulationWorker] 处理命令失败: {e}")
                import traceback
                traceback.print_exc()
                try:
                    result_queue.put({
                        "request_id": request_id if 'request_id' in locals() else "",
                        "type": "error",
                        "data": {"error": str(e)},
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

        print(f"[SimulationWorker] 子进程退出，PID: {os.getpid()}")

    def execute_sync(self, cmd: str, data: Dict[str, Any] = None, timeout: float = 5.0) -> Dict[str, Any]:
        """
        同步执行命令（等待结果返回）
        
        参数:
            cmd: 命令类型
            data: 命令数据
            timeout: 超时时间（秒）
            
        返回:
            结果字典
            
        异常:
            TimeoutError: 超时
            RuntimeError: 进程未运行
        """
        if not self.is_alive():
            raise RuntimeError("仿真进程未运行")

        result_holder = {"result": None, "ready": False}

        def callback(result):
            result_holder["result"] = result
            result_holder["ready"] = True

        request_id = self.send_command(cmd, data, callback=callback)

        start_time = time.time()
        while not result_holder["ready"] and time.time() - start_time < timeout:
            self.process_results(max_count=1)
            time.sleep(0.01)

        if not result_holder["ready"]:
            raise TimeoutError(f"命令 {cmd} 执行超时（{timeout}s）")

        return result_holder["result"]


class SimulationWorkerManager:
    """
    仿真Worker管理器 - 单例模式，方便全局访问
    """
    _instance: Optional["SimulationWorkerManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._worker = SimulationWorkerProcess()
        return cls._instance

    @property
    def worker(self) -> SimulationWorkerProcess:
        return self._worker

    def start(self) -> None:
        if not self._worker.is_alive():
            self._worker.start()

    def stop(self) -> None:
        self._worker.stop()


def run_standalone_worker():
    """
    命令行模式运行独立Worker进程
    """
    import argparse
    parser = argparse.ArgumentParser(description="塑性仿真独立Worker进程")
    parser.add_argument("--grid-size", type=int, default=None, help="网格大小")
    parser.add_argument("--no-redis", action="store_true", help="禁用Redis（仅使用队列）")
    args = parser.parse_args()

    worker = SimulationWorkerProcess(grid_size=args.grid_size, use_redis=not args.no_redis)
    
    try:
        worker.start()
        print("[StandaloneWorker] 仿真Worker已启动，按Ctrl+C停止")
        
        while worker.is_alive():
            time.sleep(1.0)
            worker.process_results(max_count=10)
            
    except KeyboardInterrupt:
        print("\n[StandaloneWorker] 收到停止信号")
    finally:
        worker.stop()
        print("[StandaloneWorker] 已退出")


if __name__ == "__main__":
    run_standalone_worker()
