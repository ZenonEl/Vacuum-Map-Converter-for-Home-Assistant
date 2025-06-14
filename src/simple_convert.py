import numpy as np
import matplotlib.pyplot as plt
import json
import struct
import os
from PIL import Image
import sys

def read_binary_file(file_path):
    with open(file_path, 'rb') as f:
        data = f.read()
    return data

def analyze_gridmap(data, map_info):
    # Get dimensions from map_record.json
    width = map_info['width']
    height = map_info['height']
    
    # Analyze the file structure
    print(f"Gridmap file size: {len(data)} bytes")
    print(f"Map dimensions: {width}x{height} = {width*height} pixels")
    
    # Try several offsets to find meaningful data
    possible_data_sections = []
    
    # Try different data types and offsets
    for offset in range(0, 1024, 4):  # Try offsets up to 1KB
        if offset + width*height > len(data):
            break
            
        # Try as bytes
        try:
            grid_bytes = np.frombuffer(data[offset:offset+width*height], dtype=np.uint8)
            if len(grid_bytes) == width*height:
                unique_values = np.unique(grid_bytes)
                if len(unique_values) > 1 and len(unique_values) < 20:  # Reasonable number of unique values for a map
                    possible_data_sections.append({
                        'offset': offset,
                        'dtype': 'uint8',
                        'unique_values': unique_values,
                        'data': grid_bytes.reshape(height, width)
                    })
                    print(f"Possible data section at offset {offset} (uint8): {unique_values}")
        except Exception as e:
            print(f"Error with uint8 at offset {offset}: {str(e)}")
            
        # Try as int16
        if offset + width*height*2 <= len(data):
            try:
                grid_int16 = np.frombuffer(data[offset:offset+width*height*2], dtype=np.int16)
                if len(grid_int16) == width*height:
                    unique_values = np.unique(grid_int16)
                    if len(unique_values) > 1 and len(unique_values) < 20:
                        possible_data_sections.append({
                            'offset': offset,
                            'dtype': 'int16',
                            'unique_values': unique_values,
                            'data': grid_int16.reshape(height, width)
                        })
                        print(f"Possible data section at offset {offset} (int16): {unique_values}")
            except Exception as e:
                print(f"Error with int16 at offset {offset}: {str(e)}")
    
    return possible_data_sections

def save_possible_maps(data_sections, prefix):
    if not data_sections:
        print(f"No valid data sections found for {prefix}")
        return
        
    for i, section in enumerate(data_sections):
        # Normalize data for visualization
        data = section['data']
        print(f"Processing section {i+1} for {prefix}. Shape: {data.shape}, Unique values: {section['unique_values']}")
        
        # Create a color map
        cmap = plt.cm.get_cmap('viridis', len(section['unique_values']))
        
        # Create a colored image
        colored_data = np.zeros((data.shape[0], data.shape[1], 3), dtype=np.uint8)
        
        for j, val in enumerate(section['unique_values']):
            mask = (data == val)
            color = (np.array(cmap(j)[:3]) * 255).astype(np.uint8)
            colored_data[mask] = color
        
        # Save the image
        img = Image.fromarray(colored_data)
        output_path = f"{prefix}_option_{i+1}.png"
        img.save(output_path)
        print(f"Saved potential map to {output_path}")
        
        # Also save a black and white version
        plt.figure(figsize=(10, 10))
        plt.imshow(data, cmap='gray')
        plt.axis('off')
        plt.savefig(f"{prefix}_option_{i+1}_bw.png", bbox_inches='tight', pad_inches=0)
        plt.close()
        print(f"Saved black and white version to {prefix}_option_{i+1}_bw.png")

def analyze_file(file_path, map_info, prefix):
    print(f"Analyzing {file_path}...")
    data = read_binary_file(file_path)
    possible_sections = analyze_gridmap(data, map_info)
    save_possible_maps(possible_sections, prefix)
    return possible_sections

def main():
    # Load map info
    with open('map_record.json', 'r') as f:
        map_info = json.load(f)
    
    print(f"Loaded map info: width={map_info['width']}, height={map_info['height']}, resolution={map_info['resolution']}")
    
    # Try a direct approach first - we know the map is 170x190 pixels
    width = map_info['width']
    height = map_info['height']
    
    # Analyze map.gridmap directly with different offsets
    print("\nDirect analysis of map.gridmap...")
    gridmap_data = read_binary_file('map.gridmap')
    
    # Try with fixed header size of 32 bytes
    header_size = 32
    if header_size + width * height <= len(gridmap_data):
        try:
            grid = np.frombuffer(gridmap_data[header_size:header_size+width*height], dtype=np.uint8)
            grid = grid.reshape(height, width)
            
            # Save direct visualization
            plt.figure(figsize=(10, 10))
            plt.imshow(grid, cmap='gray')
            plt.axis('off')
            plt.savefig("direct_gridmap.png", bbox_inches='tight', pad_inches=0)
            plt.close()
            print(f"Saved direct visualization to direct_gridmap.png")
            
            # Try with different colormap
            plt.figure(figsize=(10, 10))
            plt.imshow(grid, cmap='viridis')
            plt.axis('off')
            plt.savefig("direct_gridmap_color.png", bbox_inches='tight', pad_inches=0)
            plt.close()
            print(f"Saved colorized visualization to direct_gridmap_color.png")
        except Exception as e:
            print(f"Error in direct visualization: {str(e)}")
    
    # Analyze both map files with offset scanning
    gridmap_sections = analyze_file('map.gridmap', map_info, 'gridmap')
    segmentmap_sections = analyze_file('map.segmentmap', map_info, 'segmentmap')
    
    # If map_record.map doesn't look like 0x7F bytes, analyze it too
    map_record_data = read_binary_file('map_record.map')
    if not all(b == 0x7F for b in map_record_data[:100]):
        map_record_sections = analyze_file('map_record.map', map_info, 'map_record')
    
    # If present, also analyze path files
    if os.path.exists('path_map'):
        path_map_sections = analyze_file('path_map', map_info, 'path_map')
    
    print("\nAnalysis complete! Check the generated PNG files to see which one matches your apartment layout.")
    print("Once identified, you can use this information to create a proper map converter.")

if __name__ == "__main__":
    main()