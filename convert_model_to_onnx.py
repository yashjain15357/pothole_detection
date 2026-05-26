#!/usr/bin/env python
"""
Convert YOLO PyTorch model to ONNX format
Reduces model size from ~300MB to ~50-100MB
Run this script ONCE to create the ONNX model
"""

import os
import sys
from pathlib import Path
from ultralytics import YOLO

def convert_to_onnx():
    """Convert best.pt to ONNX format"""
    
    print("=" * 60)
    print("YOLO Model Conversion to ONNX")
    print("=" * 60)
    
    # Check which model file exists
    model_path = None
    if os.path.exists('best.pt'):
        model_path = 'best.pt'
    elif os.path.exists('best(2).pt'):
        model_path = 'best(2).pt'
    else:
        print("❌ Error: No model file found (best.pt or best(2).pt)")
        return False
    
    print(f"\n📦 Found model: {model_path}")
    
    # Check file size before conversion
    model_size = os.path.getsize(model_path) / (1024 * 1024)
    print(f"📊 Original size: {model_size:.2f} MB")
    
    try:
        print("\n⏳ Loading model...")
        model = YOLO(model_path)
        
        print("🔄 Converting to ONNX format (this may take 1-2 minutes)...")
        
        # Export to ONNX with optimizations
        onnx_path = model.export(
            format='onnx',
            imgsz=416,  # Match inference size
            half=True,  # Use FP16 for smaller size
            optimize=True,  # Optimize for inference
            dynamic=False  # Fixed input size for better performance
        )
        
        print(f"\n✅ Conversion successful!")
        print(f"📁 ONNX model saved to: {onnx_path}")
        
        # Check new file size
        onnx_size = os.path.getsize(onnx_path) / (1024 * 1024)
        print(f"📊 ONNX size: {onnx_size:.2f} MB")
        print(f"💾 Size reduction: {(1 - onnx_size/model_size)*100:.1f}%")
        
        print("\n" + "=" * 60)
        print("✨ Conversion Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. The ONNX model is ready to use")
        print("2. app.py will automatically use it for faster, lighter inference")
        print(f"3. You can optionally delete original {model_path} to save space")
        print("\n")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during conversion: {e}")
        return False

if __name__ == "__main__":
    success = convert_to_onnx()
    sys.exit(0 if success else 1)
