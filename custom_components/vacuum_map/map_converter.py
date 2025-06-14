"""Vacuum map converter module for Home Assistant."""
import os
import numpy as np
import json
import logging
from PIL import Image
import io
import base64

_LOGGER = logging.getLogger(__name__)

def create_map_image(map_path, output_path):
    """Create a map image for Home Assistant from binary map data.
    
    Args:
        map_path (str): Path to the directory containing map files
        output_path (str): Path where the output image should be saved
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Load map info
        map_info_path = os.path.join(map_path, 'map_record.json')
        with open(map_info_path, 'r') as f:
            map_info = json.load(f)
        
        # Load charger info
        charger_info_path = os.path.join(map_path, 'charger_pose.json')
        with open(charger_info_path, 'r') as f:
            charger_info = json.load(f)
        
        # Load area info
        area_info_path = os.path.join(map_path, 'area_info.json')
        with open(area_info_path, 'r') as f:
            area_info = json.load(f)
        
        # Extract map dimensions
        width = map_info['width']
        height = map_info['height']
        resolution = map_info['resolution']
        x_min = map_info['x_min']
        y_min = map_info['y_min']
        
        _LOGGER.debug(f"Map dimensions: {width}x{height} pixels")
        _LOGGER.debug(f"Resolution: {resolution} meters per pixel")
        _LOGGER.debug(f"Origin: ({x_min}, {y_min})")
        
        # Read the map data
        map_data_path = os.path.join(map_path, 'map_record.map')
        with open(map_data_path, 'rb') as f:
            map_data = f.read()
        
        # Make sure we have enough data
        if len(map_data) < width * height:
            _LOGGER.error(f"Error: Map data too small ({len(map_data)} bytes) for {width}x{height} map")
            return False
        
        # Convert to numpy array
        map_array = np.frombuffer(map_data[:width * height], dtype=np.uint8).reshape(height, width)
        
        # Create a colored map image
        # Values seem to be:
        # 0x7F (127) = Unknown/unexplored
        # 0x00 (0) = Free space
        # Other values = Obstacles
        
        # Create RGBA image
        img = np.zeros((height, width, 4), dtype=np.uint8)
        
        # Set alpha channel to fully opaque
        img[:, :, 3] = 255
        
        # Set colors based on map values
        # Unknown (value 127 or 0x7F) - light gray
        unknown_mask = (map_array == 127)
        img[unknown_mask, 0:3] = [200, 200, 200]  # Light gray
        
        # Free space (value 0) - white
        free_mask = (map_array == 0)
        img[free_mask, 0:3] = [255, 255, 255]  # White
        
        # Obstacles (other values) - black
        obstacle_mask = ~(unknown_mask | free_mask)
        img[obstacle_mask, 0:3] = [0, 0, 0]  # Black
        
        # Add charger position
        charger_x, charger_y = charger_info['charger_pose']
        charger_phi = charger_info['charger_phi']
        
        # Convert world coordinates to pixel coordinates
        charger_pixel_x = int((charger_x - x_min) / resolution)
        charger_pixel_y = int((charger_y - y_min) / resolution)
        
        # Make sure coordinates are within image bounds
        if 0 <= charger_pixel_x < width and 0 <= charger_pixel_y < height:
            # Draw a red dot for the charger (5x5 pixel square)
            radius = 3
            for dx in range(-radius, radius+1):
                for dy in range(-radius, radius+1):
                    x, y = charger_pixel_x + dx, charger_pixel_y + dy
                    if 0 <= x < width and 0 <= y < height:
                        img[y, x, 0:3] = [255, 0, 0]  # Red
        
        # Add rooms and forbidden areas if available
        if area_info:
            # Add forbidden areas first (in semi-transparent red)
            if 'forbidAreaValue' in area_info:
                for area in area_info['forbidAreaValue']:
                    vertices = area['vertexs']
                    # Convert to pixel coordinates
                    pixel_vertices = []
                    for x, y in vertices:
                        # Note: looks like coordinates are in cm
                        px = int((x/100.0 - x_min) / resolution)
                        py = int((y/100.0 - y_min) / resolution)
                        pixel_vertices.append((px, py))
                    
                    # Draw the polygon outline
                    if len(pixel_vertices) >= 3:
                        for i in range(len(pixel_vertices)):
                            x1, y1 = pixel_vertices[i]
                            x2, y2 = pixel_vertices[(i+1) % len(pixel_vertices)]
                            
                            # Draw thick line (3px) between vertices
                            for t in np.linspace(0, 1, max(abs(x2-x1), abs(y2-y1))*3):
                                x = int(x1 + t * (x2 - x1))
                                y = int(y1 + t * (y2 - y1))
                                if 0 <= x < width and 0 <= y < height:
                                    # Draw a 3x3 square
                                    for dx in range(-1, 2):
                                        for dy in range(-1, 2):
                                            nx, ny = x + dx, y + dy
                                            if 0 <= nx < width and 0 <= ny < height:
                                                img[ny, nx, 0:3] = [255, 0, 0]  # Red
            
            # Add room/area borders if available
            if 'areaValue' in area_info:
                for area in area_info['areaValue']:
                    vertices = area['vertexs']
                    # Convert to pixel coordinates
                    pixel_vertices = []
                    for x, y in vertices:
                        # Note: looks like coordinates are in cm
                        px = int((x/100.0 - x_min) / resolution)
                        py = int((y/100.0 - y_min) / resolution)
                        pixel_vertices.append((px, py))
                    
                    # Draw the polygon outline
                    if len(pixel_vertices) >= 3:
                        for i in range(len(pixel_vertices)):
                            x1, y1 = pixel_vertices[i]
                            x2, y2 = pixel_vertices[(i+1) % len(pixel_vertices)]
                            
                            # Draw line between vertices
                            for t in np.linspace(0, 1, max(abs(x2-x1), abs(y2-y1))*3):
                                x = int(x1 + t * (x2 - x1))
                                y = int(y1 + t * (y2 - y1))
                                if 0 <= x < width and 0 <= y < height:
                                    # Draw a 3x3 square
                                    for dx in range(-1, 2):
                                        for dy in range(-1, 2):
                                            nx, ny = x + dx, y + dy
                                            if 0 <= nx < width and 0 <= ny < height:
                                                img[ny, nx, 0:3] = [0, 0, 255]  # Blue
        
        # Save the image
        pil_img = Image.fromarray(img)
        
        # Create a resized version (2x) for better visibility
        img_resized = pil_img.resize((width*2, height*2), Image.LANCZOS)
        
        # Create the output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        img_resized.save(output_path)
        _LOGGER.info(f"Map saved to {output_path}")
        
        # Create a base64 encoded version for Home Assistant
        base64_path = output_path.replace('.png', '.base64.txt')
        buffered = io.BytesIO()
        img_resized.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        # Write base64 to file
        with open(base64_path, 'w') as f:
            f.write(img_base64)
        _LOGGER.debug(f"Base64 encoded map saved to {base64_path}")
        
        return True
    except Exception as e:
        _LOGGER.error(f"Error creating map: {e}")
        return False