# SKIN Import Addons for Blender

This repository contains two Blender addons for importing custom `.SKIN` files that store models with multi-submesh data, materials, textures, UV coordinates, and custom normals.

- **skin_imp.py**: Import addon for Blender 2.80+ (e.g., Blender 4.4).  
- **skin_imp_2,79b.py**: Import addon for Blender 2.79.

---

## Table of Contents

- [Overview](#overview)
- [File Structure](#file-structure)
- [.SKIN File Format Specification](#skin-file-format-specification)
- [Installation](#installation)
  - [Blender 2.80+](#blender-280)
  - [Blender 2.79](#blender-279)
- [Usage](#usage)
- [Features](#features)
- [Known Issues & Future Improvements](#known-issues--future-improvements)

---

## Overview

These addons allow you to import a custom binary `.SKIN` file format. The file format supports:
- Multiple submeshes (each imported as a separate object)
- Materials with up to three texture references per material
- UV mapping and custom normals

Each addon is tailored to the respective Blender API:
- **skin_imp.py** is designed for Blender 2.80+.
- **skin_imp_2,79b.py** is adapted for Blender 2.79, including differences in scene linking and UV handling.

---

## File Structure

```
.
├── skin_imp.py             # Import addon for Blender 2.80+ (e.g., Blender 4.4)
└── skin_imp_2,79b.py       # Import addon for Blender 2.79
```

---

## .SKIN File Format Specification

### Material Block

```c
struct material_t (
    uint32_t color1,
    uint32_t color2,
    float    alpha,
    uint32_t color3,
    uint32_t color4,
    uint8_t  flag,
    uint32_t texture1_name_length,
    char[texture1_name_length] texture1_name,
    uint32_t texture2_name_length,
    char[texture2_name_length] texture2_name,
    uint32_t texture3_name_length,
    char[texture3_name_length] texture3_name,
    uint32_t material_name_length,
    char[material_name_length] material_name
);
```

### Submesh Block

```c
struct submesh_t (
    uint32_t name_length,
    char[name_length] name,
    uint32_t vertex_count,
    float[3][vertex_count] vertices,
    uint32_t face_count,
    uint32_t[face_count] faces,
    uint8_t  uv_flag,
    uint32_t uv_count,
    float[2][uv_count] uvs,
    uint8_t  normal_flag,
    uint32_t normal_count,
    float[3][normal_count] normals,
    uint8_t  extra_flag,
    uint32_t unknown_int3,
    uint32_t material_count,
    material_t[material_count] materials,
    uint32_t matid_count,
    uint16_t[matid_count] matids,
    uint32_t unknown_tail[4]
);
```

### Global File Structure

```c
struct file_t (
    uint8_t  header_byte,
    uint32_t header_val1,
    uint32_t header_val2,
    uint32_t header_val3,
    uint32_t submesh_count,
    submesh_t[submesh_count] submeshes
);
```

---

## Installation

### Blender 2.80+

1. Open Blender.
2. Navigate to **Edit > Preferences > Add-ons**.
3. Click **Install...** and select the `skin_imp.py` file.
4. Enable the addon by checking its box.
5. The importer appears under **File > Import > SKIN Model (.skin)**.

### Blender 2.79

1. Open Blender 2.79.
2. Go to **File > User Preferences > Add-ons**.
3. Click **Install Add-on from File...** and select the `skin_imp_2,79b.py` file.
4. Enable the addon.
5. The importer appears under **File > Import > SKIN Model (2.79) (.skin)**.

---

## Usage

1. Place your `.SKIN` file in an accessible folder.
2. In Blender, navigate to the Import menu:
   - **Blender 2.80+**: **File > Import > SKIN Model (.skin)**
   - **Blender 2.79**: **File > Import > SKIN Model (2.79) (.skin)**
3. Select your `.SKIN` file.
4. The addon will parse the file and:
   - Create one object per submesh.
   - Build geometry with vertices and faces.
   - Assign UV coordinates.
   - Apply custom normals (with auto‑smooth enabled in Blender 2.79).
   - Create and assign materials with texture nodes (loading textures from the same folder as the `.SKIN` file).

---

## Features

- **Multi-Submesh Support**  
  Each submesh in the `.SKIN` file becomes a separate object in Blender.

- **Material & Texture Handling**  
  Materials are built using Blender’s node system with a Principled BSDF shader. The addon assigns textures (using `texture1_name`) to the Base Color input.

- **UV Mapping**  
  UV coordinates are imported and mapped to each vertex/face.

- **Custom Normals**  
  Vertex normals are applied:
  - In Blender 2.80+, normals are set directly.
  - In Blender 2.79, auto‑smooth is enabled and faces are marked smooth to support custom normals.

---

## Known Issues & Future Improvements

- **Normals in Blender 2.79**  
  Custom normals require auto‑smooth and smooth shading. Ensure your `.SKIN` files include valid normals.

- **Texture Path Resolution**  
  Currently, texture files are assumed to be located in the same directory as the `.SKIN` file. Future enhancements could include custom search paths or user-specified directories.

- **Robustness**  
  Further error handling could be added for cases such as missing data or non-triangular faces.

- **Combined Mesh Option**  
  Future versions might include an option to import all submeshes into one object.
