import vtk
import numpy as np
from PIL import Image
import os
from vtk.util import numpy_support
from inference import inference
import shutil

# 在文件开头强制设置 QT_API
import os
os.environ["QT_API"] = "pyqt5"  # 关键：确保 VTK 使用 PyQt5 的绑定

class App:
    def __init__(self, zip_path, png_path):
        self.zip_path = zip_path
        self.png_path = png_path  
        self.patient_path = None
        self.first_img = None
        self.width, self.height = None, None
        self.num_slices = None
        self.spacing = (0.7285, 0.7285, 5.0)  # 实际物理间距（x,y,z 单位：mm）

    def Infer(self):
        temp_dir = os.path.join(os.path.dirname(self.zip_path), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            # 执行推理并处理结果
            self.patient_path = inference(self.zip_path, self.png_path, temp_dir)
            self.png_files = sorted([f for f in os.listdir(self.patient_path) if f.endswith(".png")])
            self.first_img = Image.open(os.path.join(self.patient_path, self.png_files[0]))
            self.width, self.height = self.first_img.size
            self.num_slices = len(self.png_files)
        finally:
            # 确保在函数结束时销毁临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"已清理临时目录: {temp_dir}")
            
    def process_mask(self, color):
        

        # 根据颜色生成体积掩膜
        volume = np.zeros((self.height, self.width, self.num_slices), dtype=np.uint8)
        for z, filename in enumerate(self.png_files):
            img_path = os.path.join(self.patient_path, filename)
            img_data = np.array(Image.open(img_path).convert('RGB'))
            # 创建颜色掩膜
            if color == 'blue':
                mask = (img_data[..., 0] == 0) & (img_data[..., 1] == 0) & (img_data[..., 2] == 255)
            elif color == 'cyan':
                mask = (img_data[..., 0] == 0) & (img_data[..., 1] == 255) & (img_data[..., 2] == 255)
            volume[:, :, z] = np.flipud(mask.astype(np.uint8) * 255)
        return volume

    def calculate_volume(self, volume_data):
        voxel_count = np.count_nonzero(volume_data)
        voxel_volume = self.spacing[0] * self.spacing[1] * self.spacing[2]
        return voxel_count * voxel_volume

    def create_3d_model(self, volume_data, color):
        vtk_array = numpy_support.numpy_to_vtk(
            np.transpose(volume_data, (1, 0, 2)).ravel(order='F'),
            deep=True,
            array_type=vtk.VTK_UNSIGNED_CHAR
        )

        vtk_image = vtk.vtkImageData()
        vtk_image.SetDimensions(self.width, self.height, self.num_slices)
        vtk_image.SetSpacing(*self.spacing)  # 设置物理间距（根据实际情况调整）
        vtk_image.GetPointData().SetScalars(vtk_array)

        # Marching Cubes 表面重建
        marching_cubes = vtk.vtkMarchingCubes()
        marching_cubes.SetInputData(vtk_image)
        marching_cubes.SetValue(0, 128)
        marching_cubes.Update()

        # 高斯平滑
        smoother = vtk.vtkSmoothPolyDataFilter()
        smoother.SetInputConnection(marching_cubes.GetOutputPort())
        smoother.SetNumberOfIterations(250)      # 迭代次数
        smoother.SetRelaxationFactor(0.1)       # 松弛因子
        smoother.SetFeatureAngle(60.0)          # 保持特征角度
        smoother.Update()

        return smoother.GetOutput()

    def output_volume(self):
        # 获取 PNG 文件列表
        if not hasattr(self, 'png_files') or not self.png_files:
            print(f"没有找到 PNG 文件: {self.patient_path}")
            return None, None

        try:
            # 生成掩膜体积
            blue_vol = self.process_mask('blue')
            cyan_vol = self.process_mask('cyan')

            # 计算体积（假设青色为左肾，蓝色为右肾）
            left_kidney = self.calculate_volume(cyan_vol)/1000
            right_kidney = self.calculate_volume(blue_vol)/1000
        except Exception as e:
            print(f"处理出错: {str(e)}")
            return None, None

        return left_kidney, right_kidney

    def display_3d_model(self, vtk_widget):
        self.Infer()
        
        """
        在传入的 QVTKRenderWindowInteractor 中显示 3D 渲染效果
        """
        # 获取现有渲染窗口和渲染器
        render_window = vtk_widget.GetRenderWindow()
        renderer = render_window.GetRenderers().GetFirstRenderer()

        if not renderer:
            renderer = vtk.vtkRenderer()
            render_window.AddRenderer(renderer)

        # 创建蓝色肾脏模型
        blue_mask = self.process_mask('blue')
        blue_model = self.create_3d_model(blue_mask, (0, 0, 1))
        blue_mapper = vtk.vtkPolyDataMapper()
        blue_mapper.SetInputData(blue_model)
        blue_actor = vtk.vtkActor()
        blue_actor.SetMapper(blue_mapper)
        blue_actor.GetProperty().SetColor(0, 0, 1)  # 蓝色

        # 创建青色肾脏模型
        cyan_mask = self.process_mask('cyan')
        cyan_model = self.create_3d_model(cyan_mask, (0, 1, 1))
        cyan_mapper = vtk.vtkPolyDataMapper()
        cyan_mapper.SetInputData(cyan_model)
        cyan_actor = vtk.vtkActor()
        cyan_actor.SetMapper(cyan_mapper)
        cyan_actor.GetProperty().SetColor(0, 1, 1)  # 青色

        # 清除旧模型并添加新模型
        renderer.RemoveActor(blue_actor)
        renderer.RemoveActor(cyan_actor)
        renderer.AddActor(blue_actor)
        renderer.AddActor(cyan_actor)
        renderer.SetBackground(0.2, 0.2, 0.2)  # 设置背景颜色

        # 调整相机视角
        renderer.ResetCamera()
        render_window.Render()
