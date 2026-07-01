#!/usr/bin/env python3
"""
Presentation Compressor
=======================
Compresses the presentation file size by resizing and optimizing
its background images to fit under the 5MB limit.
"""

import zipfile
import io
from PIL import Image
import os

def compress_pptx(input_path, output_path):
    print(f"Compressing {input_path}...")
    
    # Read the original file sizes
    orig_size = os.path.getsize(input_path)
    
    with zipfile.ZipFile(input_path, 'r') as yin:
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as yout:
            for item in yin.infolist():
                data = yin.read(item.filename)
                
                # Check if it's one of the large background images
                if item.filename in ('ppt/media/image3.png', 'ppt/media/image2.png'):
                    print(f"  Optimizing {item.filename}...")
                    img = Image.open(io.BytesIO(data))
                    
                    # Resize to standard 720p (perfect balance of quality and size)
                    img_resized = img.resize((1280, 720), Image.Resampling.LANCZOS)
                    
                    # Save with optimization and high compression
                    out_buffer = io.BytesIO()
                    img_resized.save(out_buffer, format="PNG", optimize=True)
                    new_data = out_buffer.getvalue()
                    
                    print(f"    Size reduced from {len(data)/1024/1024:.2f} MB to {len(new_data)/1024/1024:.2f} MB")
                    yout.writestr(item.filename, new_data)
                else:
                    # Copy other files unchanged
                    yout.writestr(item, data)
                    
    new_size = os.path.getsize(output_path)
    print(f"Compression complete. Size reduced from {orig_size/1024/1024:.2f} MB to {new_size/1024/1024:.2f} MB")

if __name__ == "__main__":
    # Compress the output file
    compress_pptx('TalentLens_AI_Pitch_Deck.pptx', 'Compressed_TalentLens_AI_Pitch_Deck.pptx')
    
    # Overwrite the downloads path with the compressed version
    downloads_path = '/Users/aaryankarthik/Downloads/TalentLens_AI_Pitch_Deck.pptx'
    os.replace('Compressed_TalentLens_AI_Pitch_Deck.pptx', downloads_path)
    print(f"Updated presentation in Downloads: {downloads_path}")
    
    # Also overwrite the local repo one for git tracking
    os.replace('TalentLens_AI_Pitch_Deck.pptx', 'temp.pptx')
    compress_pptx('temp.pptx', 'TalentLens_AI_Pitch_Deck.pptx')
    os.remove('temp.pptx')
    print("Updated repository presentation file.")
