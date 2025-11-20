# Region 坐标系统说明

## 坐标系统

### 默认：left-bottom（左下角原点）

```
(0,1) ─────────────── (1,1)
  │                     │
  │                     │
  │    ┌─────────┐     │  ← top=0.7
  │    │  区域   │     │
  │    └─────────┘     │  ← bottom=0.3
  │                     │
(0,0) ─────────────── (1,0)
     left=0.2    right=0.8
```

**特点**：
- Y轴向上增长（类似数学坐标系）
- 0.0 = 底部，1.0 = 顶部
- top > bottom（正常数学逻辑）

### 可选：left-top（左上角原点）

```
(0,0) ─────────────── (1,0)
  │                     │  ← top=0.3
  │    ┌─────────┐     │
  │    │  区域   │     │
  │    └─────────┘     │  ← bottom=0.7
  │                     │
(0,1) ─────────────── (1,1)
     left=0.2    right=0.8
```

**特点**：
- Y轴向下增长（类似图像坐标系）
- 0.0 = 顶部，1.0 = 底部
- top < bottom（图像逻辑）

## 使用示例

### 示例1：擦除画面中央区域（默认left-bottom）

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.25 0.75 0.75 0.25
  #        ↑    ↑    ↑    ↑
  #        左   上   右   下
  #      (距离底部25%到75%，水平25%到75%)
```

### 示例2：擦除顶部字幕区域（默认left-bottom）

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.0 1.0 1.0 0.85
  #        ↑   ↑   ↑   ↑
  #        左  上  右  下
  #      (距离底部85%-100%，即顶部15%)
```

### 示例3：擦除底部字幕区域（默认left-bottom）

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.0 0.15 1.0 0.0
  #        ↑   ↑    ↑   ↑
  #        左  上   右  下
  #      (距离底部0%-15%，即底部15%)
```

### 示例4：多个区域

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.0 1.0 1.0 0.85 \    # 顶部字幕
  --region 0.0 0.15 1.0 0.0       # 底部字幕
```

### 示例5：使用left-top坐标系

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.0 0.0 1.0 0.15 \    # 顶部字幕
  --region_origin left-top
  #        ↑   ↑   ↑   ↑
  #        左  上  右  下
  #      (距离顶部0%-15%)
```

### 示例6：从JSON文件读取

**regions.json**:
```json
[
  [0.1, 0.9, 0.5, 0.5],
  [0.5, 0.5, 0.9, 0.1]
]
```

```bash
python inference_propainter.py \
  -i video.mp4 \
  --region_json regions.json
```

## 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `--region LEFT TOP RIGHT BOTTOM` | 4个浮点数 | 定义一个区域，可重复 |
| `--region_json FILE` | 文件路径 | 从JSON读取多个区域 |
| `--region_origin` | left-bottom/left-top | 坐标系统（默认left-bottom） |
| `--mask_output FILE` | 文件路径 | 保存生成的mask图片 |

## 坐标范围

- 所有坐标值范围：**0.0 ~ 1.0**（归一化坐标）
- 0.0 = 0%，1.0 = 100%
- 例如：0.5 = 50%

## 验证规则

### left-bottom模式（默认）
- ✅ `left < right`
- ✅ `top > bottom`
- ✅ 示例：`0.1 0.9 0.9 0.1` ✓

### left-top模式
- ✅ `left < right`
- ✅ `top < bottom`
- ✅ 示例：`0.1 0.1 0.9 0.9` ✓

## 常见场景

### 擦除视频logo（右上角）
```bash
# left-bottom模式
--region 0.8 1.0 1.0 0.9

# left-top模式
--region 0.8 0.0 1.0 0.1 --region_origin left-top
```

### 擦除水印（右下角）
```bash
# left-bottom模式
--region 0.8 0.1 1.0 0.0

# left-top模式
--region 0.8 0.9 1.0 1.0 --region_origin left-top
```

### 擦除人物（中央）
```bash
# left-bottom模式
--region 0.3 0.7 0.7 0.3
```

## 调试技巧

### 保存mask查看效果
```bash
python inference_propainter.py \
  -i video.mp4 \
  --region 0.1 0.9 0.9 0.1 \
  --mask_output debug_mask.png \
  --keep_auto_mask
```

然后用图片查看器打开 `debug_mask.png` 确认区域是否正确。

## 总结

- **默认坐标系**：left-bottom（数学坐标系，Y向上）
- **参数顺序**：左 上 右 下
- **坐标范围**：0.0-1.0（百分比）
- **推荐**：使用默认的left-bottom，更符合直觉（上面的值比下面大）
