import { MCPController, MCPTool } from '@anthropic-ai/sdk';

@MCPController({
  name: 'test-mcp-tool',
  description: 'A test MCP tool controller'
})
export class TestMcpController {

  @MCPTool({
    name: 'hello',
    description: 'Say hello'
  })
  async hello(name: string): Promise<string> {
    return `Hello, ${name}!`;
  }
}
