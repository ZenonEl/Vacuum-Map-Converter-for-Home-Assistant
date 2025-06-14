import numpy as np
import matplotlib.pyplot as plt
import json
import os
from PIL import Image
import struct

def read_binary_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return data

def try_grid_format(data, width, height, dtype, output_name):
    """Try different interpretations of the data as a grid"""
    print(f"Trying to interpret as {dtype} grid...")
    
    if dtype == 'uint8':
        bytes_per_pixel = 1
    elif dtype == 'int16' or dtype == 'uint16':
        bytes_per_pixel = 2
    elif dtype == 'int32' or dtype == 'uint32' or dtype == 'float32':
        bytes_per_pixel = 4
    else:
        print(f"Unsupported dtype: {dtype}")
        return None
    
    # Check if file is big enough
    if len(data) < width * height * bytes_per_pixel:
        print(f"File too small for {width}x{height} {dtype} grid")
        return None
    
    # Try different header sizes
    for header_size in [0, 4, 8, 16, 32, 48, 64, 128]:
        if len(data) < header_size + width * height * bytes_per_pixel:
            continue
        
        try:
            # Extract data starting at this offset
            grid_data = np.frombuffer(data[header_size:header_size + width * height * bytes_per_pixel], dtype=dtype)
            
            # Reshape if possible
            if len(grid_data) >= width * height:
                grid = grid_data[:width * height].reshape(height, width)
                
                # Skip if all values are the same
                if np.all(grid == grid[0, 0]):
                    continue
                
                # Save as image
                plt.figure(figsize=(10, 10))
                plt.imshow(grid, cmap='viridis')
                plt.title(f"{output_name} - {dtype} - Header {header_size}")
                plt.colorbar()
                plt.savefig(f"{output_name}_{dtype}_header{header_size}.png")
                plt.close()
                
                # Also save a black and white version
                plt.figure(figsize=(10, 10))
                plt.imshow(grid, cmap='gray')
                plt.title(f"{output_name} - {dtype} - Header {header_size} (grayscale)")
                plt.colorbar()
                plt.savefig(f"{output_name}_{dtype}_header{header_size}_gray.png")
                plt.close()
                
                print(f"Saved {output_name}_{dtype}_header{header_size}.png")
                
                # Return the grid data for further processing
                return {'header_size': header_size, 'dtype': dtype, 'grid': grid}
        except Exception as e:
            print(f"Error with {dtype} at header size {header_size}: {str(e)}")
    
    print(f"No valid interpretation found as {dtype}")
    return None

def process_file(file_path, width, height, base_name):
    """Process a single map file"""
    print(f"\nProcessing {file_path}...")
    data = read_binary_file(file_path)
    print(f"File size: {len(data)} bytes")
    
    # Try different data types
    results = []
    dtypes = ['uint8', 'int16', 'uint16', 'int32', 'float32']
    
    for dtype in dtypes:
        result = try_grid_format(data, width, height, dtype, base_name)
        if result:
            results.append(result)
    
    return results

def main():
    # Load map info
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    width = map_info['width']
    height = map_info['height']
    resolution = map_info['resolution']
    
    print(f"Map dimensions: {width}x{height} pixels")
    print(f"Resolution: {resolution} meters per pixel")
    
    # Map files to process
    map_files = {
        'map.gridmap': 'gridmap',
        'map.segmentmap': 'segmentmap',
        'map_record.map': 'recordmap',
        'path_map': 'pathmap'
    }
    
    # Process each file
    all_results = {}
    for file_path, base_name in map_files.items():
        if os.path.exists(file_path):
            results = process_file(file_path, width, height, base_name)
            if results:
                all_results[file_path] = results
    
    # Special processing for map_record.map - try using the exact size as specified
    special_file = 'map_record.map'
    if os.path.exists(special_file):
        data = read_binary_file(special_file)
        
        # Try direct interpretation without header
        if len(data) >= width * height:
            try:
                grid = np.frombuffer(data[:width * height], dtype=np.uint8).reshape(height, width)
                plt.figure(figsize=(10, 10))
                plt.imshow(grid, cmap='viridis')
                plt.title(f"Direct {special_file} interpretation")
                plt.colorbar()
                plt.savefig(f"direct_{special_file.replace('.', '_')}.png")
                plt.close()
                print(f"Saved direct_{special_file.replace('.', '_')}.png")
            except Exception as e:
                print(f"Error with direct interpretation: {str(e)}")
    
    print("\nProcessing complete!")
    print("Check the generated PNG files to see if any of them resemble your apartment layout.")

if __name__ == "__main__":
    main()