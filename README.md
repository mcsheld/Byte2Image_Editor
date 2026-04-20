**Languages:** [🇬🇧](./README.md) | [🇷🇺](./README_RU.md)

# Byte2Image Editor

**A visual editor for creating and editing binary images from HEX data in the format used by monochrome instrument cluster displays in Kia and Hyundai vehicles.**

![Main screen](https://github.com/mcsheld/Byte2Image_Editor/blob/main/image/byte2image_main.jpg?raw=true)

## 📖 About the Project

This application allows you to work with images represented as HEX strings using a multi-layer system. It is suitable for working with graphics for microcontrollers, OLED displays, DIY projects, and any tasks where an image is stored as a byte array.

![Byte code format](https://github.com/mcsheld/Byte2Image_Editor/blob/main/image/format_byte_code.jpg?raw=true)

### Key Features

| Function | Description |
|---------|-------------|
| 🖼️ **Multi-layer** | Create, delete, rename, and reorder layers |
| ✏️ **Drawing** | Pixel-by-pixel image editing |
| 🖱️ **Movement** | Drag-and-drop or keyboard arrows (←→↑↓) |
| 🔄 **Pixel Shift** | Batch offset of layer content |
| 📂 **Image Import** | PNG, JPEG, BMP with threshold and inversion settings |
| ↩️ **Undo/Redo** | Undo and redo actions (up to 50 steps) |
| 💾 **HEX Editor** | Header highlighting, copy/paste |
| 🔍 **Zoom** | From 5x to 30x |
| 📁 **Save Projects** | JSON format with all layers |
| 📤 **Export** | Save as PNG, JPEG, BMP |

### DENSO Data Format

The editor supports the specific data format used in DENSO monochrome instrument cluster displays:

- **4 header bytes:** `X_start`, `Y_block_start`, `X_end`, `Y_block_end`
- **Byte array:** Each bit = one pixel (1 — black, 0 — white)
- **Data organization:** Line by line, in blocks of 8 vertical pixels

## 🚀 Quick Start

### 📦 Installation

### System Requirements

- **Python** 3.7 or higher
- **pip** (Python package manager)

### Quick Installation

1. **Clone the repository**

```bash
git clone https://github.com/mcsheld/Byte2Image_Editor.git
cd Byte2Image_Editor
```

2. **Install dependencies**

``` bash
pip install numpy pillow
```

3. **Run the program**
``` bash
python Byte2Image_Editor.py
```
