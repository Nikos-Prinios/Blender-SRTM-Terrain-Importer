# SRTM Terrain Importer for Blender

A Blender addon that imports SRTM (Shuttle Radar Topography Mission) HGT files as accurate 3D terrain with proper georeferencing and elevation data.

## Features

- Import SRTM 1 arc-second (30m) elevation data as 3D terrain
- Accurate geographic dimensions based on latitude
- Real-world elevation values
- Adjustable vertical scale
- Choice of color schemes (natural terrain or grayscale)
- Automatic UV mapping for texturing
- Displacement-based mesh detail
- Metadata storage (coordinates, elevation range, dimensions)

## Usage

1. Go to File > Import > SRTM HGT (.hgt)
2. Select your .hgt file
3. Adjust import settings:
   - Subdivisions: Controls mesh detail (higher = more detail but slower)
   - Vertical Scale: Multiplier for elevation values (1.0 = real scale)
   - Color Scheme: Choose between natural terrain colors or grayscale

## Getting SRTM Data

1. Visit https://dwtkns.com/srtm30m/ to browse and select terrain tiles
2. Create a free NASA Earthdata account at https://urs.earthdata.nasa.gov/ if you don't have one
3. Download the desired .hgt files
4. Files are named based on their coordinates (e.g., N37W123.hgt)

## Technical Details

- Supports SRTM 1 arc-second (30m) resolution data
- Creates proper mesh geometry with displacement mapping
- Calculates accurate tile dimensions based on latitude
- Stores geographic metadata in the object properties
- Uses Cycles displacement for high-quality rendering
- Compatible with Blender 4.2+

## Known Limitations

- Large files may require significant memory
- High subdivision levels can impact performance
- Vertical scale may need adjustment for visual clarity in areas with low elevation variation

## License

This addon is released under the GNU General Public License v3.0 or later.

## Credits

Created by Nikos Priniotakis

SRTM data courtesy of NASA/USGS.

## Support

For issues, questions, or contributions, please visit the GitHub repository.
