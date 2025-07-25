const { spawn } = require('child_process');

console.log('Testing Context7 get-library-docs tool...');

// Test the MCP server directly using cmd.exe (Windows)
const mcp = spawn('cmd.exe', ['/c', 'npx', '-y', '@upstash/context7-mcp'], {
  stdio: ['pipe', 'pipe', 'pipe']
});

// Send MCP initialization message
const initMessage = {
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2024-11-05",
    capabilities: {
      tools: {}
    },
    clientInfo: {
      name: "test-client",
      version: "1.0.0"
    }
  }
};

mcp.stdin.write(JSON.stringify(initMessage) + '\n');

// Test get-library-docs tool with React documentation
const toolMessage = {
  jsonrpc: "2.0",
  id: 2,
  method: "tools/call",
  params: {
    name: "get-library-docs",
    arguments: {
      context7CompatibleLibraryID: "/reactjs/react.dev",
      topic: "hooks",
      tokens: 5000
    }
  }
};

setTimeout(() => {
  mcp.stdin.write(JSON.stringify(toolMessage) + '\n');
}, 1000);

mcp.stdout.on('data', (data) => {
  const response = data.toString();
  console.log('MCP Response Length:', response.length);
  // Only show first 1000 characters to avoid overwhelming output
  console.log('MCP Response Preview:', response.substring(0, 1000) + '...');
});

mcp.stderr.on('data', (data) => {
  console.error('MCP Error:', data.toString());
});

mcp.on('close', (code) => {
  console.log(`MCP server exited with code ${code}`);
});

// Close after 15 seconds
setTimeout(() => {
  mcp.kill();
}, 15000);