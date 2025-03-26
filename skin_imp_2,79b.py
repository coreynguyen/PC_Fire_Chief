bl_info = {
    "name": "Import .SKIN (Multi-Submesh) for Blender 2.79",
    "author": "Your Name",
    "version": (1, 1),
    "blender": (2, 79, 0),
    "location": "File > Import",
    "description": "Import .SKIN files (multi-submesh, materials, textures) for Blender 2.79 with custom normals",
    "category": "Import-Export",
}

import bpy
import struct
import os

from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator


def read_material_279(f):
    """
    Reads a material_t structure with three possible textures, as described:
        struct material_t (
            uint32_t color1
            uint32_t color2
            float    alpha
            uint32_t color3
            uint32_t color4
            uint8_t  flag
            uint32_t texture1_name_length
            char[texture1_name_length] texture1_name
            uint32_t texture2_name_length
            char[texture2_name_length] texture2_name
            uint32_t texture3_name_length
            char[texture3_name_length] texture3_name
            uint32_t material_name_length
            char[material_name_length] material_name
        )
    """
    color1, color2 = struct.unpack("<II", f.read(8))
    alpha = struct.unpack("<f", f.read(4))[0]
    color3, color4 = struct.unpack("<II", f.read(8))
    flag = struct.unpack("<B", f.read(1))[0]

    tex1_len = struct.unpack("<I", f.read(4))[0]
    texture1_name = f.read(tex1_len).decode("utf-8", errors="ignore") if tex1_len > 0 else ""

    tex2_len = struct.unpack("<I", f.read(4))[0]
    texture2_name = f.read(tex2_len).decode("utf-8", errors="ignore") if tex2_len > 0 else ""

    tex3_len = struct.unpack("<I", f.read(4))[0]
    texture3_name = f.read(tex3_len).decode("utf-8", errors="ignore") if tex3_len > 0 else ""

    mat_name_len = struct.unpack("<I", f.read(4))[0]
    material_name = f.read(mat_name_len).decode("utf-8", errors="ignore") if mat_name_len > 0 else "ImportedMaterial"

    return {
        "color1": color1,
        "color2": color2,
        "alpha": alpha,
        "color3": color3,
        "color4": color4,
        "flag": flag,
        "texture1_name": texture1_name,
        "texture2_name": texture2_name,
        "texture3_name": texture3_name,
        "material_name": material_name,
    }


def create_blender_material_279(mat_data, search_dir=None):
    """
    Creates a Blender Material in 2.79 style using nodes (Principled BSDF).
    Uses 'texture1_name' as the diffuse/base color texture.
    """
    mat_name = mat_data["material_name"] if mat_data["material_name"] else "ImportedMaterial"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    # Find the output and principled nodes if they exist
    principled_node = None
    output_node = None
    for node in mat.node_tree.nodes:
        if node.type == 'OUTPUT_MATERIAL':
            output_node = node
        elif node.type == 'BSDF_PRINCIPLED':
            principled_node = node

    if not output_node:
        output_node = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
        output_node.location = (300, 0)

    if not principled_node:
        principled_node = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        principled_node.location = (0, 0)
        mat.node_tree.links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    tex_path = mat_data["texture1_name"].strip()
    if tex_path:
        if search_dir:
            full_path = os.path.join(search_dir, tex_path)
        else:
            full_path = tex_path

        tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.location = (-300, 0)
        try:
            img = bpy.data.images.load(full_path)
            tex_node.image = img
        except Exception as e:
            print("Warning: could not load {}, creating placeholder image.".format(full_path))
            img = bpy.data.images.new(tex_path, 1024, 1024)
            tex_node.image = img

        mat.node_tree.links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])

    return mat


def read_submesh_279(f, scene, search_dir=None):
    """
    Reads a single submesh structure and creates a Mesh and Object in Blender 2.79.
    Structure:
        uint32_t name_length
        char[name_length] name
        uint32_t vertex_count
        float[3][vertex_count] vertices
        uint32_t face_count
        uint32_t[face_count] faces
        uint8_t  uv_flag
        uint32_t uv_count
        float[2][uv_count] uvs
        uint8_t  normal_flag
        uint32_t normal_count
        float[3][normal_count] normals
        uint8_t  extra_flag
        uint32_t unknown_int3
        uint32_t material_count
        material_t[material_count] materials
        uint32_t matid_count
        uint16_t[matid_count] matids
        uint32_t unknown_tail[4]
    """

    # 1) Name
    submesh_name_len = struct.unpack("<I", f.read(4))[0]
    submesh_name = f.read(submesh_name_len).decode("utf-8", errors="ignore") if submesh_name_len > 0 else "Submesh"

    # 2) Vertices
    vertex_count = struct.unpack("<I", f.read(4))[0]
    vertices = []
    if vertex_count > 0:
        vert_data = struct.unpack("<" + "f" * (vertex_count * 3), f.read(vertex_count * 12))
        for i in range(vertex_count):
            x = vert_data[i * 3 + 0]
            y = vert_data[i * 3 + 1]
            z = vert_data[i * 3 + 2]
            vertices.append((x, y, z))

    # 3) Faces (assume triangles)
    face_count = struct.unpack("<I", f.read(4))[0]
    face_indices = []
    if face_count > 0:
        face_data = struct.unpack("<" + "I" * face_count, f.read(face_count * 4))
        face_indices = [face_data[i:i+3] for i in range(0, face_count, 3)]

    # 4) UV Data
    uv_flag = struct.unpack("<B", f.read(1))[0]
    uv_count = struct.unpack("<I", f.read(4))[0]
    uvs = []
    if uv_count > 0:
        uv_data = struct.unpack("<" + "f" * (uv_count * 2), f.read(uv_count * 8))
        for i in range(uv_count):
            u = uv_data[i * 2 + 0]
            v = uv_data[i * 2 + 1]
            uvs.append((u, v))

    # 5) Normals
    normal_flag = struct.unpack("<B", f.read(1))[0]
    normal_count = struct.unpack("<I", f.read(4))[0]
    normals = []
    if normal_count > 0:
        normal_data = struct.unpack("<" + "f" * (normal_count * 3), f.read(normal_count * 12))
        for i in range(normal_count):
            nx = normal_data[i * 3 + 0]
            ny = normal_data[i * 3 + 1]
            nz = normal_data[i * 3 + 2]
            normals.append((nx, ny, nz))

    # 6) Extra fields
    extra_flag = struct.unpack("<B", f.read(1))[0]
    unknown_int3 = struct.unpack("<I", f.read(4))[0]

    # 7) Materials
    material_count = struct.unpack("<I", f.read(4))[0]
    materials = []
    for _ in range(material_count):
        mat_data = read_material_279(f)
        materials.append(mat_data)

    # 8) Material IDs
    matid_count = struct.unpack("<I", f.read(4))[0]
    matids = []
    if matid_count > 0:
        matids = struct.unpack("<" + "H" * matid_count, f.read(matid_count * 2))

    # 9) Unknown tail
    unknown_tail = struct.unpack("<IIII", f.read(16))

    # --- Create the mesh in Blender 2.79 ---
    mesh = bpy.data.meshes.new(name=submesh_name)
    mesh.from_pydata(vertices, [], face_indices)
    mesh.update()

    # Create a UV map.
    # In 2.79 we create a UV map using uv_textures.new and then access the active UV layer.
    if uvs and (len(uvs) == len(vertices)):
        if len(mesh.uv_textures) == 0:
            mesh.uv_textures.new(name="UVMap")
        uv_data = mesh.uv_layers.active.data
        for poly in mesh.polygons:
            for li in range(poly.loop_start, poly.loop_start + poly.loop_total):
                vi = mesh.loops[li].vertex_index
                uv_data[li].uv = uvs[vi]

    # Set custom normals if available: enable auto smooth and set smooth shading.
    if normals and (len(normals) == len(vertices)):
        mesh.use_auto_smooth = True
        try:
            mesh.normals_split_custom_set_from_vertices(normals)
        except Exception as e:
            print("Could not set custom normals: {}".format(e))
        mesh.update()
        for poly in mesh.polygons:
            poly.use_smooth = True

    # Create the object and link it to the scene (2.79 style)
    obj = bpy.data.objects.new(submesh_name, mesh)
    scene.objects.link(obj)
    scene.objects.active = obj

    # Add material slots and create materials
    for mat_data in materials:
        mat = create_blender_material_279(mat_data, search_dir=search_dir)
        obj.data.materials.append(mat)

    # Assign material indices to faces based on matids
    num_faces = len(face_indices)
    if matids and (len(matids) == num_faces):
        for face_idx, poly in enumerate(mesh.polygons):
            mat_index = matids[face_idx]
            if mat_index < len(obj.data.materials):
                poly.material_index = mat_index

    return obj


def read_skin_file_279(context, filepath):
    """
    Main function that reads the .SKIN file header, loops over submeshes, and builds them.
    """
    print("Importing .SKIN file: ", filepath)
    scene = bpy.context.scene
    search_dir = os.path.dirname(filepath)

    with open(filepath, "rb") as f:
        header_byte = struct.unpack("<B", f.read(1))[0]
        header_vals = struct.unpack("<III", f.read(12))  # 3 uint32 values
        submesh_count = struct.unpack("<I", f.read(4))[0]

        for _ in range(submesh_count):
            read_submesh_279(f, scene, search_dir=search_dir)

    print("Finished importing .SKIN file.")
    return {'FINISHED'}


class ImportSKIN_279(Operator, ImportHelper):
    """Import a .SKIN (multi-submesh) file (Blender 2.79)"""
    bl_idname = "import_test.skin_279"
    bl_label = "Import .SKIN (2.79)"

    filename_ext = ".skin"
    filter_glob = StringProperty(default="*.skin", options={'HIDDEN'})

    some_setting = BoolProperty(
        name="Example Setting",
        description="Example bool",
        default=True,
    )

    def execute(self, context):
        return read_skin_file_279(context, self.filepath)


def menu_func_import_279(self, context):
    self.layout.operator(ImportSKIN_279.bl_idname, text="SKIN Model (2.79) (.skin)")


def register():
    bpy.utils.register_class(ImportSKIN_279)
    bpy.types.INFO_MT_file_import.append(menu_func_import_279)


def unregister():
    bpy.types.INFO_MT_file_import.remove(menu_func_import_279)
    bpy.utils.unregister_class(ImportSKIN_279)


if __name__ == "__main__":
    register()
    # To test the importer, uncomment the following line:
    # bpy.ops.import_test.skin_279('INVOKE_DEFAULT')
