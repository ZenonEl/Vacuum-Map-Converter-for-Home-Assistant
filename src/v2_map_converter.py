import numpy as np
import matplotlib.pyplot as plt
import json
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
import io
import base64
import sys
import colorsys
from datetime import datetime

def read_binary_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return data

def debug_output_array(array, filename):
    """Save an array as an image for debugging"""
    img = Image.fromarray(array.astype(np.uint8))
    img.save(filename)
    print(f"Debug image saved to {filename}")

def generate_colors(num_colors):
    """Generate visually distinct colors"""
    # Predefined colors matching the Smart Life app
    predefined = [
        (255, 195, 0),    # Yellow (room1)
        (200, 80, 80),    # Red (room2)
        (30, 144, 255),   # Blue (room3)
        (0, 230, 170),    # Turquoise (room6)
        (100, 210, 255),  # Light blue (room7)
    ]

    # Use predefined colors first, then generate more if needed
    if num_colors <= len(predefined):
        return predefined[:num_colors]

    # Generate additional colors using HSV for better distinction
    colors = list(predefined)
    for i in range(len(predefined), num_colors):
        h = (i - len(predefined)) / float(num_colors - len(predefined))
        s = 0.8
        v = 0.9
        r, g, b = [int(x * 255) for x in colorsys.hsv_to_rgb(h, s, v)]
        colors.append((r, g, b))

    return colors

def try_load_font(size=16):
    """Try to load a font with fallbacks"""
    font_paths = [
        "arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/Vera.ttf",
        "/usr/share/fonts/noto/NotoSans-Regular.ttf",
        "/System/Library/Fonts/Helvetica.ttc"  # macOS
    ]

    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except:
            continue

    # Fallback to default font
    return ImageFont.load_default()

def parse_segment_map(segment_data, width, height):
    """Parse the segment map file to extract room segmentation"""
    try:
        # Extract the segment map data
        # The structure might be different depending on the robot model
        # This is a simplified approach
        segment_map = np.zeros((height, width), dtype=np.uint8)
        
        # Try different header sizes and formats as different robot models use different formats
        possible_formats = [
            # (header_size, dtype, reshape_order)
            (16, np.uint8, 'C'),  # Most common format
            (20, np.uint8, 'C'),  # Alternative header size
            (32, np.uint8, 'C'),  # Another alternative
            (16, np.uint8, 'F'),  # Column-major order
            (20, np.uint8, 'F'),  # Column-major with different header
            (0, np.uint8, 'C'),   # No header
            (0, np.uint8, 'F'),   # No header, column-major
        ]
        
        for header_size, dtype, order in possible_formats:
            if len(segment_data) >= header_size + (width * height):
                try:
                    # Try to parse the segment data after the header
                    segment_array = np.frombuffer(segment_data[header_size:header_size + (width * height)], 
                                                dtype=dtype)
                    
                    # Try different reshape orders
                    try:
                        segment_array = segment_array.reshape(height, width, order=order)
                    except:
                        continue
                    
                    # Check if we have any non-zero values that might be room IDs
                    unique_values = np.unique(segment_array)
                    if len(unique_values) > 1:  # At least one room ID besides 0
                        # Filter out very small segments that might be noise
                        room_id_count = 0
                        for segment_id in unique_values:
                            if segment_id > 0:  # Skip background (0)
                                mask = (segment_array == segment_id)
                                pixel_count = np.sum(mask)
                                if pixel_count > 50:  # Minimum area to be considered a room
                                    segment_map[mask] = segment_id
                                    room_id_count += 1
                        
                        if room_id_count > 0:
                            print(f"Successfully parsed segment map with {room_id_count} rooms (header size: {header_size}, order: {order})")
                            
                            # Save the segment map for debugging
                            debug_output_array(segment_map * 30, f"segment_map_h{header_size}_o{order}_debug.png")
                            
                            return segment_map
                except Exception as inner_e:
                    continue  # Try next format
        
        # Try one more approach - look for markers that might indicate segmentation data
        # This is common in some binary formats where segments are marked with special values
        for offset in range(0, min(1000, len(segment_data) - width * height), 4):
            try:
                test_array = np.frombuffer(segment_data[offset:offset + (width * height)], dtype=np.uint8).reshape(height, width)
                unique_values = np.unique(test_array)
                
                # A good segmentation usually has several unique values (rooms) with reasonable distribution
                if 1 < len(unique_values) < 20:  # Reasonable number of rooms
                    # Check if the values are distributed in a way that looks like rooms
                    # (not just random noise or solid blocks)
                    value_counts = [(val, np.sum(test_array == val)) for val in unique_values if val > 0]
                    
                    # Sort by count (descending)
                    value_counts.sort(key=lambda x: x[1], reverse=True)
                    
                    # If we have reasonably sized regions, this might be our segmentation
                    if value_counts and all(count > 50 for _, count in value_counts):
                        print(f"Found potential segment map at offset {offset} with {len(value_counts)} rooms")
                        
                        for segment_id, count in value_counts:
                            mask = (test_array == segment_id)
                            segment_map[mask] = segment_id
                        
                        if os.environ.get('DEBUG_MODE') == '1':
                            debug_output_array(segment_map * 30, f"segment_map_offset{offset}_debug.png")
                        return segment_map
            except:
                continue
        
        print("Could not parse segment map with any common format")
        
        # Fallback to flood fill detection if segment map parsing failed
        return None
    except Exception as e:
        print(f"Error parsing segment map: {str(e)}")
        return None

def flood_fill(raw_map, x, y, target_color, replacement_color, visited):
    """Flood fill algorithm to detect connected areas"""
    height, width = raw_map.shape
    if (x < 0 or y < 0 or x >= width or y >= height or 
        visited[y, x] or raw_map[y, x] != target_color):
        return []
    
    pixels = [(x, y)]
    queue = [(x, y)]
    visited[y, x] = True
    
    while queue:
        cx, cy = queue.pop(0)
        for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if (0 <= nx < width and 0 <= ny < height and 
                not visited[ny, nx] and raw_map[ny, nx] == target_color):
                visited[ny, nx] = True
                queue.append((nx, ny))
                pixels.append((nx, ny))
    
    return pixels

def detect_rooms(raw_map, min_room_size=100):
    """Detect rooms using flood fill algorithm"""
    height, width = raw_map.shape
    visited = np.zeros((height, width), dtype=bool)
    room_segments = []
    
    # Find large open areas (potential rooms)
    for y in range(height):
        for x in range(width):
            if not visited[y, x] and raw_map[y, x] == 0:  # 0 = free space
                area = flood_fill(raw_map, x, y, 0, 1, visited)
                if len(area) > min_room_size:  # Minimum size threshold for a room
                    room_segments.append(area)
    
    # Sort room segments by size (largest first)
    room_segments.sort(key=lambda x: len(x), reverse=True)
    return room_segments

def create_polygon_from_points(points, simplify_factor=0.8):
    """Create a simplified polygon from a set of points"""
    # If we have too few points, just return the bounding box
    if len(points) < 20:
        x_coords = [x for x, y in points]
        y_coords = [y for x, y in points]
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]
    
    # Try to use scipy's ConvexHull if available
    try:
        # Only import if we know it's available (checked in create_perfect_map)
        if 'ConvexHull' in globals():
            points_array = np.array(points)
            hull = ConvexHull(points_array)
            hull_points = [points_array[i] for i in hull.vertices]
            
            # Simplify by keeping only a subset of the hull points
            if simplify_factor < 1.0 and len(hull_points) > 10:
                step = max(1, int(len(hull_points) * (1.0 - simplify_factor)))
                simplified = [hull_points[i] for i in range(0, len(hull_points), step)]
                return simplified
            return hull_points
    except Exception as e:
        print(f"Error using scipy ConvexHull: {str(e)}")
    
    # Fallback to manual convex hull calculation
    try:
        # Sort points by x, then by y
        sorted_points = sorted(points, key=lambda p: (p[0], p[1]))
        
        # Find the leftmost and rightmost points
        leftmost = sorted_points[0]
        rightmost = sorted_points[-1]
        
        # Divide points into upper and lower sets
        upper = [leftmost]
        lower = [leftmost]
        
        # Build the upper hull
        for p in sorted_points[1:]:
            while len(upper) >= 2 and cross_product(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)
        
        # Build the lower hull
        for p in reversed(sorted_points[:-1]):
            while len(lower) >= 2 and cross_product(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)
        
        # Combine to form the convex hull
        hull = upper[:-1] + lower[:-1]
        
        # Simplify by keeping only a subset of the points
        if simplify_factor < 1.0 and len(hull) > 10:
            step = max(1, int(len(hull) * (1.0 - simplify_factor)))
            simplified = [hull[i] for i in range(0, len(hull), step)]
            return simplified
        else:
            return hull
    except Exception as e:
        print(f"Error creating convex hull: {str(e)}")
    
    # Ultimate fallback - just use the bounding box
    x_coords = [x for x, y in points]
    y_coords = [y for x, y in points]
    min_x, max_x = min(x_coords), max(x_coords)
    min_y, max_y = min(y_coords), max(y_coords)
    
    return [(min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y)]

def cross_product(p1, p2, p3):
    """Calculate the cross product to determine if points make a left or right turn"""
    return (p2[0] - p1[0]) * (p3[1] - p1[1]) - (p2[1] - p1[1]) * (p3[0] - p1[0])

def create_perfect_map(map_data_file, map_info_file, charger_info_file, area_info_file, output_path):
    """Create a perfect map with predefined room areas and proper colors"""
    print("Creating perfect map with predefined rooms...")

    # Load all the config files
    with open(map_info_file, 'r') as f:
        map_info = json.load(f)

    with open(charger_info_file, 'r') as f:
        charger_info = json.load(f)

    with open(area_info_file, 'r') as f:
        area_info = json.load(f)

    # Extract map dimensions
    width = map_info['width']
    height = map_info['height']
    resolution = map_info['resolution']
    x_min = map_info['x_min']
    y_min = map_info['y_min']

    print(f"Map dimensions: {width}x{height}")
    print(f"Resolution: {resolution} meters/pixel")
    print(f"Origin: ({x_min}, {y_min})")

    # Read binary map data
    map_data = read_binary_file(map_data_file)

    # Check if we have enough data
    if len(map_data) < width * height:
        print(f"Error: Map data too small ({len(map_data)} bytes) for {width}x{height} map")
        return False

    # Convert to numpy array without any transformations
    raw_map = np.frombuffer(map_data[:width * height], dtype=np.uint8).reshape(height, width)

    # Save raw map for debugging
    debug_output_array(raw_map, "raw_map_debug.png")

    # Create a high-quality scaled map
    scale_factor = 4  # Scale up for better quality
    img_width = width * scale_factor
    img_height = height * scale_factor

    # Create a base map with walls and free space
    base_map = np.zeros((img_height, img_width, 3), dtype=np.uint8)

    # Apply color mapping with high-quality upscaling
    for y in range(height):
        for x in range(width):
            value = raw_map[y, x]
            
            # Determine color based on pixel value
            if value == 0:
                color = [255, 255, 255]  # White (free space)
            elif value == 127:
                color = [230, 230, 230]  # Light gray (unknown)
            else:
                color = [40, 40, 40]     # Dark gray (obstacle)
            
            # Fill the scaled area
            y_start = y * scale_factor
            y_end = (y + 1) * scale_factor
            x_start = x * scale_factor
            x_end = (x + 1) * scale_factor
            
            base_map[y_start:y_end, x_start:x_end] = color

    # Convert to PIL image for advanced processing
    pil_map = Image.fromarray(base_map)

    # Create separate layers for better control
    room_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    room_draw = ImageDraw.Draw(room_layer)

    # Define predefined room areas manually
    # These coordinates are carefully adjusted based on the image from app
    predefined_rooms = [
        {
            "id": 1,
            "name": "room1",
            "color": (255, 195, 0),  # Yellow
            "polygon": [
                (115, 150), (140, 150), (150, 170), (170, 180), (170, 210), 
                (115, 210), (115, 180), (130, 170), (115, 160)
            ]
        },
        {
            "id": 3,
            "name": "room3",
            "color": (30, 144, 255),  # Blue
            "polygon": [
                (35, 110), (75, 110), (100, 140), (100, 170), (60, 170),
                (35, 150)
            ]
        },
        {
            "id": 7,
            "name": "room7",
            "color": (100, 210, 255),  # Light blue
            "polygon": [
                (105, 110), (170, 110), (170, 150), (140, 150), (130, 140),
                (105, 140)
            ]
        },
        {
            "id": 6,
            "name": "room6",
            "color": (0, 230, 170),  # Turquoise
            "polygon": [
                (35, 50), (105, 50), (105, 110), (75, 110), (35, 90)
            ]
        },
        {
            "id": 2,
            "name": "room2",
            "color": (255, 100, 100),  # Light red
            "polygon": [
                (50, 170), (90, 190), (90, 205), (50, 205)
            ]
        },
        {
            "id": 5,
            "name": "room5",
            "color": (200, 80, 80),  # Red
            "polygon": [
                (150, 35), (170, 35), (170, 65), (150, 65)
            ]
        }
    ]

    # Use our predefined rooms
    detected_rooms = predefined_rooms

    # Draw all rooms
    print(f"Drawing {len(detected_rooms)} rooms")
    for room in detected_rooms:
        if "polygon" in room:
            # Scale polygon coordinates
            scaled_polygon = [(x * scale_factor, y * scale_factor) for x, y in room["polygon"]]
            
            # Draw filled polygon with semi-transparent color
            room_draw.polygon(scaled_polygon, fill=(*room["color"], 180))  # Semi-transparent
            
            # Draw polygon outline
            for i in range(len(scaled_polygon)):
                start = scaled_polygon[i]
                end = scaled_polygon[(i + 1) % len(scaled_polygon)]
                room_draw.line([start, end], fill=(*room["color"], 220), width=3)
            
            # Calculate center for label
            center_x = sum(x for x, y in scaled_polygon) / len(scaled_polygon)
            center_y = sum(y for x, y in scaled_polygon) / len(scaled_polygon)
            
            # Add room name
            font = try_load_font(size=24)
            
            # Get room name and ensure proper display orientation
            room_name = room["name"]
            
            # Calculate proper text size based on polygon size
            x_coords = [x for x, y in scaled_polygon]
            y_coords = [y for x, y in scaled_polygon]
            polygon_width = max(x_coords) - min(x_coords)
            polygon_height = max(y_coords) - min(y_coords)
            
            # Adjust font size based on polygon size
            font_size = min(22, max(14, int(min(polygon_width, polygon_height) / 6)))
            font = try_load_font(size=font_size)
            
            # Draw text with outline for visibility
            for dx, dy in [(0,2), (2,0), (0,-2), (-2,0)]:
                room_draw.text(
                    (center_x+dx, center_y+dy),
                    room_name,
                    font=font,
                    fill=(255, 255, 255, 230)
                )
        
            # Draw text
            room_draw.text(
                (center_x, center_y),
                room_name,
                font=font,
                fill=(0, 0, 0, 255)
            )
            
            # Print room info for debugging if needed
            # print(f"Room {room['id']} ({room['name']}): Drawn at {room['polygon']}")

    # Add forbidden areas - using the data from area_info
    forbidden_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    forbidden_draw = ImageDraw.Draw(forbidden_layer)

    if 'forbidAreaValue' in area_info:
        for area in area_info['forbidAreaValue']:
            vertices = area['vertexs']
            forbid_type = area.get('forbidType', 'all')

            # Convert to pixel coordinates (WITHOUT any transformation)
            pixel_vertices = []
            for x, y in vertices:
                # Convert from cm to pixel coordinates
                px = int(((x/100.0) - x_min) / resolution) * scale_factor
                py = int(((y/100.0) - y_min) / resolution) * scale_factor
                pixel_vertices.append((px, py))

            # Draw the area based on type
            if len(pixel_vertices) >= 3:
                if forbid_type == 'mop':
                    # Blue for no-mop areas
                    forbidden_draw.polygon(pixel_vertices, fill=(0, 0, 255, 80))

                    # Add diagonal stripes pattern
                    min_x = min(x for x, y in pixel_vertices)
                    max_x = max(x for x, y in pixel_vertices)
                    min_y = min(y for x, y in pixel_vertices)
                    max_y = max(y for x, y in pixel_vertices)

                    stripe_spacing = 20
                    for i in range(int(min_x), int(max_x + max_y - min_y), stripe_spacing):
                        forbidden_draw.line(
                            [(i, min_y), (i - (max_y - min_y), max_y)],
                            fill=(0, 0, 255, 180),
                            width=3
                        )

                    # Draw blue border
                    for i in range(len(pixel_vertices)):
                        start = pixel_vertices[i]
                        end = pixel_vertices[(i + 1) % len(pixel_vertices)]
                        forbidden_draw.line([start, end], fill=(0, 0, 255, 200), width=3)
                else:
                    # Red for no-go areas
                    forbidden_draw.polygon(pixel_vertices, fill=(255, 0, 0, 80))

                    # Add diagonal stripes pattern
                    min_x = min(x for x, y in pixel_vertices)
                    max_x = max(x for x, y in pixel_vertices)
                    min_y = min(y for x, y in pixel_vertices)
                    max_y = max(y for x, y in pixel_vertices)

                    stripe_spacing = 20
                    for i in range(int(min_x), int(max_x + max_y - min_y), stripe_spacing):
                        forbidden_draw.line(
                            [(i, min_y), (i - (max_y - min_y), max_y)],
                            fill=(255, 0, 0, 180),
                            width=3
                        )

                    # Add stripes in the other direction too
                    for i in range(int(min_x), int(max_x + max_y - min_y), stripe_spacing):
                        forbidden_draw.line(
                            [(i, max_y), (i - (max_y - min_y), min_y)],
                            fill=(255, 0, 0, 180),
                            width=3
                        )

                    # Draw red border
                    for i in range(len(pixel_vertices)):
                        start = pixel_vertices[i]
                        end = pixel_vertices[(i + 1) % len(pixel_vertices)]
                        forbidden_draw.line([start, end], fill=(255, 0, 0, 200), width=4)

    # Add charger position
    charger_layer = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
    charger_draw = ImageDraw.Draw(charger_layer)

    # Get charger position from charger_info
    charger_x, charger_y = charger_info['charger_pose']
    charger_pixel_x = int((charger_x - x_min) / resolution) * scale_factor
    charger_pixel_y = int((charger_y - y_min) / resolution) * scale_factor

    print(f"Using charger position from data: ({charger_pixel_x/scale_factor}, {charger_pixel_y/scale_factor})")

    # Draw the charger as a nice icon
    charger_radius = 15
    charger_draw.ellipse(
        [
            charger_pixel_x - charger_radius,
            charger_pixel_y - charger_radius,
            charger_pixel_x + charger_radius,
            charger_pixel_y + charger_radius
        ],
        fill=(255, 0, 0, 255)  # Red, fully opaque
    )

    # Draw a white lightning bolt symbol
    lightning_points = [
        (charger_pixel_x, charger_pixel_y - 10),      # Top
        (charger_pixel_x - 6, charger_pixel_y - 2),   # Middle left
        (charger_pixel_x, charger_pixel_y + 3),       # Middle
        (charger_pixel_x + 6, charger_pixel_y - 2),   # Middle right
        (charger_pixel_x, charger_pixel_y + 10)       # Bottom
    ]
    charger_draw.line(lightning_points, fill=(255, 255, 255, 255), width=3)
    
    # Draw a small outer ring around the charger
    outer_radius = charger_radius + 3
    charger_draw.ellipse(
        [
            charger_pixel_x - outer_radius,
            charger_pixel_y - outer_radius,
            charger_pixel_x + outer_radius,
            charger_pixel_y + outer_radius
        ],
        outline=(255, 255, 0, 200),  # Yellow outline
        width=2
    )

    # Combine all layers WITHOUT transformation
    combined_map = pil_map.convert('RGBA')
    combined_map = Image.alpha_composite(combined_map, room_layer)
    combined_map = Image.alpha_composite(combined_map, forbidden_layer)
    combined_map = Image.alpha_composite(combined_map, charger_layer)

    # The app view is upside-down and mirrored compared to the raw map
    # NOW apply transformations to match the app view
    # We need to get the orientation right for the room labels and charging station
    # The sequence of operations is important to match the app view

    # Apply transformations to match the app view
    # First rotate 180 degrees
    transformed_map = combined_map.rotate(180, expand=False)
    
    # Then flip horizontally (mirror)
    transformed_map = ImageOps.mirror(transformed_map)
    
    # Save both the original and transformed versions for comparison
    if os.environ.get('DEBUG_MODE') == '1':
        original_output_path = output_path.replace('.png', '_original.png')
        combined_map.save(original_output_path)
        print(f"Original map saved to {original_output_path}")

    # Apply some final enhancements
    # Slightly increase contrast
    enhancer = ImageEnhance.Contrast(transformed_map)
    transformed_map = enhancer.enhance(1.1)

    # Slightly increase saturation
    enhancer = ImageEnhance.Color(transformed_map)
    transformed_map = enhancer.enhance(1.2)

    # Add timestamp and attribution
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    draw = ImageDraw.Draw(transformed_map)

    small_font = try_load_font(size=12)
    draw.text(
        (10, img_height - 20),
        f"Generated: {timestamp} • Vacuum Map Converter for Home Assistant",
        font=small_font,
        fill=(100, 100, 100, 200)
    )

    # Save the final image
    transformed_map.save(output_path)
    print(f"Map saved to {output_path}")

    # Create a base64 encoded version for Home Assistant
    buffered = io.BytesIO()
    transformed_map.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

    # Write base64 to file
    base64_path = output_path.replace('.png', '.base64.txt')
    with open(base64_path, 'w') as f:
        f.write(img_base64)
    print(f"Base64 encoded map saved to {base64_path}")

    return True

def main():
    print("=== Perfect Map Converter ===")
    print("This script creates a high-quality map with predefined rooms")
    print("that match exactly what you see in the Smart Life app.")

    # Check if required files exist
    required_files = {
        'map_record.map': 'Binary map data',
        'map_record.json': 'Map configuration',
        'charger_pose.json': 'Charger position',
        'area_info.json': 'Room and area information'
    }

    missing_files = []
    for file_name, description in required_files.items():
        if not os.path.exists(file_name):
            missing_files.append(f"{file_name} ({description})")

    if missing_files:
        print(f"Error: Missing required files: {', '.join(missing_files)}")
        sys.exit(1)

    # Create the map
    output_path = 'vacuum_map_perfect.png'
    success = create_perfect_map(
        'map_record.map',
        'map_record.json',
        'charger_pose.json',
        'area_info.json',
        output_path
    )

    if success:
        print("\nMap creation successful!")
        print(f"Your map is ready at: {output_path}")
        print("\nTo use in Home Assistant:")
        print("1. Copy the generated PNG file to your Home Assistant /config/www/ directory")
        print("2. Add the following to your configuration.yaml:")
        print("""
camera:
  - platform: local_file
    name: Vacuum Map
    file_path: /config/www/vacuum_map_perfect.png
""")
    else:
        print("\nError creating map. Check the error messages above.")

if __name__ == "__main__":
    main()
