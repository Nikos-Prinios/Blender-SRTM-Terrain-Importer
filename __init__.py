# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "SRTM Terrain Importer",
    "author": "Nikos Priniotakis",
    "version": (1, 0, 1),
    "blender": (4, 2, 0),
    "location": "File > Import > SRTM HGT (.hgt)",
    "description": """Import SRTM (Shuttle Radar Topography Mission) HGT files as 3D terrain meshes.
    
HGT files contain elevation data collected by NASA's SRTM mission and can be obtained from various sources like USGS Earth Explorer.
The addon creates accurately scaled terrain with:
- Real-world dimensions based on latitude
- Elevation-based color gradient material
- Adjustable vertical scale and subdivision levels
- Support for both 1 arc-second (30m) and 3 arc-second (90m) resolution

Location: File > Import > SRTM HGT (.hgt)""",
    "warning": "",
    "doc_url": "https://github.com/npriniotakis/blender-srtm-importer",
    "category": "Import-Export",
}

import bpy
import numpy as np
import os
import math
from mathutils import Vector
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper

# Utility functions
def get_tile_dimensions(lat):
    """Calculate actual dimensions of a 1-degree SRTM tile at given latitude"""
    EARTH_RADIUS = 6378137  # WGS84 equatorial radius in meters

    lat_rad = math.radians(lat)
    ns_distance = math.pi * EARTH_RADIUS / 180.0
    ew_distance = ns_distance * math.cos(lat_rad)

    return ew_distance, ns_distance

def setup_3d_views():
    """Configure viewport settings"""
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == 'VIEW_3D':
                for space in area.spaces:
                    if space.type == 'VIEW_3D':
                        space.clip_start = 1
                        space.clip_end = 1e+06

def create_heightmap_texture(context, heightmap, name):
    """Create texture from heightmap data"""
    size = heightmap.shape[0]

    height_min, height_max = heightmap.min(), heightmap.max()
    heightmap_normalized = (heightmap - height_min) / (height_max - height_min)

    texture = bpy.data.images.new(name=f"{name}_height", width=size, height=size)
    pixels = []
    for y in range(size):
        for x in range(size):
            pixels.extend([heightmap_normalized[y, x], 0, 0, 1])
    texture.pixels = pixels

    return texture

def create_terrain_material(name, height_texture, dem_min, dem_max, width, height, scale_z=1.0,
                          color_scheme='default'):
    """Create terrain material with accurate elevation mapping"""
    material = bpy.data.materials.new(name=f"{name}_material")
    material.use_nodes = True
    nodes = material.node_tree.nodes
    links = material.node_tree.links

    nodes.clear()

    # Create nodes
    output = nodes.new('ShaderNodeOutputMaterial')
    principled_bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    geometry = nodes.new('ShaderNodeNewGeometry')
    separate_xyz = nodes.new('ShaderNodeSeparateXYZ')
    map_range = nodes.new('ShaderNodeMapRange')
    color_ramp = nodes.new('ShaderNodeValToRGB')
    displacement = nodes.new('ShaderNodeDisplacement')
    texture = nodes.new('ShaderNodeTexImage')

    texture.image = height_texture

    principled_bsdf.inputs['Metallic'].default_value = 0.0
    principled_bsdf.inputs['Roughness'].default_value = 0.461
    principled_bsdf.inputs['IOR'].default_value = 1.5
    principled_bsdf.inputs['Alpha'].default_value = 1.0

    height_range = dem_max - dem_min
    terrain_ratio = height_range / width
    displacement_scale = height_range * scale_z

    print(f"\n=== TERRAIN DEBUG INFO ===")
    print(f"DEM Range: {dem_min:.2f}m to {dem_max:.2f}m")
    print(f"Height Range: {height_range:.2f}m")
    print(f"Terrain width: {width:.2f}m")
    print(f"Height/Width ratio: {terrain_ratio:.4f}")
    print(f"Scale Z factor: {scale_z}")
    print(f"Final Displacement Scale: {displacement_scale:.2f}m")
    print(f"Map Range values: {dem_min/10.0:.2f}m to {dem_max/10.0:.2f}m")

    value_min = nodes.new('ShaderNodeValue')
    value_min.label = "DEM Min"
    value_min.outputs[0].default_value = dem_min
    value_min.location = (-800, -200)

    value_max = nodes.new('ShaderNodeValue')
    value_max.label = "DEM Max"
    value_max.outputs[0].default_value = dem_max
    value_max.location = (-800, -400)

    value_scale_z = nodes.new('ShaderNodeValue')
    value_scale_z.label = "Scale Z"
    value_scale_z.outputs[0].default_value = scale_z
    value_scale_z.location = (-800, -600)

    # Create Math nodes for calculations
    math_height_range = nodes.new('ShaderNodeMath')
    math_height_range.operation = 'SUBTRACT'
    math_height_range.label = "Height Range"
    math_height_range.location = (-600, -300)

    math_min_div10 = nodes.new('ShaderNodeMath')
    math_min_div10.operation = 'DIVIDE'
    math_min_div10.inputs[1].default_value = 10.0
    math_min_div10.label = "Min/10"
    math_min_div10.location = (-600, -100)

    math_max_div10 = nodes.new('ShaderNodeMath')
    math_max_div10.operation = 'DIVIDE'
    math_max_div10.inputs[1].default_value = 10.0
    math_max_div10.label = "Max/10"
    math_max_div10.location = (-600, -500)

    math_displacement_scale = nodes.new('ShaderNodeMath')
    math_displacement_scale.operation = 'MULTIPLY'
    math_displacement_scale.label = "Displacement Scale"
    math_displacement_scale.location = (-400, -400)

    # Connect Value and Math nodes
    links.new(value_min.outputs[0], math_height_range.inputs[1])
    links.new(value_max.outputs[0], math_height_range.inputs[0])

    links.new(value_min.outputs[0], math_min_div10.inputs[0])
    links.new(value_max.outputs[0], math_max_div10.inputs[0])

    links.new(math_height_range.outputs[0], math_displacement_scale.inputs[0])
    links.new(value_scale_z.outputs[0], math_displacement_scale.inputs[1])

    displacement.inputs['Midlevel'].default_value = 0.0
    displacement.space = 'OBJECT'
    links.new(math_displacement_scale.outputs[0], displacement.inputs['Scale'])

    map_range.inputs['To Min'].default_value = 0.0
    map_range.inputs['To Max'].default_value = 1.0
    map_range.clamp = True
    links.new(math_min_div10.outputs[0], map_range.inputs['From Min'])
    links.new(math_max_div10.outputs[0], map_range.inputs['From Max'])

    if color_scheme == 'default':
        # Convert hex to RGB values (0-1 range)
        colors = [
            (0.0, (0.000, 0.078, 0.153, 1.0)),  # #001427
            (0.25, (0.439, 0.553, 0.506, 1.0)),  # #708d81
            (0.5, (0.957, 0.835, 0.553, 1.0)),  # #f4d58d
            (0.75, (0.749, 0.024, 0.012, 1.0)),  # #bf0603
            (1.0, (0.553, 0.031, 0.004, 1.0))   # #8d0801
        ]
    elif color_scheme == 'grayscale':
        colors = [
            (0.0, (0.1, 0.1, 0.1, 1.0)),
            (0.33, (0.3, 0.3, 0.3, 1.0)),
            (0.66, (0.6, 0.6, 0.6, 1.0)),
            (1.0, (0.9, 0.9, 0.9, 1.0))
        ]

    for i in range(len(color_ramp.color_ramp.elements) - 1, 0, -1):
        color_ramp.color_ramp.elements.remove(color_ramp.color_ramp.elements[i])

    color_ramp.color_ramp.elements[0].position = colors[0][0]
    color_ramp.color_ramp.elements[0].color = colors[0][1]

    for pos, color in colors[1:]:
        elem = color_ramp.color_ramp.elements.new(pos)
        elem.color = color

    color_ramp.color_ramp.interpolation = 'LINEAR'

    # Position nodes
    output.location = (600, 0)
    principled_bsdf.location = (300, 100)
    geometry.location = (-600, 0)
    separate_xyz.location = (-400, 0)
    map_range.location = (-200, 0)
    color_ramp.location = (0, 0)
    texture.location = (-200, -300)
    displacement.location = (300, -200)

    links.new(geometry.outputs['Position'], separate_xyz.inputs['Vector'])
    links.new(separate_xyz.outputs['Z'], map_range.inputs[0])
    links.new(map_range.outputs[0], color_ramp.inputs[0])
    links.new(color_ramp.outputs['Color'], principled_bsdf.inputs['Base Color'])
    links.new(principled_bsdf.outputs['BSDF'], output.inputs['Surface'])
    links.new(texture.outputs['Color'], displacement.inputs['Height'])
    links.new(displacement.outputs['Displacement'], output.inputs['Displacement'])

    # Enable displacement
    material.cycles.displacement_method = 'DISPLACEMENT'
    material.displacement_method = 'DISPLACEMENT'

    return material

def create_terrain_from_hgt(filepath, subdivisions=50, scale_z=1.0, color_scheme='default'):
    """Create terrain mesh from HGT file with accurate dimensions"""
    # Read HGT file
    data = np.fromfile(filepath, dtype='>i2')
    size = int(np.sqrt(data.size))
    heightmap = data.reshape((size, size))

    # Extract coordinates from filename
    basename = os.path.basename(filepath)
    lat = int(basename[1:3])
    lon = int(basename[4:7])
    if basename[0] == 'S':
        lat = -lat
    if basename[3] == 'W':
        lon = -lon

    width, height = get_tile_dimensions(lat)

    bpy.ops.mesh.primitive_plane_add(size=1)
    plane = bpy.context.active_object
    plane.name = os.path.splitext(basename)[0]

    plane.location.x = width * lon
    plane.location.y = height * lat
    plane.scale.x = width
    plane.scale.y = height

    subdivision = plane.modifiers.new(name="Subdivisions", type='SUBSURF')
    subdivision.subdivision_type = 'SIMPLE'
    subdivision.levels = 2
    subdivision.render_levels = 2

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=subdivisions)
    bpy.ops.object.mode_set(mode='OBJECT')

    dem_min = float(heightmap.min())
    dem_max = float(heightmap.max())

    print(f"\n=== TERRAIN METRICS ===")
    print(f"Latitude: {lat}°")
    print(f"Longitude: {lon}°")
    print(f"Tile dimensions: {width/1000:.2f}km x {height/1000:.2f}km")
    print(f"Elevation range: {dem_min:.2f}m to {dem_max:.2f}m")

    height_texture = create_heightmap_texture(bpy.context, heightmap, plane.name)

    material = create_terrain_material(plane.name, height_texture, dem_min, dem_max,
                                     width, height, scale_z, color_scheme)
    plane.data.materials.append(material)

    # Store metadata
    plane["latitude"] = lat
    plane["longitude"] = lon
    plane["dem_min"] = dem_min
    plane["dem_max"] = dem_max
    plane["tile_width"] = width
    plane["tile_height"] = height

    return plane

class ImportHGTDisplacementOperator(bpy.types.Operator, ImportHelper):
    """Import SRTM HGT files as 3D terrain"""
    bl_idname = "import_mesh.hgt_displacement"
    bl_label = "Import SRTM HGT (.hgt)"
    bl_options = {'PRESET', 'UNDO'}

    filename_ext = ".hgt"

    filter_glob: StringProperty(
        default="*.hgt",
        options={'HIDDEN'},
    )

    subdivisions: IntProperty(
        name="Subdivisions",
        description="Number of mesh subdivisions",
        default=50,
        min=10,
        max=200,
    )

    scale_z: FloatProperty(
        name="Vertical Scale",
        description="Height multiplier (1.0 = real scale)",
        default=1.0,
        min=0.1,
        max=5.0,
        soft_min=0.2,
        soft_max=3.0,
        step=1,
        precision=2
    )

    color_scheme: bpy.props.EnumProperty(
        name="Color Scheme",
        description="Choose the terrain color scheme",
        items=[
            ('default', "Default", "Natural terrain colors"),
            ('grayscale', "Grayscale", "Black and white elevation map"),
        ],
        default='default'
    )

    def execute(self, context):
        setup_3d_views()

        terrain = create_terrain_from_hgt(
            self.filepath,
            self.subdivisions,
            self.scale_z,
            self.color_scheme
        )

        bpy.ops.object.select_all(action='DESELECT')
        terrain.select_set(True)
        context.view_layer.objects.active = terrain
        return {'FINISHED'}

class HGTImportFileHandler(bpy.types.FileHandler):
    """Support for dragging and dropping .hgt files into Blender"""
    bl_idname = "import_mesh.hgt_handler"
    bl_label = "Import SRTM HGT"
    bl_file_extensions = ".hgt"

    def save(self, context, filepath=""):
        return {'CANCELLED'}

    def load(self, context, filepath="", *, relpath=None):
        terrain = create_terrain_from_hgt(
            filepath,
            subdivisions=50,  # default values
            scale_z=1.0,
            color_scheme='default'
        )
        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(ImportHGTDisplacementOperator.bl_idname, text="SRTM HGT (.hgt)")

classes = (
    ImportHGTDisplacementOperator,
    HGTImportFileHandler,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
