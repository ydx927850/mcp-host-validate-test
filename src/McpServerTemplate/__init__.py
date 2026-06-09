from McpServerTemplate.open_platform_server import server as mcp

def main():
    mcp.run(transport="sse")

if __name__ == "__main__":
    main()
