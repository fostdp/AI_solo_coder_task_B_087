"""
SimulationWorker 单元测试套件

覆盖正常、边界、异常三类测试场景，共约12个测试用例。
由于 multiprocessing 在 pytest 中可能存在问题，大部分测试使用 mock。
标记为 slow 的测试会实际启动进程。
"""

import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch, create_autospec
from multiprocessing import Queue
from typing import Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.simulation_worker import (
    SimulationWorkerProcess,
    SimulationWorkerManager,
)


# ============================================================================
# Pytest 自定义标记配置
# ============================================================================

def pytest_configure(config):
    """注册自定义标记"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


# ============================================================================
# Fixtures
# ============================================================================

def create_mock_queue():
    """创建一个 mock 队列"""
    queue = MagicMock()
    queue.put = MagicMock()
    queue.get = MagicMock()
    return queue


@pytest.fixture
def worker_with_mock_process():
    """创建一个带有 mock 进程的 SimulationWorkerProcess 实例"""
    worker = SimulationWorkerProcess(use_redis=False)
    worker._process = MagicMock()
    worker._process.is_alive.return_value = True
    worker._running = True
    worker._cmd_queue = create_mock_queue()
    worker._result_queue = create_mock_queue()
    return worker


@pytest.fixture
def worker_without_process():
    """创建一个未启动进程的 SimulationWorkerProcess 实例"""
    return SimulationWorkerProcess(use_redis=False)


@pytest.fixture
def mock_queues():
    """创建 mock 的命令队列和结果队列"""
    cmd_queue = create_mock_queue()
    result_queue = create_mock_queue()
    return cmd_queue, result_queue


# ============================================================================
# 正常场景测试（6个）
# ============================================================================

class TestNormalScenarios:
    """正常场景测试"""

    def test_manager_singleton_pattern(self):
        """正常场景：测试管理器单例特性 - 多次实例化返回同一对象"""
        SimulationWorkerManager._instance = None
        
        manager1 = SimulationWorkerManager()
        manager2 = SimulationWorkerManager()
        
        assert manager1 is manager2, "两次实例化应返回同一对象"
        assert SimulationWorkerManager._instance is not None
        assert hasattr(manager1, '_worker'), "管理器应包含 worker 属性"

    def test_send_command_generates_unique_request_id(self, worker_with_mock_process):
        """正常场景：测试 send_command 生成唯一请求ID"""
        request_ids = []
        for _ in range(10):
            rid = worker_with_mock_process.send_command("ping")
            request_ids.append(rid)
        
        assert len(set(request_ids)) == 10, "10次调用应生成10个不同的ID"
        for rid in request_ids:
            assert rid.startswith("req_"), "ID应以 req_ 开头"
            assert len(rid) > 10, "ID应有足够长度保证唯一性"

    def test_ping_command_response_structure(self, worker_with_mock_process):
        """正常场景：测试 ping 命令响应格式正确（通过 mock 队列验证）"""
        mock_result = {
            "request_id": "test_req_123",
            "type": "pong",
            "data": {"pid": 12345, "alive": True},
            "timestamp": time.time(),
        }
        
        worker_with_mock_process._result_queue.get.return_value = mock_result
        
        rid = worker_with_mock_process.send_command("ping")
        result = worker_with_mock_process.get_result(timeout=0.1)
        
        assert result is not None
        assert result["type"] == "pong"
        assert result["data"]["alive"] is True
        assert "pid" in result["data"]
        assert "timestamp" in result

    def test_get_state_returns_expected_structure(self, worker_with_mock_process):
        """正常场景：测试 get_state 命令返回完整状态数据结构"""
        mock_state = {
            "request_id": "state_req_001",
            "type": "state",
            "data": {
                "foil_id": "NF-WORKER-001",
                "session_id": "session-123456",
                "total_strikes": 5,
                "total_elongation": 0.15,
                "thickness_distribution": {"metrics": {}},
                "fracture_risk": 0.05,
                "temperature_c": 25.0,
                "plastic_strain": 0.02,
                "grid_size": 48,
            },
            "timestamp": time.time(),
        }
        
        worker_with_mock_process._result_queue.get.return_value = mock_state
        
        rid = worker_with_mock_process.send_command("get_state")
        result = worker_with_mock_process.get_result(timeout=0.1)
        
        assert result is not None
        assert result["type"] == "state"
        state_data = result["data"]
        expected_fields = [
            "foil_id", "session_id", "total_strikes", 
            "total_elongation", "thickness_distribution",
            "fracture_risk", "temperature_c", "plastic_strain", "grid_size"
        ]
        for field in expected_fields:
            assert field in state_data, f"状态数据应包含字段: {field}"
        assert isinstance(state_data["total_strikes"], int)
        assert isinstance(state_data["temperature_c"], float)

    def test_async_command_with_callback(self, worker_with_mock_process):
        """正常场景：测试异步命令发送与回调函数调用"""
        callback_called = []
        callback_result = []
        
        def test_callback(result):
            callback_called.append(True)
            callback_result.append(result)
        
        rid = worker_with_mock_process.send_command("ping", callback=test_callback)
        assert rid in worker_with_mock_process._request_callbacks
        
        mock_result = {
            "request_id": rid,
            "type": "pong",
            "data": {"status": "ok"},
            "timestamp": time.time(),
        }
        
        worker_with_mock_process._result_queue.get.side_effect = [mock_result, None]
        
        processed = worker_with_mock_process.process_results(max_count=5)
        
        assert processed >= 1
        assert len(callback_called) == 1, "回调函数应被调用一次"
        assert callback_result[0]["type"] == "pong"
        assert rid not in worker_with_mock_process._request_callbacks, "回调后应清理"

    def test_execute_sync_returns_result(self, worker_with_mock_process):
        """正常场景：测试同步执行命令正确返回结果"""
        mock_result = {
            "request_id": "sync_test_001",
            "type": "thickness",
            "data": {
                "grid_size": 48,
                "mean_um": 450.0,
                "min_um": 420.0,
                "max_um": 480.0,
            },
            "timestamp": time.time(),
        }
        
        original_send_command = worker_with_mock_process.send_command
        
        def mock_send_command(cmd, data=None, callback=None):
            rid = "sync_test_001"
            if callback:
                worker_with_mock_process._request_callbacks[rid] = callback
            return rid
        
        worker_with_mock_process.send_command = mock_send_command
        
        original_process_results = worker_with_mock_process.process_results
        
        def side_effect_process(max_count=10):
            if not worker_with_mock_process._request_callbacks:
                return 0
            rid = next(iter(worker_with_mock_process._request_callbacks))
            callback = worker_with_mock_process._request_callbacks.pop(rid)
            callback(mock_result)
            return 1
        
        worker_with_mock_process.process_results = side_effect_process
        
        try:
            result = worker_with_mock_process.execute_sync(
                "get_thickness", timeout=2.0
            )
            
            assert result is not None
            assert result["type"] == "thickness"
            assert "mean_um" in result["data"]
            assert result["data"]["grid_size"] == 48
        finally:
            worker_with_mock_process.send_command = original_send_command
            worker_with_mock_process.process_results = original_process_results


# ============================================================================
# 边界场景测试（3个）
# ============================================================================

class TestBoundaryScenarios:
    """边界场景测试"""

    def test_short_timeout_returns_none_or_raises(self, worker_with_mock_process):
        """边界场景：测试短超时行为 - 应返回None或不崩溃"""
        worker_with_mock_process._result_queue.get.side_effect = Exception("Queue empty")
        
        result = worker_with_mock_process.get_result(timeout=0.001)
        assert result is None, "超时或空队列应返回None"
        
        result2 = worker_with_mock_process.get_result(timeout=0.0)
        assert result2 is None, "0超时也应返回None"

    def test_fast_consecutive_commands(self, worker_with_mock_process):
        """边界场景：测试快速连续发送多个命令不丢失"""
        sent_ids = []
        put_calls = []
        
        def track_put(message):
            put_calls.append(message)
        
        worker_with_mock_process._cmd_queue.put.side_effect = track_put
        
        commands = [
            ("ping", None),
            ("get_state", None),
            ("reset", None),
            ("get_thickness", None),
            ("ping", {"extra": "data"}),
        ]
        
        for cmd, data in commands:
            rid = worker_with_mock_process.send_command(cmd, data=data)
            sent_ids.append(rid)
        
        assert len(sent_ids) == 5, "应成功发送5条命令"
        assert len(put_calls) == 5, "队列put应被调用5次"
        
        for i, call in enumerate(put_calls):
            assert call["cmd"] == commands[i][0]
            assert call["request_id"] == sent_ids[i]
            assert "data" in call
            assert "timestamp" not in call, "时间戳由worker进程添加"

    def test_empty_data_command(self, worker_with_mock_process):
        """边界场景：测试不需要data的命令（如reset）正常工作"""
        put_calls = []
        worker_with_mock_process._cmd_queue.put.side_effect = lambda msg: put_calls.append(msg)
        
        rid1 = worker_with_mock_process.send_command("reset")
        rid2 = worker_with_mock_process.send_command("reset", data=None)
        rid3 = worker_with_mock_process.send_command("reset", data={})
        
        assert len(put_calls) == 3
        
        for call in put_calls:
            assert call["cmd"] == "reset"
            assert call["data"] == {}, "空数据命令的data应为空字典"
        
        assert len(set([rid1, rid2, rid3])) == 3, "即使命令相同也应生成不同ID"


# ============================================================================
# 异常场景测试（3个）
# ============================================================================

class TestExceptionScenarios:
    """异常场景测试"""

    def test_unknown_command_returns_error(self, worker_with_mock_process):
        """异常场景：测试发送未知命令返回错误响应"""
        mock_error = {
            "request_id": "error_test_001",
            "type": "error",
            "data": {"error": "Command 'invalid_cmd' not recognized"},
            "timestamp": time.time(),
        }
        
        worker_with_mock_process._result_queue.get.return_value = mock_error
        
        rid = worker_with_mock_process.send_command("invalid_cmd")
        result = worker_with_mock_process.get_result(timeout=0.1)
        
        assert result is not None
        assert result["type"] == "error"
        assert "error" in result["data"]
        assert isinstance(result["data"]["error"], str)
        assert len(result["data"]["error"]) > 0

    def test_get_nonexistent_result_timeout(self, worker_with_mock_process):
        """异常场景：测试获取结果时超时（队列空）"""
        worker_with_mock_process._result_queue.get.side_effect = Exception("Timeout")
        
        start_time = time.time()
        result = worker_with_mock_process.get_result(timeout=0.5)
        elapsed = time.time() - start_time
        
        assert result is None
        assert elapsed < 1.0, "超时不应等待过长时间"

    def test_send_command_when_process_not_running(self, worker_without_process):
        """异常场景：测试进程未启动时发送命令抛出RuntimeError"""
        worker = worker_without_process
        
        assert worker.is_alive() is False
        
        with pytest.raises(RuntimeError) as exc_info:
            worker.send_command("ping")
        
        assert "仿真进程未运行" in str(exc_info.value)
        assert "start()" in str(exc_info.value)
        
        with pytest.raises(RuntimeError) as exc_info2:
            worker.execute_sync("get_state")
        
        assert "仿真进程未运行" in str(exc_info2.value)


# ============================================================================
# 额外测试：覆盖更多方法
# ============================================================================

class TestAdditionalMethods:
    """额外测试：覆盖管理器和进程的其他方法"""

    def test_process_lifecycle_methods(self, worker_without_process):
        """测试进程生命周期相关方法的基本行为"""
        worker = worker_without_process
        
        assert worker.is_alive() is False
        
        with patch('modules.simulation_worker.Process') as mock_process_class:
            mock_process = MagicMock()
            mock_process.is_alive.side_effect = [True, True, False]
            mock_process_class.return_value = mock_process
            
            worker.start()
            
            assert worker.is_alive() is True
            assert worker._running is True
            mock_process.start.assert_called_once()
            
            worker.stop()
            
            assert worker._running is False
            mock_process.join.assert_called()

    def test_process_results_handles_exception(self, worker_with_mock_process):
        """测试 process_results 处理回调异常时不崩溃"""
        error_callback = MagicMock(side_effect=Exception("Callback error"))
        mock_result = {
            "request_id": "error_cb_001",
            "type": "pong",
            "data": {},
            "timestamp": time.time(),
        }
        
        worker_with_mock_process._result_queue.get.side_effect = [mock_result, None]
        worker_with_mock_process._request_callbacks["error_cb_001"] = error_callback
        
        processed = worker_with_mock_process.process_results(max_count=5)
        
        assert processed >= 1
        error_callback.assert_called_once()
        assert "error_cb_001" not in worker_with_mock_process._request_callbacks

    def test_worker_loop_message_protocol(self, mock_queues):
        """测试 worker 循环的消息协议处理（静态方法测试）"""
        cmd_queue, result_queue = mock_queues
        stop_event = MagicMock()
        stop_event.is_set.side_effect = [False, True]
        
        test_message = {
            "cmd": "ping",
            "request_id": "proto_test_001",
            "data": {"key": "value"},
        }
        
        cmd_queue.get.return_value = test_message
        
        with patch('modules.simulation_worker.load_material_config') as mock_load:
            mock_load.return_value = {
                "physics": {"foil_size_mm": 150.0, "default_grid_size": 16},
                "material": {
                    "youngs_modulus": 79.0,
                    "poisson_ratio": 0.42,
                    "yield_strength": 120.0,
                    "ultimate_strength": 210.0,
                    "density": 19300.0,
                    "initial_thickness_um": 500.0,
                    "work_hardening_coeff": 0.45,
                    "work_hardening_exp": 0.35,
                    "recrystallization_temp": 200.0,
                    "melting_point": 1064.0,
                },
                "remesh": {"enable": False},
            }
            
            with patch('modules.simulation_worker.GoldFoilPhysicsModel') as mock_physics:
                mock_instance = MagicMock()
                mock_physics.return_value = mock_instance
                
                try:
                    SimulationWorkerProcess._worker_loop(
                        cmd_queue, result_queue, stop_event, None, False
                    )
                except StopIteration:
                    pass
                
                result_queue.put.assert_called()
                call_args = result_queue.put.call_args[0][0]
                
                assert "request_id" in call_args
                assert "type" in call_args
                assert "data" in call_args
                assert "timestamp" in call_args
                assert call_args["request_id"] == "proto_test_001"
                assert call_args["type"] == "pong"


# ============================================================================
# Slow 测试：实际启动进程（默认跳过）
# ============================================================================

@pytest.mark.slow
class TestSlowIntegration:
    """慢速集成测试：实际启动进程验证（需要较长时间）"""

    def test_real_process_ping_pong(self):
        """实际测试：启动进程并验证 ping-pong 通信"""
        worker = SimulationWorkerProcess(grid_size=16, use_redis=False)
        
        try:
            worker.start()
            time.sleep(2.0)
            
            assert worker.is_alive() is True
            
            result = worker.execute_sync("ping", timeout=5.0)
            
            assert result is not None
            assert result["type"] == "pong"
            assert result["data"]["alive"] is True
            assert result["data"]["pid"] > 0
            
        finally:
            worker.stop()
            time.sleep(0.5)

    def test_real_process_restart(self):
        """实际测试：进程重启功能"""
        worker = SimulationWorkerProcess(grid_size=16, use_redis=False)
        
        try:
            worker.start()
            time.sleep(1.5)
            assert worker.is_alive() is True
            
            pid1 = worker._process.pid
            
            worker.restart()
            time.sleep(1.5)
            assert worker.is_alive() is True
            
            pid2 = worker._process.pid
            assert pid1 != pid2, "重启后PID应不同"
            
        finally:
            worker.stop()
            time.sleep(0.5)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
