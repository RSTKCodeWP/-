# 🎮 Exporters Guide - TerraForge Studio v4.x

Руководство по экспорту террейнов в различные игровые движки.

---

## 🎯 Поддерживаемые форматы

### **1. Godot Engine 4.x** 🦎

**Формат**: `.tres` (Text Resource) или `.res` (Binary Resource)  
**Что экспортируется**: HeightMapShape3D, ArrayMesh, Materials

#### Настройки:
- **Mesh Subdivision**: 32-512 вершин (рекомендуется 128)
- **Height Scale**: 0.1-10.0 (множитель высоты)
- **Generate Collision**: HeightMapShape3D для физики
- **Include Materials**: Автоматические материалы с текстурами

#### Импорт в Godot:
```gdscript
# 1. Скопируйте .tres файл в ваш проект
# 2. Создайте MeshInstance3D
# 3. Присвойте импортированный terrain как mesh

var terrain = preload("res://terrain.tres")
$MeshInstance3D.mesh = terrain
```

---

### **2. Unity Engine** 🎮

**Формат**: `.raw` (RAW Heightmap)  
**Что экспортируется**: 16-bit или 8-bit heightmap

#### Настройки:
- **Resolution**: 257, 513, 1025, 2049 (2^n + 1)
- **Height Scale**: 1-10000m
- **Bit Depth**: 8-bit или 16-bit
- **Byte Order**: Windows (Little Endian) / Mac (Big Endian)

#### Импорт в Unity:
```csharp
// 1. Window → Terrain → Create Terrain
// 2. Terrain Settings → Import Raw
// 3. Выберите .raw файл
// 4. Настройте:
//    - Depth: Bit (8 или 16)
//    - Resolution: 513 x 513 (или ваш размер)
//    - Byte Order: Windows
//    - Terrain Height: 600 (или ваш Height Scale)
```

---

### **3. Unreal Engine 5** 🔷

**Формат**: `.png` (16-bit Grayscale PNG)  
**Что экспортируется**: Heightmap + Metadata JSON

#### Настройки:
- **Resolution**: 1009, 2017, 4033, 8129
- **Components**: 4x4, 8x8, 16x16
- **Z Scale**: 1-1000 cm
- **World Partition**: UE5 streaming
- **Nanite LODs**: Для высокой детализации

#### Импорт в UE5:
```
1. Landscape Mode → Import from File
2. Выберите .png heightmap
3. Настройте:
   - Section Size: 63x63 quads
   - Sections Per Component: 1x1
   - Number of Components: 8x8
   - Overall Resolution: 2017x2017
   - Z Scale: 100.0
4. Нажмите Import
```

---

## 🔧 Использование Exporter Registry

```typescript
import { exporterRegistry } from '@/exporters/ExporterRegistry';

// Получить все экспортеры
const allExporters = exporterRegistry.getAll();

// Получить экспортеры по категории
const gameEngines = exporterRegistry.getByCategory('game-engine');

// Получить конкретный экспортер
const godotConfig = exporterRegistry.get('godot');

// Проверить поддержку
if (exporterRegistry.isSupported('unity')) {
  // Export...
}
```

---

## 📝 Создание кастомного экспортера

```typescript
import type { CustomExporter } from '@/types/exporter';

const myExporter: CustomExporter = {
  id: 'my-custom-exporter',
  name: 'My Game Engine',
  description: 'Export for my custom engine',
  author: 'Your Name',
  version: '1.0.0',
  category: 'game-engine',
  
  config: {
    format: 'custom',
    // ... exporter config
  },
  
  async execute(request) {
    // Your export logic
    return {
      id: `custom-${Date.now()}`,
      format: 'custom',
      status: 'completed',
      // ...
    };
  },
  
  validate(request) {
    // Validation logic
    return true;
  },
};

// Зарегистрировать
exporterRegistry.registerCustom(myExporter);
```

---

## 🎨 Форматы файлов

### Godot `.tres`:
```
[gd_resource type="ArrayMesh" format=3]
[resource]
_surfaces = [{...}]
```

### Unity `.raw`:
- Binary heightmap
- Little/Big Endian
- 8 или 16 бит на пиксель

### Unreal `.png`:
- 16-bit grayscale PNG
- + JSON metadata file

---

## 📊 Сравнение форматов

| Движок | Формат | Размер | Качество | Сложность |
|--------|--------|---------|----------|-----------|
| Godot | .tres | Средний | Хороший | Низкая |
| Unity | .raw | Малый | Отличный | Средняя |
| Unreal | .png | Средний | Отличный | Высокая |

---

**Создано**: 22 октября 2025  
**Версия**: 1.0.0
