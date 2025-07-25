const { spawn } = require('child_process');

console.log('Testing Context7 MCP Server...');

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

// Test resolve-library-id tool
const toolMessage = {
  jsonrpc: "2.0",
  id: 2,
  method: "tools/call",
  params: {
    name: "resolve-library-id",
    arguments: {
      libraryName: "React"
    }
  }
};

setTimeout(() => {
  mcp.stdin.write(JSON.stringify(toolMessage) + '\n');
}, 1000);

mcp.stdout.on('data', (data) => {
  console.log('MCP Response:', data.toString());
});

mcp.stderr.on('data', (data) => {
  console.error('MCP Error:', data.toString());
});

mcp.on('close', (code) => {
  console.log(`MCP server exited with code ${code}`);
});

// Close after 10 seconds
setTimeout(() => {
  mcp.kill();
}, 10000);