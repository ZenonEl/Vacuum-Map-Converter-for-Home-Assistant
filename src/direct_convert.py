import numpy as np
import matplotlib.pyplot as plt
import json
import os
from PIL import Image

def read_binary_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return data

def try_all_offsets(data, width, height, output_dir):
    """Try all possible offsets and save the resulting images"""
    os.makedirs(output_dir, exist_ok=True)
    
    # Try different offsets up to a reasonable limit
    max_offset = min(1024, len(data) - width * height)
    
    for offset in range(0, max_offset):
        if offset + width * height > len(data):
            break
            
        try:
            # Extract data at this offset
            map_data = data[offset:offset + width * height]
            
            # Skip if not enough data
            if len(map_data) < width * height:
                continue
                
            # Try to reshape into an image
            grid = np.frombuffer(map_data, dtype=np.uint8).reshape(height, width)
            
            # Skip if all values are the same
            if np.all(grid == grid[0, 0]):
                continue
                
            # Save the image
            img = Image.fromarray(grid)
            output_path = os.path.join(output_dir, f"offset_{offset}.png")
            img.save(output_path)
            
            # Also save a colored version for better visualization
            plt.figure(figsize=(10, 10))
            plt.imshow(grid, cmap='viridis')
            plt.title(f"Offset: {offset}")
            plt.axis('off')
            plt.savefig(os.path.join(output_dir, f"offset_{offset}_color.png"), 
                       bbox_inches='tight', pad_inches=0.1)
            plt.close()
            
            print(f"Saved image with offset {offset}")
        except Exception as e:
            print(f"Error at offset {offset}: {str(e)}")

def process_map_file(file_path, width, height):
    """Process a map file and try to extract usable map data"""
    print(f"\nProcessing {file_path}...")
    
    # Create output directory based on filename
    base_name = os.path.basename(file_path)
    output_dir = f"output_{base_name}"
    
    # Read the binary data
    data = read_binary_file(file_path)
    print(f"File size: {len(data)} bytes")
    
    # Try all offsets
    try_all_offsets(data, width, height, output_dir)
    
    return output_dir

def main():
    # Load map dimensions from map_record.json
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    width = map_info['width']
    height = map_info['height']
    resolution = map_info['resolution']
    
    print(f"Map dimensions: {width}x{height} pixels")
    print(f"Resolution: {resolution} meters per pixel")
    
    # Process all available map files
    map_files = [
        'map.gridmap',
        'map.segmentmap',
        'map_record.map',
        'path_map'
    ]
    
    output_dirs = []
    for map_file in map_files:
        if os.path.exists(map_file):
            output_dir = process_map_file(map_file, width, height)
            output_dirs.append(output_dir)
    
    print("\nProcessing complete!")
    print("Look through the generated images in these directories:")
    for directory in output_dirs:
        print(f"- {directory}")
    print("\nFind the image that most resembles your apartment layout.")

if __name__ == "__main__":
    main()