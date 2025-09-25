#!/usr/bin/env python3
"""
Simple Homebridge MCP Server - Control HomeKit accessories through Homebridge Config UI X API
"""
import os
import sys
import logging
from datetime import datetime, timezone
import httpx
import json
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("homebridge-server")

# Initialize MCP server - NO PROMPT PARAMETER!
mcp = FastMCP("homebridge")

# Configuration
HOMEBRIDGE_HOST = os.environ.get("HOMEBRIDGE_HOST", "homebridge.local:8081")
HOMEBRIDGE_BASE_URL = f"http://{HOMEBRIDGE_HOST}"

# Token cache
_auth_token = None
_token_expires = None

# === UTILITY FUNCTIONS ===

async def get_auth_token():
    """Get authentication token from Homebridge API."""
    global _auth_token, _token_expires
    
    # Check if we have a valid cached token
    if _auth_token and _token_expires and datetime.now(timezone.utc) < _token_expires:
        return _auth_token
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{HOMEBRIDGE_BASE_URL}/api/auth/noauth")
            response.raise_for_status()
            
            token_data = response.json()
            _auth_token = token_data.get("access_token")
            expires_in = token_data.get("expires_in", 3600)
            
            # Calculate expiration time (subtract 5 minutes for buffer)
            _token_expires = datetime.now(timezone.utc).replace(tzinfo=None)
            _token_expires = _token_expires.timestamp() + expires_in - 300
            _token_expires = datetime.fromtimestamp(_token_expires, tz=timezone.utc)
            
            logger.info("Successfully obtained auth token")
            return _auth_token
            
    except Exception as e:
        logger.error(f"Failed to get auth token: {e}")
        return None

async def make_api_request(method, endpoint, data=None):
    """Make authenticated API request to Homebridge."""
    token = await get_auth_token()
    if not token:
        return None, "Failed to authenticate with Homebridge"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if method.upper() == "GET":
                response = await client.get(f"{HOMEBRIDGE_BASE_URL}{endpoint}", headers=headers)
            elif method.upper() == "PUT":
                response = await client.put(f"{HOMEBRIDGE_BASE_URL}{endpoint}", headers=headers, json=data)
            else:
                return None, f"Unsupported HTTP method: {method}"
            
            response.raise_for_status()
            return response.json(), None
            
    except httpx.HTTPStatusError as e:
        return None, f"HTTP {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return None, str(e)

def format_accessory_info(accessory):
    """Format accessory information for display."""
    name = accessory.get("serviceName", "Unknown")
    service_type = accessory.get("serviceType", "Unknown")
    unique_id = accessory.get("uniqueId", "")
    room = accessory.get("customName", "")
    
    # Extract current values
    values = {}
    for char in accessory.get("serviceCharacteristics", []):
        char_type = char.get("type", "")
        value = char.get("value")
        if "On" in char_type:
            values["Power"] = "On" if value else "Off"
        elif "Brightness" in char_type:
            values["Brightness"] = f"{value}%"
        elif "Hue" in char_type:
            values["Hue"] = f"{value}°"
        elif "Saturation" in char_type:
            values["Saturation"] = f"{value}%"
    
    status = " | ".join([f"{k}: {v}" for k, v in values.items()])
    
    return f"🏠 {name} ({service_type})\n   ID: {unique_id}\n   Room: {room}\n   Status: {status}"

# HomeKit characteristic UUID mappings
HOMEKIT_CHARACTERISTIC_UUIDS = {
    "On": "00000025-0000-1000-8000-0026BB765291",
    "Brightness": "00000008-0000-1000-8000-0026BB765291", 
    "Hue": "00000013-0000-1000-8000-0026BB765291",
    "Saturation": "0000002F-0000-1000-8000-0026BB765291",
    "OutletInUse": "00000026-0000-1000-8000-0026BB765291"
}

def find_characteristic_by_action(characteristics, action):
    """Find the appropriate characteristic based on action type."""
    action_lower = action.lower()
    
    for char in characteristics:
        char_type = char.get("type", "")
        can_write = char.get("canWrite", False)
        
        if not can_write:
            continue
            
        # Map actions to characteristic type patterns
        if action_lower in ["power", "on", "off"] and "On" in char_type:
            return char  # Return the characteristic as-is with original type
        elif action_lower == "brightness" and "Brightness" in char_type:
            return char
        elif action_lower == "hue" and "Hue" in char_type:
            return char
        elif action_lower == "saturation" and "Saturation" in char_type:
            return char
    
    return None

# === MCP TOOLS ===

@mcp.tool()
async def list_accessories() -> str:
    """List all HomeKit accessories available in Homebridge."""
    logger.info("Fetching accessories list")
    
    data, error = await make_api_request("GET", "/api/accessories")
    if error:
        return f"❌ Error fetching accessories: {error}"
    
    if not data:
        return "📱 No accessories found"
    
    # Group accessories by room/type
    accessories_info = []
    for accessory in data:
        accessories_info.append(format_accessory_info(accessory))
    
    if not accessories_info:
        return "📱 No accessories found"
    
    return f"📱 Found {len(accessories_info)} accessories:\n\n" + "\n\n".join(accessories_info)

@mcp.tool()
async def get_accessories_layout() -> str:
    """Get the layout configuration of accessories organized by rooms."""
    logger.info("Fetching accessories layout")
    
    data, error = await make_api_request("GET", "/api/accessories/layout")
    if error:
        return f"❌ Error fetching layout: {error}"
    
    if not data:
        return "🏠 No layout found"
    
    layout_info = []
    for room in data:
        room_name = room.get("name", "Unknown Room")
        services = room.get("services", [])
        
        if services:
            service_list = []
            for service in services:
                service_name = service.get("serviceName", "Unknown")
                service_type = service.get("serviceType", "")
                service_list.append(f"   • {service_name} ({service_type})")
            
            room_info = f"🏠 {room_name} ({len(services)} devices):\n" + "\n".join(service_list)
            layout_info.append(room_info)
    
    if not layout_info:
        return "🏠 No rooms configured"
    
    return f"🏠 Home Layout:\n\n" + "\n\n".join(layout_info)

@mcp.tool()
async def get_accessory_details(unique_id: str = "") -> str:
    """Get detailed information about a specific accessory by its unique ID."""
    if not unique_id.strip():
        return "❌ Error: unique_id parameter is required"
    
    logger.info(f"Fetching details for accessory: {unique_id}")
    
    data, error = await make_api_request("GET", f"/api/accessories/{unique_id}")
    if error:
        return f"❌ Error fetching accessory details: {error}"
    
    if not data:
        return f"❌ Accessory not found: {unique_id}"
    
    # Format detailed information
    name = data.get("serviceName", "Unknown")
    service_type = data.get("serviceType", "Unknown")
    room = data.get("customName", "No room assigned")
    
    details = [f"🔍 Accessory Details: {name}"]
    details.append(f"   Type: {service_type}")
    details.append(f"   ID: {unique_id}")
    details.append(f"   Room: {room}")
    details.append("")
    details.append("📊 Characteristics:")
    
    for char in data.get("serviceCharacteristics", []):
        char_type = char.get("type", "Unknown")
        value = char.get("value")
        can_read = char.get("canRead", False)
        can_write = char.get("canWrite", False)
        
        permissions = []
        if can_read:
            permissions.append("Read")
        if can_write:
            permissions.append("Write")
        
        perm_str = " | ".join(permissions) if permissions else "No permissions"
        
        if "On" in char_type:
            status = "🟢 On" if value else "🔴 Off"
            details.append(f"   • Power: {status} ({perm_str})")
        elif "Brightness" in char_type:
            details.append(f"   • Brightness: {value}% ({perm_str})")
        elif "Hue" in char_type:
            details.append(f"   • Hue: {value}° ({perm_str})")
        elif "Saturation" in char_type:
            details.append(f"   • Saturation: {value}% ({perm_str})")
        else:
            # Show other characteristics with simplified names
            simple_name = char_type.split(".")[-1] if "." in char_type else char_type
            details.append(f"   • {simple_name}: {value} ({perm_str})")
    
    return "\n".join(details)

@mcp.tool()
async def control_accessory(unique_id: str = "", action: str = "", value: str = "") -> str:
    """Control an accessory by setting its characteristics (turn on/off, set brightness, etc.)."""
    if not unique_id.strip():
        return "❌ Error: unique_id parameter is required"
    
    if not action.strip():
        return "❌ Error: action parameter is required (e.g., 'power', 'brightness', 'hue', 'saturation')"
    
    logger.info(f"Controlling accessory {unique_id}: {action} = {value}")
    
    # First, get current accessory state
    current_data, error = await make_api_request("GET", f"/api/accessories/{unique_id}")
    if error:
        return f"❌ Error fetching current state: {error}"
    
    if not current_data:
        return f"❌ Accessory not found: {unique_id}"
    
    # Find the appropriate characteristic for this action
    characteristics = current_data.get("serviceCharacteristics", [])
    target_char = find_characteristic_by_action(characteristics, action)
    
    if not target_char:
        available_actions = []
        for char in characteristics:
            if char.get("canWrite", False):
                char_type = char.get("type", "")
                if "On" in char_type:
                    available_actions.append("power")
                elif "Brightness" in char_type:
                    available_actions.append("brightness")
                elif "Hue" in char_type:
                    available_actions.append("hue")
                elif "Saturation" in char_type:
                    available_actions.append("saturation")
        
        available_str = ", ".join(set(available_actions)) if available_actions else "none"
        return f"❌ Error: action '{action}' not supported. Available actions: {available_str}"
    
    # Prepare the target value based on action type
    action_lower = action.lower()
    
    if action_lower in ["power", "on", "off"]:
        if value.strip():
            target_value = value.lower() in ["on", "true", "1", "yes"]
        elif action_lower == "off":
            target_value = False
        else:
            target_value = True
    
    elif action_lower == "brightness":
        if not value.strip():
            return "❌ Error: brightness value is required (0-100)"
        
        try:
            target_value = int(value)
            if not 0 <= target_value <= 100:
                return "❌ Error: brightness must be between 0-100"
        except ValueError:
            return f"❌ Error: invalid brightness value: {value}"
    
    elif action_lower == "hue":
        if not value.strip():
            return "❌ Error: hue value is required (0-360)"
        
        try:
            target_value = int(value)
            if not 0 <= target_value <= 360:
                return "❌ Error: hue must be between 0-360"
        except ValueError:
            return f"❌ Error: invalid hue value: {value}"
    
    elif action_lower == "saturation":
        if not value.strip():
            return "❌ Error: saturation value is required (0-100)"
        
        try:
            target_value = int(value)
            if not 0 <= target_value <= 100:
                return "❌ Error: saturation must be between 0-100"
        except ValueError:
            return f"❌ Error: invalid saturation value: {value}"
    
    # Use the correct format from Swagger documentation
    payload = {
        "characteristicType": target_char["type"],  # Use the exact type from the characteristic (e.g., "On")
        "value": target_value
    }
    
    logger.info(f"Sending payload: {json.dumps(payload, indent=2)}")
    
    result, error = await make_api_request("PUT", f"/api/accessories/{unique_id}", payload)
    
    if error:
        return f"❌ Error controlling accessory: {error}"
    
    # Format success message
    accessory_name = current_data.get("serviceName", unique_id)
    action_description = f"{action} = {value}" if value.strip() else action
    
    return f"✅ Successfully controlled {accessory_name}: {action_description}"

@mcp.tool()
async def reset_cached_accessories() -> str:
    """Reset the cached accessories in Homebridge to refresh all device information."""
    logger.info("Resetting cached accessories")
    
    result, error = await make_api_request("PUT", "/api/server/reset-cached-accessories")
    
    if error:
        return f"❌ Error resetting cached accessories: {error}"
    
    return "✅ Successfully reset cached accessories. Homebridge will rediscover all accessories with updated names and configurations. Wait a few moments and then list accessories again to see the changes."
    """Quickly toggle an accessory's power state (on/off)."""
    if not unique_id.strip():
        return "❌ Error: unique_id parameter is required"
    
    logger.info(f"Quick toggling accessory: {unique_id}")
    
    # Get current state
    current_data, error = await make_api_request("GET", f"/api/accessories/{unique_id}")
    if error:
        return f"❌ Error fetching current state: {error}"
    
    if not current_data:
        return f"❌ Accessory not found: {unique_id}"
    
    # Find current power state
    current_power = None
    power_char = None
    
    for char in current_data.get("serviceCharacteristics", []):
        if "On" in char.get("type", "") and char.get("canWrite", False):
            current_power = char.get("value")
            power_char = char
            break
    
    if power_char is None:
        return "❌ Error: This accessory doesn't support power control"
    
    # Toggle the power state
    new_power = not bool(current_power)
    
    # Use the correct format from Swagger documentation
    payload = {
        "characteristicType": power_char["type"],  # Use the actual type from the characteristic (e.g., "On")
        "value": new_power
    }
    
    logger.info(f"Sending toggle payload: {json.dumps(payload, indent=2)}")
    
    result, error = await make_api_request("PUT", f"/api/accessories/{unique_id}", payload)
    
    if error:
        return f"❌ Error toggling accessory: {error}"
    
    accessory_name = current_data.get("serviceName", unique_id)
    new_state = "🟢 On" if new_power else "🔴 Off"
    old_state = "🟢 On" if current_power else "🔴 Off"
    
    return f"✅ Toggled {accessory_name}: {old_state} → {new_state}"

@mcp.tool()
async def create_room_groups() -> str:
    """Create logical room groups based on accessory names and allow user to organize accessories."""
    logger.info("Creating room-based organization")
    
    # Get all accessories
    data, error = await make_api_request("GET", "/api/accessories")
    if error:
        return f"❌ Error fetching accessories: {error}"
    
    if not data:
        return "📱 No accessories found"
    
    # Suggest room groupings based on accessory names
    room_suggestions = {}
    unassigned = []
    
    for accessory in data:
        name = accessory.get("serviceName", "Unknown").lower()
        unique_id = accessory.get("uniqueId", "")
        accessory_info = {
            "name": accessory.get("serviceName", "Unknown"),
            "id": unique_id,
            "type": accessory.get("serviceType", "Unknown")
        }
        
        # Smart room detection based on names
        if any(keyword in name for keyword in ["sala", "living", "salon"]):
            room_suggestions.setdefault("Sala", []).append(accessory_info)
        elif any(keyword in name for keyword in ["comedor", "dining"]):
            room_suggestions.setdefault("Comedor", []).append(accessory_info)
        elif any(keyword in name for keyword in ["entrada", "entry", "hall"]):
            room_suggestions.setdefault("Entrada", []).append(accessory_info)
        elif any(keyword in name for keyword in ["jardin", "garden", "patio"]):
            room_suggestions.setdefault("Jardín", []).append(accessory_info)
        elif any(keyword in name for keyword in ["garage"]):
            room_suggestions.setdefault("Garage", []).append(accessory_info)
        elif any(keyword in name for keyword in ["navidad", "christmas", "arbol"]):
            room_suggestions.setdefault("Decoración", []).append(accessory_info)
        elif any(keyword in name for keyword in ["luz", "light"]):
            # Group lights by position
            if "derecha" in name or "right" in name:
                room_suggestions.setdefault("Luces - Derecha", []).append(accessory_info)
            elif "izquierda" in name or "left" in name:
                room_suggestions.setdefault("Luces - Izquierda", []).append(accessory_info)
            else:
                room_suggestions.setdefault("Luces - Otros", []).append(accessory_info)
        elif "switch" in name:
            room_suggestions.setdefault("Switches", []).append(accessory_info)
        else:
            unassigned.append(accessory_info)
    
    # Format the output
    result = ["🏠 Organización sugerida por habitaciones:\n"]
    
    for room, accessories in room_suggestions.items():
        result.append(f"📍 **{room}** ({len(accessories)} dispositivos):")
        for acc in accessories:
            result.append(f"   • {acc['name']} ({acc['type']})")
            result.append(f"     ID: {acc['id']}")
        result.append("")
    
    if unassigned:
        result.append("❓ **Sin asignar** (requiere revisión manual):")
        for acc in unassigned:
            result.append(f"   • {acc['name']} ({acc['type']})")
            result.append(f"     ID: {acc['id']}")
        result.append("")
    
    result.append("💡 **Próximos pasos:**")
    result.append("1. Revisa la organización sugerida")
    result.append("2. Puedes usar control_room_devices() para controlar todas las luces de una habitación")
    result.append("3. La asignación formal de habitaciones se debe hacer desde la app Apple Home")
    
    return "\n".join(result)

@mcp.tool()
async def control_room_devices(room_pattern: str = "", action: str = "power", value: str = "toggle") -> str:
    """Control multiple devices in a room based on name patterns."""
    if not room_pattern.strip():
        return "❌ Error: room_pattern parameter is required (e.g., 'sala', 'comedor', 'luz')"
    
    logger.info(f"Controlling room devices matching: {room_pattern}")
    
    # Get all accessories
    data, error = await make_api_request("GET", "/api/accessories")
    if error:
        return f"❌ Error fetching accessories: {error}"
    
    if not data:
        return "📱 No accessories found"
    
    # Find matching accessories
    matching_accessories = []
    pattern = room_pattern.lower()
    
    for accessory in data:
        name = accessory.get("serviceName", "").lower()
        if pattern in name:
            # Check if it has controllable characteristics
            has_power = False
            for char in accessory.get("serviceCharacteristics", []):
                if "On" in char.get("type", "") and char.get("canWrite", False):
                    has_power = True
                    break
            
            if has_power:
                matching_accessories.append(accessory)
    
    if not matching_accessories:
        return f"❌ No se encontraron dispositivos controlables que coincidan con '{room_pattern}'"
    
    # Control each matching accessory
    results = []
    results.append(f"🎯 Controlando {len(matching_accessories)} dispositivos que coinciden con '{room_pattern}':\n")
    
    for accessory in matching_accessories:
        unique_id = accessory.get("uniqueId", "")
        name = accessory.get("serviceName", "Unknown")
        
        try:
            if value.lower() == "toggle":
                # Use quick_toggle for each device
                current_data, error = await make_api_request("GET", f"/api/accessories/{unique_id}")
                if error:
                    results.append(f"❌ {name}: Error obteniendo estado - {error}")
                    continue
                
                # Find current power state
                current_power = None
                power_char = None
                
                for char in current_data.get("serviceCharacteristics", []):
                    if "On" in char.get("type", "") and char.get("canWrite", False):
                        current_power = char.get("value")
                        power_char = char
                        break
                
                if power_char:
                    new_power = not bool(current_power)
                    payload = {
                        "characteristicType": power_char["type"],
                        "value": new_power
                    }
                    
                    result, error = await make_api_request("PUT", f"/api/accessories/{unique_id}", payload)
                    if error:
                        results.append(f"❌ {name}: Error - {error}")
                    else:
                        old_state = "🟢 On" if current_power else "🔴 Off"
                        new_state = "🟢 On" if new_power else "🔴 Off"
                        results.append(f"✅ {name}: {old_state} → {new_state}")
                else:
                    results.append(f"❌ {name}: No se puede controlar")
            else:
                # Use specific value
                target_value = value.lower() in ["on", "true", "1", "yes"]
                
                # Find power characteristic
                power_char = None
                for char in accessory.get("serviceCharacteristics", []):
                    if "On" in char.get("type", "") and char.get("canWrite", False):
                        power_char = char
                        break
                
                if power_char:
                    payload = {
                        "characteristicType": power_char["type"],
                        "value": target_value
                    }
                    
                    result, error = await make_api_request("PUT", f"/api/accessories/{unique_id}", payload)
                    if error:
                        results.append(f"❌ {name}: Error - {error}")
                    else:
                        state = "🟢 On" if target_value else "🔴 Off"
                        results.append(f"✅ {name}: {state}")
                else:
                    results.append(f"❌ {name}: No se puede controlar")
        
        except Exception as e:
            results.append(f"❌ {name}: Error inesperado - {str(e)}")
    
    return "\n".join(results)
    """Quickly toggle an accessory's power state (on/off)."""
    if not unique_id.strip():
        return "❌ Error: unique_id parameter is required"
    
    logger.info(f"Quick toggling accessory: {unique_id}")
    
    # Get current state
    current_data, error = await make_api_request("GET", f"/api/accessories/{unique_id}")
    if error:
        return f"❌ Error fetching current state: {error}"
    
    if not current_data:
        return f"❌ Accessory not found: {unique_id}"
    
    # Find current power state
    current_power = None
    power_char = None
    
    for char in current_data.get("serviceCharacteristics", []):
        if "On" in char.get("type", "") and char.get("canWrite", False):
            current_power = char.get("value")
            power_char = char
            break
    
    if power_char is None:
        return "❌ Error: This accessory doesn't support power control"
    
    # Toggle the power state
    new_power = not bool(current_power)
    
    payload = {
        "characteristics": [{
            "characteristicType": HOMEKIT_CHARACTERISTIC_UUIDS["On"],  # Use the correct UUID
            "value": new_power
        }]
    }
    
    logger.info(f"Sending toggle payload: {json.dumps(payload, indent=2)}")
    
    result, error = await make_api_request("PUT", f"/api/accessories/{unique_id}", payload)
    
    if error:
        return f"❌ Error toggling accessory: {error}"
    
    accessory_name = current_data.get("serviceName", unique_id)
    new_state = "🟢 On" if new_power else "🔴 Off"
    old_state = "🟢 On" if current_power else "🔴 Off"
    
    return f"✅ Toggled {accessory_name}: {old_state} → {new_state}"

# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info("Starting Homebridge MCP server...")
    logger.info(f"Connecting to Homebridge at: {HOMEBRIDGE_BASE_URL}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)