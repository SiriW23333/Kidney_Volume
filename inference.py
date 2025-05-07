# 推理函数输入为dicom转化而来的png序列（不需要像训练时的格式，只需要普通的包含图像序列的文件夹即可）
# 输出为模型直接推理得到的结果和转化为RGB以后的结果，分别是Output和Output_color，后面一个目录就和whole_data中一致了
# 
# 函数主体包括下面几个部分：
# 1 将png图像中的32位图像转化为24位，因为训练的时候采用的是24位，需要统一，不然会报错
# 2 在png文件的名字最后加上"_0000"，也是模型输入要求
# 3 运行命令行进行推理，在这里如果报错就是环境没有换成kidney_volume，换上以后就行了
# 4 最后再将推理结果转化为彩色图像，这里就是一个映射

import os
import subprocess
from PIL import Image
import numpy as np
from DICOM2PNG import DICOM2PNG  

# 标签颜色映射，用于将灰度标签转换为彩色
LABEL_COLORS = {
    0: (0, 0, 0),       # 背景 - 黑色
    1: (0, 0, 255),     # 右肾 - 蓝色
    2: (0, 255, 255),   # 左肾 - 青色
}

def convert_to_rgb(input_dir):
    """
    将 input_dir 中所有 32 位 RGBA PNG 图像转换为 24 位 RGB，直接覆盖原文件
    """
    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith('.png'):
            continue
        path = os.path.join(input_dir, filename)
        try:
            img = Image.open(path)
        except Exception as e:
            print(f"跳过无法打开的文件: {filename} ({e})")
            continue
        if img.mode == 'RGBA':
            rgb = img.convert('RGB')
            rgb.save(path)
            print(f"已转换为 RGB: {filename}")

def add_suffix_to_filenames(input_dir, suffix='_0000'):
    """
    在 input_dir 中的每个 PNG 文件名末尾添加指定"_0000"后缀
    """
    for filename in sorted(os.listdir(input_dir)):
        if not filename.lower().endswith('.png'):
            continue
        base, ext = os.path.splitext(filename)
        # 如果已经添加过后缀，则跳过
        if base.endswith(suffix):
            continue
        new_name = f"{base}{suffix}{ext}"
        src = os.path.join(input_dir, filename)
        dst = os.path.join(input_dir, new_name)
        os.rename(src, dst)
        print(f"重命名: {filename} -> {new_name}")


def predict_with_nnunet(input_dir, output_dir):
    """
    使用 nnUNetv2_predict 命令行工具进行推理。
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 推理命令也不太复杂，只需要-d表示之前训练时的110的数据，这里的意思就是直接用当时训练好的模型进行推理，不需要过多修改
    cmd = [
        'nnUNetv2_predict',
        '-d', '110',
        '-i', input_dir,
        '-o', output_dir,
        '-f', '5',
        '-t', 'nnUNetTrainer',
        '-c', '2d'
    ]
    print("运行命令: " + ' '.join(cmd))
    subprocess.run(cmd, check=True)
    print("推理完成，结果保存在: {}".format(output_dir))


def label_to_color(label_slice):
    """
    将单通道标签图像转换为 RGB 彩色图像。
    """
    h, w = label_slice.shape
    color_img = np.zeros((h, w, 3), dtype=np.uint8)
    for label_val, color in LABEL_COLORS.items():
        color_img[label_slice == label_val] = color
    return color_img


def convert_gray_mask_folder_to_color(input_folder):
    """
    将灰度掩膜 PNG 序列批量转换为彩色，并覆盖原来的文件
    """
    for filename in sorted(os.listdir(input_folder)):
        if not filename.lower().endswith('.png'):
            continue
        gray_path = os.path.join(input_folder, filename)
        try:
            gray = np.array(Image.open(gray_path))
        except Exception as e:
            print(f"跳过无法打开的文件: {filename} ({e})")
            continue
        color = label_to_color(gray)
        Image.fromarray(color).save(gray_path)
        print(f"已覆盖彩色掩膜: {gray_path}")
    print(f"灰度掩膜序列已转换为彩色，并覆盖原来的文件")


def inference(zip_dir, png_dir,temp_dir):
    """
    完整推理流程：
      1. 检查并转换输入目录下的 PNG 为 24 位 RGB。  
      2. 在文件名末尾添加 _0000 后缀。  
      3. 使用 nnUNetv2_predict 进行推理，结果保存在 output_dir。  
      4. 将输出灰度掩膜序列转换为彩色，保存在 output_dir + '_color' 目录。

    参数:
      input_dir: 包含一系列 PNG 图像的文件夹路径（原始）。
      output_dir: nnUNet 推理结果输出文件夹路径（灰度掩膜）。
    """
    

    DICOM2PNG(zip_dir, temp_dir)  # 将 DICOM 转换为 PNG
    # 1. 转换为 RGB
    print("步骤1：检查并转换为 RGB...")
    convert_to_rgb(temp_dir)
    # 2. 添加后缀
    print("步骤2：添加文件名后缀...")
    add_suffix_to_filenames(temp_dir)
    # 3. 推理
    print("步骤3：运行 nnUNetv2 推理...")
    predict_with_nnunet(temp_dir, png_dir)
    # 4. 灰度转彩色
    print("步骤4：将灰度掩膜转换为彩色...")
    convert_gray_mask_folder_to_color(png_dir)
    print("全部流程完成！")
    return png_dir

