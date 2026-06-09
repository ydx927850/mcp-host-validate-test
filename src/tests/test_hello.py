import unittest
import asyncio
from McpServerTemplate.open_mcp_platform_server import add  # 从你的模块中导入需要测试的函数


class TestHello(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()  # 获取事件循环

    def tearDown(self):
        self.loop.close()  # 清理：关闭事件循环

    def test_add(self):
        result = self.loop.run_until_complete(add(3, 5))  # 运行异步函数
        self.assertEqual(result, 8)  # 断言结果是否正确

if __name__ == '__main__':
    unittest.main()
