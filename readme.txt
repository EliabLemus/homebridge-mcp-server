# Homebridge MCP Server

A Model Context Protocol (MCP) server that provides AI assistants with the ability to control HomeKit accessories through Homebridge Config UI X API.

## Purpose

This MCP server provides a secure interface for AI assistants to control smart home devices managed by Homebridge, including lights, switches, and other HomeKit-compatible accessories.

## Features

### Current Implementation

- **`list_accessories`** - List all available HomeKit accessories with their current status
- **`get_accessories_layout`** - View home layout organized by rooms  
- **`get_accessory_details`** - Get detailed information about a specific accessory
- **`control_accessory`** - Control accessories (power, brightness, hue, saturation)
- **`quick_toggle`** - Quickly toggle any accessory's power state on/off

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- Homebridge instance running with Config UI X plugin
- Network access to your Homebridge instance (default: homebridge.local:8081)

## Installation

See the step-by-step instructions provided with the files.

## Usage Examples

In Claude Desktop, you can ask:

- "List all my smart home devices"
- "Show me the layout of my home"
- "Turn on the living room lights"
- "Set bedroom lamp brightness to 50%"
- "Get details about my kitchen switch"
- "Toggle the front porch light"
- "Set the mood lighting to blue (hue 240)"

## Configuration

The server connects to Homebridge Config UI X API at `http://homebridge.local:8081` by default. You can customize this by setting the `HOMEBRIDGE_HOST` environment variable:

```bash
# Custom Homebridge host
docker run -e HOMEBRIDGE_HOST="192.168.1.100:8081" homebridge-mcp-server
```

## Architecture

```
Claude Desktop → MCP Gateway → Homebridge MCP Server → Homebridge Config UI X API
                                                      ↓
                                                   HomeKit Accessories
```

## Authentication

The server uses the `/api/auth/noauth` endpoint to obtain bearer tokens for API authentication. Tokens are automatically refreshed as needed.

## Development

### Local Testing

```bash
# Set environment variable for custom Homebridge host (optional)
export HOMEBRIDGE_HOST="192.168.1.100:8081"

# Run directly
python homebridge_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python homebridge_server.py
```

### Adding New Tools

1. Add the function to `homebridge_server.py`
2. Decorate with `@mcp.tool()`  
3. Update the catalog entry with the new tool name
4. Rebuild the Docker image

## Supported Accessory Types

The server works with any HomeKit accessory that supports the following characteristics:

- **Power Control** (On/Off) - Lights, switches, outlets
- **Brightness** - Dimmable lights  
- **Hue** - Color-changing lights
- **Saturation** - Color-changing lights

## API Endpoints Used

- `GET /api/accessories` - List all accessories
- `GET /api/accessories/layout` - Get room layout
- `GET /api/accessories/{uniqueId}` - Get accessory details
- `PUT /api/accessories/{uniqueId}` - Control accessory
- `POST /api/auth/noauth` - Get authentication token

## Troubleshooting

### Tools Not Appearing
- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### Connection Errors
- Verify Homebridge is running and accessible
- Check the HOMEBRIDGE_HOST environment variable
- Ensure Config UI X plugin is installed and enabled
- Test API access: `curl http://homebridge.local:8081/api/auth/noauth`

### Control Issues
- Verify the accessory supports the requested characteristic
- Check that the characteristic has write permissions
- Some accessories may require being "On" before adjusting brightness/color

## Security Considerations

- No hardcoded credentials required
- Authentication tokens automatically managed
- Running as non-root user
- API communication over local network only

## Network Requirements

The server needs network access to your Homebridge instance. Ensure:
- Homebridge Config UI X is running and accessible
- No firewall blocking port 8081
- Server and Homebridge are on the same network (or properly routed)

## License

MIT License