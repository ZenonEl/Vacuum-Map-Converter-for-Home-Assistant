import numpy as np
import matplotlib.pyplot as plt
import json
import struct
import os
from PIL import Image

def read_binary_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return data

def parse_gridmap(data):
    # Based on the hexdump, we need to parse the header
    # First 4 bytes seem to be a float (resolution)
    resolution = struct.unpack('f', data[0:4])[0]
    
    # Next values might be map bounds or dimensions
    # Extract width and height from map_record.json
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    width = map_info['width']
    height = map_info['height']
    
    # Skip the header (around 32-48 bytes) and read the map data
    # This is an approximation - the exact header size might vary
    header_size = 48  
    map_data = data[header_size:]
    
    # Convert binary data to numpy array - this assumes 1 byte per cell
    # Try to reshape according to width and height
    try:
        grid = np.frombuffer(map_data, dtype=np.uint8)
        grid = grid[:width*height].reshape(height, width)
    except:
        print("Failed to reshape data. Trying different approach...")
        # If the above fails, try to create a flat array and truncate
        grid = np.frombuffer(map_data, dtype=np.uint8)
        grid = grid[:width*height]
        if len(grid) < width*height:
            # Pad if needed
            grid = np.pad(grid, (0, width*height - len(grid)), 'constant')
        grid = grid.reshape(height, width)
    
    return grid, width, height, resolution

def parse_segmentmap(data):
    # Extract info from map_record.json
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    width = map_info['width']
    height = map_info['height']
    
    # Skip header (approximation)
    header_size = 48
    map_data = data[header_size:]
    
    # Try to reshape the data
    try:
        segments = np.frombuffer(map_data, dtype=np.uint8)
        segments = segments[:width*height].reshape(height, width)
    except:
        print("Failed to reshape segment data. Using alternative approach...")
        segments = np.frombuffer(map_data, dtype=np.uint8)
        segments = segments[:width*height]
        if len(segments) < width*height:
            segments = np.pad(segments, (0, width*height - len(segments)), 'constant')
        segments = segments.reshape(height, width)
    
    return segments

def create_map_image(grid_data, segment_data, width, height, output_path):
    # Create a color map image
    # 0 - Unknown (gray)
    # 1 - Free space (white)
    # 2 - Obstacle (black)
    # Segments will be colored with different colors
    
    # Create RGBA image
    img = np.zeros((height, width, 4), dtype=np.uint8)
    
    # Base map colors
    # Assuming 0 is unknown, 1 is free, 2 is obstacle
    # Fill with gray (unknown)
    img[:, :, 0:3] = 128  # Gray
    img[:, :, 3] = 255  # Fully opaque
    
    # Set free space to white
    free_mask = (grid_data == 1)
    img[free_mask, 0:3] = 255  # White
    
    # Set obstacles to black
    obstacle_mask = (grid_data == 2)
    img[obstacle_mask, 0:3] = 0  # Black
    
    # Color segments (if any valid segment data)
    if np.max(segment_data) > 0:
        # Get unique segment IDs
        segment_ids = np.unique(segment_data)
        segment_ids = segment_ids[segment_ids > 0]  # Skip 0 (non-segment)
        
        # Create colors for segments
        colors = plt.cm.rainbow(np.linspace(0, 1, len(segment_ids)))
        colors = (colors[:, 0:3] * 255).astype(np.uint8)
        
        for i, seg_id in enumerate(segment_ids):
            mask = (segment_data == seg_id) & free_mask
            img[mask, 0:3] = colors[i % len(colors)]
    
    # Add charger position and forbidden areas
    with open('charger_pose.json', 'r') as f:
        charger_data = json.load(f)
    
    # Convert charger position to pixels
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    resolution = map_info['resolution']
    x_min = map_info['x_min']
    y_min = map_info['y_min']
    
    charger_x, charger_y = charger_data['charger_pose']
    
    # Convert world coordinates to pixel coordinates
    charger_pixel_x = int((charger_x - x_min) / resolution)
    charger_pixel_y = int((charger_y - y_min) / resolution)
    
    # Ensure coordinates are within image bounds
    if 0 <= charger_pixel_x < width and 0 <= charger_pixel_y < height:
        # Draw a red dot for the charger (5x5 pixel square)
        radius = 2
        for dx in range(-radius, radius+1):
            for dy in range(-radius, radius+1):
                x, y = charger_pixel_x + dx, charger_pixel_y + dy
                if 0 <= x < width and 0 <= y < height:
                    img[y, x, 0:3] = [255, 0, 0]  # Red
    
    # Add forbidden areas with different colors
    try:
        with open('area_info.json', 'r') as f:
            area_info = json.load(f)
        
        if 'forbidAreaValue' in area_info:
            for area in area_info['forbidAreaValue']:
                vertices = area['vertexs']
                # Convert to pixel coordinates
                pixel_vertices = []
                for x, y in vertices:
                    px = int((x/100.0 - x_min) / resolution)
                    py = int((y/100.0 - y_min) / resolution)
                    pixel_vertices.append((px, py))
                
                # Fill the polygon (simple approach)
                if len(pixel_vertices) >= 3:
                    # Just highlight the boundaries for simplicity
                    for i in range(len(pixel_vertices)):
                        x1, y1 = pixel_vertices[i]
                        x2, y2 = pixel_vertices[(i+1) % len(pixel_vertices)]
                        
                        # Draw line between vertices
                        for t in np.linspace(0, 1, 100):
                            x = int(x1 + t * (x2 - x1))
                            y = int(y1 + t * (y2 - y1))
                            if 0 <= x < width and 0 <= y < height:
                                img[y, x, 0:3] = [255, 0, 255]  # Magenta
    except Exception as e:
        print(f"Error adding forbidden areas: {e}")
    
    # Save the image
    pil_img = Image.fromarray(img)
    pil_img.save(output_path)
    print(f"Map saved to {output_path}")
    
    return pil_img

def main():
    # Read the binary files
    gridmap_data = read_binary_file('map.gridmap')
    segmentmap_data = read_binary_file('map.segmentmap')
    
    # Parse the gridmap
    grid, width, height, resolution = parse_gridmap(gridmap_data)
    
    # Parse the segmentmap
    segments = parse_segmentmap(segmentmap_data)
    
    # Create and save the map image
    output_path = 'vacuum_map.png'
    create_map_image(grid, segments, width, height, output_path)
    
    print(f"Map dimensions: {width}x{height}")
    print(f"Resolution: {resolution}")
    
    # Create a simplified version for Home Assistant
    try:
        img = Image.open(output_path)
        # Resize to a reasonable size for HA
        img_resized = img.resize((width*2, height*2), Image.LANCZOS)
        img_resized.save('vacuum_map_ha.png')
        print("Created resized map for Home Assistant")
    except Exception as e:
        print(f"Error creating resized map: {e}")

if __name__ == "__main__":
    main()