# Vacuum Map Converter for Home Assistant

This repository contains scripts to convert binary map data from robot vacuums to visual maps that can be displayed in Home Assistant. Initially developed for HSR Home M3, but may work with other models that use similar map formats.

![Sample Map](https://github.com/username/vacuum-map-converter/raw/main/docs/sample_map.png)

## Features

- Converts binary map files to PNG images
- Shows walls, rooms, and forbidden zones
- Displays charger position
- Generates base64 encoded maps for direct use in Home Assistant
- Includes debugging tools to analyze binary map formats

## Supported Devices

- HSR Home M3 (tested and confirmed working)
- Other models that use similar map formats may also work (untested)

## Prerequisites

- Python 3.6+
- Python packages: numpy, matplotlib, pillow

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/username/vacuum-map-converter.git
   cd vacuum-map-converter
   ```

2. Install required packages:
   ```
   pip install numpy matplotlib pillow
   ```

## Usage

1. Download the map files from your vacuum robot
2. Run the map converter script:
   ```
   python ha_map_converter.py
   ```
3. The script will generate:
   - `vacuum_map_ha.png`: Visual map image
   - `vacuum_map_ha.base64.txt`: Base64 encoded map for Home Assistant

### Setting Up in Home Assistant

#### Method 1: Using a Local File Camera

1. Copy the generated `vacuum_map_ha.png` to your Home Assistant configuration directory
2. Add the following to your `configuration.yaml` file:

```yaml
camera:
  - platform: local_file
    name: Vacuum Map
    file_path: vacuum_map_ha.png
```

3. Restart Home Assistant
4. Add a camera card to your dashboard that uses the new entity

#### Method 2: Using Base64 Image Data

1. Copy the contents of `vacuum_map_ha.base64.txt`
2. In your Lovelace UI, add a Picture Element card:

```yaml
type: picture-elements
image: data:image/png;base64,YOUR_BASE64_DATA_HERE
elements: []
```

Replace `YOUR_BASE64_DATA_HERE` with the content of the base64 file.

## Troubleshooting

If the generated map doesn't look right:

1. Try the alternative scripts:
   - `direct_convert.py`: Tries all possible offsets
   - `direct_approach.py`: Tries different data types and header sizes
   - `simple_convert.py`: Simplified approach for map conversion

2. Check the output of these scripts to find an image that resembles your apartment layout, then modify `ha_map_converter.py` accordingly.

## Contributing

Contributions are welcome! If you've got this working with another vacuum model, please submit a pull request with your modifications.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE.md) file for details.