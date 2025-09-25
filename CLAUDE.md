# Homebridge MCP Server - Implementation Guide

## Overview

This MCP server provides Claude with smart home control capabilities through the Homebridge Config UI X API. It enables natural language control of HomeKit accessories including lights, switches, and other smart home devices.

## Architecture Details

### API Integration
- **Base URL**: `http://homebridge.local:8081`
- **Authentication**: Bearer token via `/api/auth/noauth`
- **Token Management**: Automatic refresh with 5-minute buffer
- **Timeout**: 10 seconds for all API calls

### Tool Functions

#### `list_accessories()`
- **Purpose**: Discover all available HomeKit accessories
- **API**: `GET /api/accessories`
- **Returns**: Formatted list with device names, types, rooms, and current status
- **Format**: Groups by device with power, brightness, hue, saturation states

#### `get_accessories_layout()`
- **Purpose**: Show home organization by rooms
- **API**: `GET /api/accessories/layout`
- **Returns**: Room-based grouping with device counts
- **Use Case**: Understanding home structure and device locations

#### `get_accessory_details(unique_id)`
- **Purpose**: Deep dive into specific device capabilities
- **API**: `GET /api/accessories/{uniqueId}`
- **Returns**: Full characteristic list with read/write permissions
- **Parameters**: `unique_id` (required) - Device identifier from list_accessories

#### `control_accessory(unique_id, action, value)`
- **Purpose**: Primary control interface for devices
- **API**: `PUT /api/accessories/{uniqueId}`
- **Actions Supported**:
  - `power/on/off` - Toggle or set power state
  - `brightness` - Set brightness (0-100)
  - `hue` - Set color hue (0-360)  
  - `saturation` - Set color saturation (0-100)
- **Parameters**: All strings with validation and conversion

#### `quick_toggle(unique_id)`
- **Purpose**: Fast on/off toggle without knowing current state
- **API**: `GET` then `PUT /api/accessories/{uniqueId}`
- **Logic**: Reads current state, inverts it, applies change
- **Returns**: Clear before/after status indication

## Implementation Patterns

### Error Handling
```python
# Three-tier error handling:
1. Parameter validation (empty strings, required fields)
2. API communication errors (HTTP status, timeouts)  
3. Data processing errors (JSON parsing, missing fields)

# All errors return user-friendly messages with ❌ prefix
```

### Token Management
```python
# Global token caching with expiration:
- _auth_token: Current bearer token
- _token_expires: UTC expiration timestamp  
- 5-minute buffer before expiration
- Automatic refresh on first use after expiration
```

### API Response Processing
```python
# Consistent pattern:
1. Extract relevant data from JSON response
2. Format for human readability
3. Add appropriate emoji indicators
4. Handle missing/null values gracefully
```

## Usage Patterns for Claude

### Natural Language Mapping

**Device Discovery**:
- "What smart home devices do I have?" → `list_accessories()`
- "Show me my home layout" → `get_accessories_layout()`
- "Tell me about my kitchen lights" → Find ID then `get_accessory_details()`

**Basic Control**:
- "Turn on the living room lamp" → Find ID then `control_accessory(id, "on", "")`
- "Turn off bedroom lights" → Find ID then `control_accessory(id, "off", "")`
- "Toggle the front porch light" → Find ID then `quick_toggle()`

**Advanced Control**:
- "Dim the kitchen lights to 30%" → `control_accessory(id, "brightness", "30")`
- "Set mood lighting to blue" → `control_accessory(id, "hue", "240")`
- "Make the lights more saturated" → Get current, then increase saturation

### Multi-Step Workflows

1. **Device Identification**: Use `list_accessories()` to find device names and IDs
2. **Status Check**: Use `get_accessory_details()` for current state and capabilities  
3. **Control Action**: Use `control_accessory()` or `quick_toggle()` for changes
4. **Verification**: Can re-check status to confirm changes

### Error Recovery

- **Device Not Found**: Re-run `list_accessories()` to refresh device list
- **Permission Denied**: Check `get_accessory_details()` for write permissions
- **Value Out of Range**: Provide valid ranges in error message
- **Network Issues**: Suggest checking Homebridge connectivity

## Configuration Notes

### Environment Variables
- `HOMEBRIDGE_HOST`: Override default homebridge.local:8081
- Useful for custom IPs: `192.168.1.100:8081`
- No authentication environment variables needed

### Network Requirements  
- Same network as Homebridge instance
- Port 8081 accessible
- Config UI X plugin enabled on Homebridge
- No VPN/firewall blocking local communication

### Homebridge Compatibility
- Requires homebridge-config-ui-x plugin
- API version compatibility: Works with current stable releases
- No specific Homebridge version requirements
- Compatible with all HomeKit accessory types

## Limitations and Considerations

### API Limitations
- No authentication beyond bearer tokens
- Token expires (handled automatically)  
- Rate limiting may apply (not currently handled)
- Some accessories may have device-specific quirks

### HomeKit Characteristic Support
- Only implements common characteristics (On, Brightness, Hue, Saturation)
- Other characteristics are displayed but not controllable
- Complex accessories may need custom handling

### Network Dependencies
- Requires local network access to Homebridge
- No cloud/remote access capabilities
- Assumes Homebridge stability and availability

## Future Enhancement Opportunities

1. **Scene Control**: Implement HomeKit scene activation
2. **Advanced Color Control**: RGB/HSV conversion utilities
3. **Automation**: Time-based or sensor-triggered controls
4. **Room-Level Control**: Bulk operations on room devices
5. **Status Monitoring**: Real-time status updates
6. **Error Recovery**: Retry logic for transient failures

## Security Considerations

- No credential storage required
- Bearer tokens are ephemeral and auto-managed  
- Local network communication only
- Non-root container execution
- No sensitive data logging