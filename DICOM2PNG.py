import zipfile
import pydicom
from pydicom.pixel_data_handlers.util import apply_voi_lut
import shutil
import os
import numpy as np
from PIL import Image

def DICOM2PNG(input_dir, output_dir):
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    decompress_zip(input_dir, temp_dir)

    process_dicom_files(temp_dir, output_dir)

    shutil.rmtree(temp_dir)
    print(f"已清理临时目录: {temp_dir}")


def decompress_zip(input_dir, temp_dir):
    if input_dir.lower().endswith('.zip'):
        with zipfile.ZipFile(input_dir, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        print(f"已解压: {input_dir} 到 {temp_dir}")
    else:
        raise ValueError(f"输入路径不是有效的 .zip 文件: {input_dir}")


def dicom_to_png(dicom_path, output_path):
    """
    将单个DICOM文件转换为PNG图像（转换为三通道图像）。
    """
    try:
        # 读取DICOM文件
        dicom = pydicom.dcmread(dicom_path)
        
        # 获取像素数据并处理为HU值
        data = dicom.pixel_array
        intercept = dicom.RescaleIntercept if hasattr(dicom, 'RescaleIntercept') else 0
        slope = dicom.RescaleSlope if hasattr(dicom, 'RescaleSlope') else 1
        hu_data = data * slope + intercept

        # 归一化到0-255范围
        MIN_BOUND = -120
        MAX_BOUND = 400
        hu_data = (hu_data - MIN_BOUND) / (MAX_BOUND - MIN_BOUND)
        hu_data[hu_data > 1] = 1
        hu_data[hu_data < 0] = 0
        hu_data = (hu_data * 255).astype(np.uint8)

        # 转换为三通道图像
        rgb_data = np.stack([hu_data] * 3, axis=-1)

        # 保存为PNG图像并依次编号
        numbered_name = f"{len(os.listdir(os.path.dirname(output_path))) + 1:04d}.png"
        numbered_path = os.path.join(os.path.dirname(output_path), numbered_name)
        img = Image.fromarray(rgb_data)
        img.save(numbered_path, format="PNG")
        print(f"成功转换: {dicom_path} -> {numbered_path}")
        
    except Exception as e:
        print(f"转换失败: {dicom_path} | 错误: {str(e)}")

def process_dicom_files(input_dir, output_dir):
    dicom_files = []

    # 遍历文件夹，找到所有 DICOM 文件并提取切片坐标
    for root, _, files in os.walk(input_dir):
        for file in files:
            if file.lower().endswith('.dcm'):
                dicom_path = os.path.join(root, file)
                try:
                    dicom = pydicom.dcmread(dicom_path)
                    slice_location = getattr(dicom, 'SliceLocation', None)
                    dicom_files.append((dicom_path, slice_location))
                except Exception as e:
                    print(f"无法读取 DICOM 文件: {dicom_path} | 错误: {str(e)}")
                    # 按切片坐标从大到小排序，None 值放在最后
    
    dicom_files.sort(key=lambda x: (x[1] is None, -x[1] if x[1] is not None else float('-inf')))

    # 转换排序后的 DICOM 文件为 PNG
    for dicom_path, _ in dicom_files:
        png_filename = os.path.splitext(os.path.basename(dicom_path))[0] + '.png'
        png_path = os.path.join(output_dir, png_filename)
        dicom_to_png(dicom_path, png_path)
