bl_info = {
    "name": "Import .SKIN (Multi-Submesh) Model",
    "author": "Your Name",
    "version": (1, 1),
    "blender": (2, 80, 0),
    "location": "File > Import > SKIN Model (.skin)",
    "description": "Import custom .SKIN model files with multiple submeshes, materials, and texture references",
    "category": "Import-Export",
}

import bpy
import struct
import os
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty
from bpy.types import Operator


def read_material(f):
    """
    Read one material_t structure from the file.
    New structure:
        uint32_t // color1
        uint32_t // color2
        float    // alpha (or another float value)
        uint32_t // color3
        uint32_t // color4
        uint8_t  // flag
        uint32_t texture_name_length
        char[texture_name_length] texture1_name
        uint32_t texture2_name_length
        char[texture2_name_length] texture2_name
        uint32_t texture3_name_length
        char[texture3_name_length] texture3_name
        uint32_t material_name_length
        char[material_name_length] material_name
    """
    # Read two color fields
    color1, color2 = struct.unpack("<II", f.read(8))
    # Read the float value
    alpha = struct.unpack("<f", f.read(4))[0]
    # Read two more color fields
    color3, color4 = struct.unpack("<II", f.read(8))
    # Read a flag (unused)
    flag1 = struct.unpack("<B", f.read(1))[0]

    # Texture1 name
    tex1_name_len = struct.unpack("<I", f.read(4))[0]
    texture1_name = f.read(tex1_name_len).decode("utf-8", errors="ignore") if tex1_name_len > 0 else ""

    # Texture2 name
    tex2_name_len = struct.unpack("<I", f.read(4))[0]
    texture2_name = f.read(tex2_name_len).decode("utf-8", errors="ignore") if tex2_name_len > 0 else ""

    # Texture3 name
    tex3_name_len = struct.unpack("<I", f.read(4))[0]
    texture3_name = f.read(tex3_name_len).decode("utf-8", errors="ignore") if tex3_name_len > 0 else ""

    # Material name
    mat_name_len = struct.unpack("<I", f.read(4))[0]
    material_name = f.read(mat_name_len).decode("utf-8", errors="ignore") if mat_name_len > 0 else ""

    return {
        "color1": color1,
        "color2": color2,
        "alpha": alpha,
        "color3": color3,
        "color4": color4,
        "flag1": flag1,
        "texture1_name": texture1_name,
        "texture2_name": texture2_name,
        "texture3_name": texture3_name,
        "material_name": material_name
    }


def create_blender_material(mat_data, search_dir=None):
    """
    Create a Blender material from the given material data.
    Uses texture1_name to set the diffuse/base color slot.
    """
    mat_name = mat_data["material_name"] if mat_data["material_name"] else "ImportedMaterial"
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True

    # Find or create a Principled BSDF node
    principled_node = None
    for node in mat.node_tree.nodes:
        if node.type == 'BSDF_PRINCIPLED':
            principled_node = node
            break
    if not principled_node:
        principled_node = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
        principled_node.location = (0, 0)
        output_node = None
        for node in mat.node_tree.nodes:
            if node.type == 'OUTPUT_MATERIAL':
                output_node = node
                break
        if output_node is None:
            output_node = mat.node_tree.nodes.new("ShaderNodeOutputMaterial")
            output_node.location = (200, 0)
        mat.node_tree.links.new(principled_node.outputs['BSDF'], output_node.inputs['Surface'])

    # Use texture1 for the diffuse/base color if available.
    tex_name = mat_data["texture1_name"].strip()
    if tex_name:
        if search_dir:
            potential_path = os.path.join(search_dir, tex_name)
        else:
            potential_path = tex_name

        tex_node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.location = (-300, 0)
        try:
            image = bpy.data.images.load(potential_path)
            tex_node.image = image
        except Exception as e:
            print(f"Could not load image '{potential_path}': {e}")
            image = bpy.data.images.new(tex_name, 1024, 1024)
            tex_node.image = image

        mat.node_tree.links.new(tex_node.outputs['Color'], principled_node.inputs['Base Color'])

    return mat


def read_submesh(f, context, search_dir=None):
    """
    Read one submesh_t structure from the file.
    Structure:
        uint32_t name_length
        char[name_length] name
        uint32_t vertex_count
        float[3][vertex_count] vertices
        uint32_t face_count
        uint32_t[face_count] faces
        uint8_t
        uint32_t uv_count
        float[2][uv_count] uvs
        uint8_t
        uint32_t normal_count
        float[3][normal_count] normals
        uint8_t
        uint32_t
        uint32_t material_count
        material_t[material_count] materials
        uint32_t matid_count
        uint16_t[matid_count] matids
        uint32_t
        uint32_t
        uint32_t
        uint32_t
    """
    # 1) Submesh name
    name_len = struct.unpack("<I", f.read(4))[0]
    submesh_name = f.read(name_len).decode("utf-8", errors="ignore") if name_len > 0 else "Submesh"

    # 2) Vertex data
    vertex_count = struct.unpack("<I", f.read(4))[0]
    vertices = []
    if vertex_count > 0:
        verts_data = struct.unpack("<" + "f" * (vertex_count * 3), f.read(vertex_count * 12))
        for i in range(vertex_count):
            vertices.append((verts_data[i*3], verts_data[i*3+1], verts_data[i*3+2]))

    # 3) Face data
    face_count = struct.unpack("<I", f.read(4))[0]
    face_indices = []
    if face_count > 0:
        face_indices_raw = struct.unpack("<" + "I" * face_count, f.read(face_count * 4))
        # Assuming triangles (group in threes)
        face_indices = [face_indices_raw[i:i+3] for i in range(0, face_count, 3)]

    # 4) UV data
    uv_flag = struct.unpack("<B", f.read(1))[0]
    uv_count = struct.unpack("<I", f.read(4))[0]
    uvs = []
    if uv_count > 0:
        uv_data = struct.unpack("<" + "f" * (uv_count * 2), f.read(uv_count * 8))
        for i in range(uv_count):
            uvs.append((uv_data[i*2], uv_data[i*2+1]))

    # 5) Normal data
    normal_flag = struct.unpack("<B", f.read(1))[0]
    normal_count = struct.unpack("<I", f.read(4))[0]
    normals = []
    if normal_count > 0:
        normal_data = struct.unpack("<" + "f" * (normal_count * 3), f.read(normal_count * 12))
        for i in range(normal_count):
            normals.append((normal_data[i*3], normal_data[i*3+1], normal_data[i*3+2]))

    # 6) Some unknown fields
    extra_flag = struct.unpack("<B", f.read(1))[0]
    unknown_int3 = struct.unpack("<I", f.read(4))[0]

    # 7) Materials
    material_count = struct.unpack("<I", f.read(4))[0]
    materials = []
    for _ in range(material_count):
        mat_data = read_material(f)
        materials.append(mat_data)

    # 8) Material IDs
    matid_count = struct.unpack("<I", f.read(4))[0]
    matids = []
    if matid_count > 0:
        matids = struct.unpack("<" + "H" * matid_count, f.read(matid_count * 2))

    # 9) Four more unknown uint32 values
    unknown_tail = struct.unpack("<IIII", f.read(16))

    # --- Create Mesh in Blender ---
    mesh = bpy.data.meshes.new(name=submesh_name)
    mesh.from_pydata(vertices, [], face_indices)
    mesh.update()

    # Create a UV layer if appropriate (assuming one UV per vertex)
    if uvs and (len(uvs) == len(vertices)):
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for poly in mesh.polygons:
            for loop_idx in poly.loop_indices:
                vert_idx = mesh.loops[loop_idx].vertex_index
                uv_layer.data[loop_idx].uv = uvs[vert_idx]

    # Create custom normals if provided (auto smooth is no longer set)
    if normals and (len(normals) == len(vertices)):
        try:
            mesh.normals_split_custom_set_from_vertices(normals)
        except Exception as e:
            print(f"Warning: Could not set custom normals: {e}")
        mesh.update()

    # Create the object and link it to the scene
    obj = bpy.data.objects.new(submesh_name, mesh)
    context.collection.objects.link(obj)
    context.view_layer.objects.active = obj

    # Create material slots for each imported material and assign faces based on the matids array
    for mat_data in materials:
        mat = create_blender_material(mat_data, search_dir=search_dir)
        obj.data.materials.append(mat)

    num_faces = len(face_indices)  # number of triangles
    if matids and len(matids) == num_faces:
        for poly_index, poly in enumerate(mesh.polygons):
            mat_index = matids[poly_index]
            if mat_index < len(obj.data.materials):
                poly.material_index = mat_index

    return obj


class ImportSkinMultiSubmesh(Operator, ImportHelper):
    """Import a multi-submesh .SKIN model file"""
    bl_idname = "import_scene.skin_multisubmesh"
    bl_label = "Import SKIN (Multi-Submesh)"
    filename_ext = ".skin"
    filter_glob: StringProperty(default="*.skin", options={'HIDDEN'})

    def execute(self, context):
        return self.read_file(context, self.filepath)

    def read_file(self, context, filepath):
        # Use the file's directory to help locate textures
        search_dir = os.path.dirname(filepath)

        with open(filepath, "rb") as f:
            # Read header: 1 byte, 3 uint32, then submesh_count uint32
            header_byte = struct.unpack("<B", f.read(1))[0]
            header_values = struct.unpack("<III", f.read(12))
            submesh_count = struct.unpack("<I", f.read(4))[0]

            # For each submesh, parse and create an object
            for _ in range(submesh_count):
                read_submesh(f, context, search_dir=search_dir)

        return {'FINISHED'}


def menu_func_import(self, context):
    self.layout.operator(ImportSkinMultiSubmesh.bl_idname, text="SKIN Model (Multi-Submesh) (.skin)")


def register():
    bpy.utils.register_class(ImportSkinMultiSubmesh)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.unregister_class(ImportSkinMultiSubmesh)


if __name__ == "__main__":
    register()
