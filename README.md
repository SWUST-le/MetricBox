# MetricBox · 深度学习指标工具箱

一个可以继续扩展的中文桌面脚本管理框架。使用 Python 标准库和 Tkinter，无需安装第三方界面依赖。
内置指标计算使用可选的 NumPy、Pillow，Excel 导出使用 openpyxl；脚本管理功能仍无需这些依赖。

## 启动

需要 Python 3.10 或以上，且包含 Tkinter（常见 Windows Python / Anaconda 安装自带）。

在本目录运行：

```powershell
python main.py
```

Windows 也可以双击 `start.bat`。如果希望使用指定环境启动工具箱：

```powershell
& "C:\path\to\python.exe" ".\main.py"
```

## 已有功能

- 中文桌面界面：分类导航、脚本列表、详情、运行日志。
- 在界面点击“添加已有脚本”，使用系统文件选择器选择文件，也可直接输入路径。
- 编辑脚本名称、分类、说明、指标标签；新分类可直接输入。
- 按名称、说明、分类、标签和路径搜索；刷新文件可访问状态。
- 自动保存脚本配置，重启后恢复；防止重复登记同一个文件。
- 为每个脚本单独指定 Python 解释器、工作目录和命令行参数。
- Python 脚本在独立进程中运行；异步显示标准输出、错误输出与退出码，可停止、保存日志。
- 移除记录时保留原始脚本文件。
- 点击“添加常用指标”导入四组内置计算脚本，重复添加不会覆盖已有配置。

## 常用指标

### 在界面中选择图像直接计算

下方新增 **图像输入与计算** 页签，无需先添加脚本或手写命令行参数：

1. 在“计算指标”中选择图像质量、二值分割或融合统计。
2. 在“原始图像 / 参考图”填入绝对路径，或点击 **图片… / 目录…** 选择输入。
3. 在“处理后图像”选择待评估图像或目录。原图作为 `target`，处理图作为 `pred`。
4. 在“输出格式”选择 `xlsx`（默认）或 `json`。可选填结果文件位置；留空会自动保存到脚本库旁的 `data/results/`（自定义数据目录则随之改变）。
5. 点击 **开始计算**，完成后自动切换到 **计算结果** 页签，显示平均值、逐图详情和保存路径。
   **运行日志** 页签保留计算命令、错误信息和退出码；计算中可以停止。

两边必须同时是单张图片或同时是目录。目录按相对路径和完整文件名严格配对，尺寸需一致；
原始输入应是有效参考图，普通原始图像不一定是处理任务的理想真值。
二值分割须选择真值与预测掩膜；0/1 掩膜设置阈值 `0.5`，0/255 掩膜默认 `127`。
融合统计仅使用“处理后图像”，原始图像栏会禁用。分类任务仍从脚本库使用 JSON 标签输入。

该入口只对所选真实路径执行计算，不使用 `--demo`，不会改动输入图像，也不改变脚本库中保存的参数。
如果已登记同类内置脚本，则复用其 Python 解释器和工作目录；未登记时使用当前 Python 环境。
结果文件名留空时每次生成唯一名称；手动指定时须是尚不存在的 `.xlsx` 或 `.json` 文件，避免覆盖历史结果。
文件扩展名决定最终格式，选择 Excel 时还会保存同名 JSON，供界面读取和复现；两个文件均不会覆盖已有文件。

### Excel 输出

更新后请在运行指标所使用的 Python 环境执行 `python -m pip install -r requirements-metrics.txt`，
安装新增的 `openpyxl>=3.1` 依赖。仅导出 JSON 时不需要导入 openpyxl。

- 图像质量、分割和融合：Excel 包含 **汇总**、**逐图明细** 两张工作表。
- 分类：Excel 包含 **汇总**、**逐类指标**、**混淆矩阵**，矩阵行为真值、列为预测。
- 汇总同时保留任务类型、演示标记、输入路径和计算参数；图像汇总仍是逐图等权平均。
- 数字保留为数值类型，显示六位小数；底层保留原始计算精度。无穷大保留为文本 `Infinity`。
- 明细支持筛选与冻结表头。文件名、类别标签始终按文本写入，不会被解释为 Excel 公式。
- 工作簿为本次计算的静态结果，不会根据修改后的单元格重新计算图像指标。

命令行直接导出 Excel：

```powershell
python builtin_scripts/quality.py --pred E:/results --target E:/ground_truth --output E:/reports/quality.xlsx
```

同时保留两种格式（也适用于其他三组内置脚本）：

```powershell
python builtin_scripts/quality.py --pred E:/results --target E:/ground_truth --output E:/reports/quality.json --xlsx E:/reports/quality.xlsx
```
界面在较小窗口中可使用右侧滚动条查看全部图像输入选项。

### 脚本库与命令行方式

启动后点击搜索框旁的 **添加常用指标**，即可导入下表中的四组脚本。
选中后点击 **运行脚本** 可先体验演示；**初始参数 `["--demo"]` 仅使用演示数据，不是你的数据评估结果**。
评估真实数据时，点击 **编辑**，将参数数组完整替换为对应示例。
已有脚本、解释器和自定义参数不会被覆盖；从列表移除后可以再次添加。

| 分类 | 指标 | 输入 |
| --- | --- | --- |
| 图像质量 | MAE、MSE、RMSE、PSNR、SSIM | 预测图与参考图，或配对目录 |
| 二值分割 | 前景 IoU、Dice、Precision、Recall、F1、Specificity、Accuracy；TP/FP/FN/TN | 预测与真值灰度掩膜，或配对目录 |
| 单标签分类 | Accuracy、逐类 Precision/Recall/F1、macro/micro/weighted、混淆矩阵 | 两份 JSON 标签列表 |
| 融合图像统计 | EN（信息熵）、SD（标准差）、SF（空间频率） | 8 位灰度融合图，或图像目录 |

在运行脚本所选的 Python 环境中安装可选依赖（当前开发环境已具备）：

```powershell
python -m pip install -r requirements-metrics.txt
```

图像质量参数（文件或目录均可）：

```json
["--pred", "E:/results", "--target", "E:/ground_truth", "--output", "E:/reports/quality.json"]
```

二值分割参数，0/255 掩膜默认阈值为 127；**0/1 掩膜必须改用 0.5**：

```json
["--pred", "E:/pred_masks", "--target", "E:/true_masks", "--threshold", "0.5", "--output", "E:/reports/segmentation.json"]
```

分类参数，两份文件内容分别为 JSON 列表，例如 `[0, 1, 2, 1]`，也支持全字符串标签：

```json
["--pred", "E:/pred.json", "--target", "E:/target.json", "--output", "E:/reports/classification.json"]
```

融合图像参数（只需融合结果图，无需源图）：

```json
["--image", "E:/fused_images", "--output", "E:/reports/fusion.json"]
```

也可以直接运行，如 `python builtin_scripts/quality.py --demo`。
计算函数位于 `metricbox/metrics/core.py`，公共命令行入口位于 `metricbox/metrics/cli.py`，
目录与说明位于 `metricbox/builtin_catalog.py`；新增计算脚本后在目录中增加一条定义即可接入界面。

### 输入与计算约定

- 图像支持 PNG/JPEG/BMP/TIFF；仅接受 8 位 `L` 或 `RGB` 模式，不隐式转换调色板、RGBA 或高位深图像。
  分割和融合要求 `L` 灰度输入。不会调整图像尺寸、做配准、归一化或裁剪。
- 单文件可使用不同文件名；目录递归扫描，按相同的**相对路径和完整文件名（含扩展名）**严格配对。
  缺失、错配、空目录、尺寸或通道不一致均会报错，不会静默跳过。
- 质量指标默认动态范围为 255，可使用 `--data-range` 显式指定。SSIM 使用 11×11 高斯窗口、
  sigma=1.5、K1=0.01、K2=0.03、总体协方差，仅对有效窗口求均值，不自动降采样；RGB 分通道计算后平均。
  图像高宽至少为 11。相同图像的 PSNR 为正无穷，在标准 JSON 中表示为字符串 `"Infinity"`。
- 分割的预测和真值均按 `像素值 > threshold` 判为前景。没有前景的两张掩膜，IoU 和 Dice 设为 1；
  Precision、Recall、F1、Specificity 的分母为零时设为 0。当前不支持多类 mIoU 或 ignore label。
- 分类只接受同类型的整数或字符串类别标签，不接受概率列表；混淆矩阵行为真值、列为预测。
  类别取预测与真值的并集，零分母置零。macro 为逐类算术平均，weighted 按真值样本数加权，
  单标签 micro 指标与 Accuracy 相同。不是目标检测 mAP/AP 评估器。
- EN 为 256-bin 灰度直方图的 Shannon 熵（log2）；SD 为总体标准差（ddof=0）；
  SF 为横向、纵向有效相邻差分各自均方之和的平方根。它们描述融合图像统计特性，不能单独判断融合优劣。
- 每张图的结果位于 `results`；`mean_per_image` 是各图指标的等权平均，
  **不是**所有像素合并后的全局指标。任一图 PSNR 为无穷时，其均值也为无穷。分割混淆计数逐图保留，不进行均值汇总。
- `--output` 按扩展名保存 UTF-8 JSON 或 Excel，`--xlsx` 可额外导出 Excel；缺省只输出到运行日志。结果路径不得覆盖输入文件。
  真实输入与 `--demo` 不能同时指定，避免误将演示结果当作真实评估。

定义参考：[SSIM 作者说明](https://www.ece.uwaterloo.ca/~z70wang/research/ssim/)、
[分类 F1 与平均方式](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.f1_score.html)。

## 第一次使用

1. 点击右上角 **添加已有脚本** → **选择文件**。
2. 可先选择本项目的 `examples/basic_metrics.py`。
3. 填写名称，例如“基础误差指标”，分类选择“图像质量”，标签填入 `MAE, MSE`。
4. Python 解释器、工作目录留空，参数保持 `[]`，点击 **保存脚本**。
5. 选中该脚本，点击 **运行脚本**，在日志页查看 MAE、MSE 计算结果。
6. 关闭并重新启动，脚本记录仍会保留。

添加你已有的 PyTorch 脚本时，在“Python 解释器”中选择对应 Conda 环境的 `python.exe`。
工具箱本身不需要 PyTorch，但被运行的脚本仍需要其所在环境具备相应依赖。

### 命令行参数

使用 JSON 字符串数组，一项对应一个命令行参数，可以可靠保留 Windows 路径、空格与中文：

```json
["--input", "E:/数据集/测试集", "--batch-size", "8"]
```

示例脚本可以使用：

```json
["--pred", "[0.2, 0.6, 0.8]", "--target", "[0, 0.5, 1]"]
```

建议在 JSON 中使用 `/` 作为路径分隔符。使用反斜杠时需写为 `E:\\dataset`。
参数不会经过 shell 展开，因此 `>`、`&&`、`*` 等被当作普通参数。
默认工作目录为脚本所在目录；依赖项目相对路径的脚本应指定其项目根目录。

## 项目结构与扩展位置

```text
MetricBox/
├─ main.py                  # 启动入口
├─ start.bat                # Windows 启动入口
├─ metricbox/
│  ├─ app.py                # 主窗口、交互与服务协调
│  ├─ config.py             # 数据目录与默认分类
│  ├─ models.py             # ScriptEntry 数据模型
│  ├─ storage.py            # JSON 脚本库，校验与原子写入
│  ├─ runner.py             # 后台运行器、事件队列、执行适配器
│  └─ ui/
│     ├─ theme.py           # 配色与控件样式
│     └─ script_dialog.py   # 脚本添加 / 编辑表单
├─ examples/
│  └─ basic_metrics.py      # 无第三方依赖的可运行示例
└─ tests/                   # 持久化、真实进程、界面流程验证
```

**新增常用指标脚本**：在界面中添加即可，不需要修改工具箱代码。现有脚本无需实现特殊接口。

**新增配置字段**：在 `models.py` 的 `ScriptEntry` 中增加带默认值的字段，
在 `ui/script_dialog.py` 增加输入控件，并在 `app.py` 展示。旧记录缺少新字段时会使用默认值。
旧版本会忽略未识别字段，因此修改数据模型前应备份脚本库，避免降级保存丢失新字段。

**新增脚本语言**：在 `runner.py` 中实现 `build_command(entry) -> list[str]` 的适配器，
并注册到 `ADAPTERS`，例如 `ADAPTERS[".m"] = MatlabAdapter()`。
执行器统一负责工作目录、输出捕获、停止与退出状态，界面无需复制这些逻辑。

**新增结果分析 / 参数表单 / 批量评估**：可在主窗口增加独立页签及对应服务模块。
当前日志保留脚本原始文本，没有预设 PyTorch、图像融合或检测任务专用输入格式。

## 数据与当前边界

- 首次保存时在本项目 `data/scripts.json` 创建脚本库，以 UTF-8 编码保存。
- 只登记原文件绝对路径，不复制、移动、导入或改写脚本。文件被移动后会显示“文件缺失”，可编辑路径。
- 保存使用临时文件替换，读取失败时以只读模式打开，避免覆盖损坏的原始数据。
- 可以通过环境变量 `METRICBOX_DATA_DIR` 指定数据目录，或修改 `config.py`。
- 当前直接运行 `.py` / `.pyw`；其他文件可以登记管理，运行前会提示需要相应适配器。
- 每次运行一个脚本。脚本需要是命令行入口；仅定义函数的模块需要另写入口脚本。
- 当前没有交互式标准输入，运行配置应通过命令行参数传入。
- 界面最多显示最近 5000 行 / 50 万字符，保存日志会保存当前显示内容。
- 点击运行会以当前用户权限执行本地脚本；适合登记你自己管理和信任的代码。
- 当前使用独立进程继承系统环境；选择 Conda 的 `python.exe` 不等于执行 `conda activate`。
  依赖特定激活环境变量的项目，建议先在其 Conda Prompt 中启动工具箱。

## 验证

```powershell
python -m unittest discover -s tests -v
```

测试使用临时目录，不修改真实脚本库。包括真实子进程运行、中文路径 / 参数、失败退出、停止运行，
以及 Tkinter 的添加、编辑、筛选、持久化恢复和日志展示流程。界面测试需要可用的桌面会话。
验证内置指标前需安装 `requirements-metrics.txt`；测试也覆盖已知数值、真实图像/标签输入、目录配对及 JSON/Excel 导出。

快捷键：`Ctrl+N` 添加脚本，`Ctrl+F` 聚焦搜索；编辑窗口内 `Ctrl+Enter` 保存，`Esc` 取消。

## 开源许可

本项目采用 [MIT License](LICENSE)，版权归属为 `Copyright (c) 2026 SWUST-le`。
允许使用、修改、分发和商业使用；分发本项目或其重要部分时，应保留版权声明和完整许可文本。
软件按原样提供，不附带保证。完整条款以仓库根目录的 `LICENSE` 文件为准。

MIT 许可证的采用无需提交审批申请，直接随代码附上标准许可证文本即可。
参考：[MIT 许可证及使用说明](https://choosealicense.com/licenses/mit/)。
未来通过工具箱登记或运行的外部脚本、数据集及模型仍遵循其各自的许可证，不会自动变为 MIT 许可。

