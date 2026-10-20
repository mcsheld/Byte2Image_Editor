import tkinter as tk
from tkinter import ttk, messagebox, filedialog, Menu
import numpy as np
from PIL import Image, ImageTk
import os
import math
import json
import copy

class Layer:
    """Класс для представления слоя изображения"""
    def __init__(self, name="Layer"):
        self.name = name
        self.hex_string = ""
        self.image_data = None
        self.image_params = None
        self.image_array = None
        self.visible = True
        self.opacity = 1.0
        
    def to_dict(self):
        """Конвертирует слой в словарь для сохранения"""
        return {
            'name': self.name,
            'hex_string': self.hex_string,
            'visible': self.visible,
            'opacity': self.opacity
        }
    
    @classmethod
    def from_dict(cls, data):
        """Создает слой из словаря"""
        layer = cls(data['name'])
        layer.hex_string = data['hex_string']
        layer.visible = data.get('visible', True)
        layer.opacity = data.get('opacity', 1.0)
        return layer
    
    def clone(self):
        """Создает глубокую копию слоя"""
        new_layer = Layer(self.name)
        new_layer.hex_string = self.hex_string
        new_layer.visible = self.visible
        new_layer.opacity = self.opacity
        
        if self.image_data is not None:
            new_layer.image_data = self.image_data.copy()
        
        if self.image_params is not None:
            new_layer.image_params = tuple(self.image_params)
        
        if self.image_array is not None:
            new_layer.image_array = self.image_array.copy()
        
        return new_layer
    
    def get_state_dict(self):
        """Получает состояние слоя в виде словаря для undo/redo"""
        return {
            'name': self.name,
            'hex_string': self.hex_string,
            'image_data': self.image_data.copy() if self.image_data is not None else None,
            'image_params': tuple(self.image_params) if self.image_params is not None else None,
            'image_array': self.image_array.copy() if self.image_array is not None else None,
            'visible': self.visible,
            'opacity': self.opacity
        }
    
    def restore_from_state(self, state):
        """Восстанавливает состояние слоя из словаря"""
        self.name = state['name']
        self.hex_string = state['hex_string']
        self.image_data = state['image_data'].copy() if state['image_data'] is not None else None
        self.image_params = tuple(state['image_params']) if state['image_params'] is not None else None
        self.image_array = state['image_array'].copy() if state['image_array'] is not None else None
        self.visible = state['visible']
        self.opacity = state['opacity']

class ImageDisplayApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Byte2Image Editor")
        self.root.geometry("1400x1000")
        
        # Переменные
        self.screen_width = 160
        self.screen_height = 160
        self.scale_factors = [1, 2, 3, 5, 8, 12, 15, 20, 25, 30]
        self.current_scale_index = 3  # По умолчанию 5x (первый элемент)
        self.scale_factor = self.scale_factors[self.current_scale_index]
        
        # Система слоев
        self.layers = []  # Список всех слоев
        self.active_layer_index = -1  # Индекс активного слоя
        self.combined_image = None  # Комбинированное изображение
        
        # Система Undo/Redo
        self.undo_stack = []  # Стек для отмены действий
        self.redo_stack = []  # Стек для повтора действий
        self.max_undo_steps = 50  # Максимальное количество шагов отмены
        self.batch_edit_mode = False  # Режим пакетного редактирования (для группировки действий)
        self.current_batch = []  # Текущий пакет действий
        
        # Drag & Drop для списка слоев
        self._dnd_drag_index = None   # индекс перетаскиваемого слоя
        self._dnd_last_target = None  # последняя подсвеченная цель
        
        # Drag & Drop для перемещения слоя на canvas
        self._canvas_drag_active = False   # идёт ли перетаскивание
        self._canvas_drag_start_x = 0     # координата мыши при начале (canvas px)
        self._canvas_drag_start_y = 0
        self._canvas_drag_orig_params = None  # image_params слоя до начала тащить

        # Флаг активной серии рисования пикселей
        self._pixel_edit_active = False

        # Режим сдвига пикселей внутри слоя
        self.shift_mode = False
        self._shift_start_x = 0
        self._shift_start_y = 0
        self._shift_orig_data = None
        self._shift_applied_dx = 0
        self._shift_applied_dy = 0
        
        # Debounce для undo при зажатых клавишах перемещения
        self._move_undo_timer = None        # ID таймера after()
        self._move_undo_pending_state = None  # состояние ДО начала серии
        self._move_undo_description = None  # описание для undo-записи
        
        # Режимы
        self.edit_mode = False
        self.highlight_on_select = tk.BooleanVar(value=True)
        self.show_layer_borders = tk.BooleanVar(value=True)
        # Видимость панелей (View → Panels). Active Layer Hex скрыта по умолчанию.
        self.show_toolbar = tk.BooleanVar(value=True)
        self.show_layers_panel = tk.BooleanVar(value=True)
        self.show_hex_panel = tk.BooleanVar(value=True)
        self.show_log_panel = tk.BooleanVar(value=True)

        # Цвета для редактирования
        self.edit_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
        self.current_color_index = 0
        
        # Глобальные переменные для хранения данных при парсинге hex
        self.image_params = None
        self.current_image_data = None
        
        # Создаем меню
        self.create_menu()
        
        # Горячие клавиши
        self.root.bind('<Control-n>', lambda e: self.create_new_image())
        self.root.bind('<Delete>', lambda e: self.delete_layer())
        self.root.bind('<Control-s>', lambda e: self.save_project())
        self.root.bind('<Control-o>', lambda e: self.load_project())
        self.root.bind('<Control-h>', lambda e: self.toggle_active_layer_visibility())
        self.root.bind('<Control-plus>', lambda e: self.zoom_in())
        self.root.bind('<Control-minus>', lambda e: self.zoom_out())
        self.root.bind('<Control-equal>', lambda e: self.zoom_in())  # Для клавиатур без отдельного +
        
        # Горячие клавиши для перемещения
        self.root.bind('<Left>', lambda e: self.move_layer_left())
        self.root.bind('<Right>', lambda e: self.move_layer_right())
        self.root.bind('<Up>', lambda e: self.move_layer_up_pos())
        self.root.bind('<Down>', lambda e: self.move_layer_down_pos())
        
        # Горячие клавиши для Undo/Redo
        self.root.bind('<Control-z>', lambda e: self.undo())
        self.root.bind('<Control-y>', lambda e: self.redo())
        self.root.bind('<Control-Z>', lambda e: self.undo())  # Для Shift+Ctrl+Z
        self.root.bind('<Control-Shift-Z>', lambda e: self.redo())  # Для некоторых систем
        
        # Горячая клавиша для ручного обновления
        self.root.bind('<F5>', lambda e: self.manual_update())
        
        self.setup_ui()
    
    # ==================== UNDO/REDO СИСТЕМА ====================
    
    def save_state_for_undo(self, action_description="Edit"):
        """Сохраняет текущее состояние для отмены"""
        if self.batch_edit_mode:
            # В режиме пакетного редактирования сохраняем только в текущий пакет
            if not self.current_batch:
                # Начинаем новый пакет с состоянием всех слоев
                state = {
                    'description': action_description,
                    'layers': [layer.get_state_dict() for layer in self.layers],
                    'active_layer_index': self.active_layer_index,
                    'timestamp': len(self.undo_stack)
                }
                self.current_batch.append(state)
        else:
            # Сохраняем состояние всех слоев
            state = {
                'description': action_description,
                'layers': [layer.get_state_dict() for layer in self.layers],
                'active_layer_index': self.active_layer_index,
                'timestamp': len(self.undo_stack)
            }
            
            # Добавляем в стек отмены
            self.undo_stack.append(state)
            
            # Ограничиваем размер стека
            if len(self.undo_stack) > self.max_undo_steps:
                self.undo_stack.pop(0)
            
            # Очищаем стек повтора при новом действии
            self.redo_stack.clear()
            
            self.update_undo_redo_buttons()
            
            self.log_info(f"Undo point saved: {action_description}")
    
    # ---- Debounce-undo для перемещения клавишами ----

    def save_state_for_undo_move(self, action_description):
        """Сохраняет undo-точку для серий перемещений (зажатая клавиша).
        
        При первом вызове в серии запоминает состояние ДО перемещения.
        Каждый последующий вызов сбрасывает таймер.
        Когда клавиша отпущена и таймер (~400 мс) истекает — в стек
        пишется одна запись, описывающая всю серию.
        """
        DEBOUNCE_MS = 400  # задержка после последнего нажатия

        # Если это первый вызов новой серии — сохраняем состояние ДО
        if self._move_undo_pending_state is None:
            self._move_undo_pending_state = {
                'description': action_description,
                'layers': [layer.get_state_dict() for layer in self.layers],
                'active_layer_index': self.active_layer_index,
                'timestamp': len(self.undo_stack)
            }
            self._move_undo_description = action_description

        # Сбрасываем таймер
        if self._move_undo_timer is not None:
            self.root.after_cancel(self._move_undo_timer)

        self._move_undo_timer = self.root.after(DEBOUNCE_MS, self._flush_move_undo)

    def _flush_move_undo(self):
        """Вызывается таймером: пишет накопленное перемещение в undo-стек."""
        if self._move_undo_pending_state is None:
            return

        state = self._move_undo_pending_state
        self._move_undo_pending_state = None
        self._move_undo_timer = None

        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_redo_buttons()
        self.log_info(f"Undo point saved: {state['description']} (grouped)")

    # ---- Конец debounce-undo ----

    def begin_batch_edit(self, description="Batch Edit"):
        """Начинает пакетное редактирование (группировку действий)"""
        self.batch_edit_mode = True
        self.current_batch = []
        self.save_state_for_undo(description)
    
    def end_batch_edit(self):
        """Заканчивает пакетное редактирование"""
        if self.batch_edit_mode and self.current_batch:
            # Сохраняем последнее состояние как одно действие
            final_state = self.current_batch[-1]
            self.undo_stack.append(final_state)
            
            # Ограничиваем размер стека
            if len(self.undo_stack) > self.max_undo_steps:
                self.undo_stack.pop(0)
            
            # Очищаем стек повтора
            self.redo_stack.clear()
            
            self.update_undo_redo_buttons()
            
            self.log_info(f"Batch edit completed: {final_state['description']}")
        
        self.batch_edit_mode = False
        self.current_batch = []
    
    def undo(self):
        """Отменяет последнее действие"""
        if not self.undo_stack:
            self.set_status("Nothing to undo")
            return
        
        # Получаем последнее состояние из стека отмены
        state = self.undo_stack.pop()
        
        # Сохраняем текущее состояние в стек повтора
        current_state = {
            'description': f"Before undo: {state['description']}",
            'layers': [layer.get_state_dict() for layer in self.layers],
            'active_layer_index': self.active_layer_index,
            'timestamp': len(self.redo_stack)
        }
        self.redo_stack.append(current_state)
        
        # Восстанавливаем предыдущее состояние
        self.restore_state(state)
        
        self.set_status(f"Undo: {state['description']}")
        self.log_info(f"Undo: {state['description']}")
        
        self.update_undo_redo_buttons()
    
    def redo(self):
        """Повторяет отмененное действие"""
        if not self.redo_stack:
            self.set_status("Nothing to redo")
            return
        
        # Получаем последнее состояние из стека повтора
        state = self.redo_stack.pop()
        
        # Сохраняем текущее состояние в стек отмены
        current_state = {
            'description': f"Before redo: {state['description']}",
            'layers': [layer.get_state_dict() for layer in self.layers],
            'active_layer_index': self.active_layer_index,
            'timestamp': len(self.undo_stack)
        }
        self.undo_stack.append(current_state)
        
        # Восстанавливаем состояние
        self.restore_state(state)
        
        self.set_status(f"Redo: {state['description']}")
        self.log_info(f"Redo: {state['description']}")
        
        self.update_undo_redo_buttons()
    
    def restore_state(self, state):
        """Восстанавливает состояние из сохраненного словаря"""
        # Восстанавливаем слои
        new_layers = []
        for layer_state in state['layers']:
            layer = Layer(layer_state['name'])
            layer.restore_from_state(layer_state)
            new_layers.append(layer)
        
        self.layers = new_layers
        self.active_layer_index = state['active_layer_index']
        
        # Обновляем интерфейс
        self.update_layer_list()
        if self.active_layer_index >= 0:
            self.layer_listbox.selection_set(self.active_layer_index)
            self.update_active_layer_display()
        else:
            self.update_active_layer_display()
        
        # Перерисовываем
        self.combine_layers()
    
    def update_undo_redo_buttons(self):
        """Обновляет состояние кнопок и пунктов меню Undo/Redo"""
        has_undo = len(self.undo_stack) > 0
        has_redo = len(self.redo_stack) > 0
        
        # Обновляем меню
        self.undo_menu.entryconfig(0, state=tk.NORMAL if has_undo else tk.DISABLED)
        self.redo_menu.entryconfig(0, state=tk.NORMAL if has_redo else tk.DISABLED)
        
        # Обновляем тулбар если есть кнопки
        if hasattr(self, 'undo_btn'):
            self.undo_btn.config(state=tk.NORMAL if has_undo else tk.DISABLED)
        if hasattr(self, 'redo_btn'):
            self.redo_btn.config(state=tk.NORMAL if has_redo else tk.DISABLED)
    
    def clear_undo_history(self):
        """Очищает историю undo/redo"""
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_redo_buttons()
        self.log_info("Undo history cleared")
    
    def toggle_auto_update(self):
        """Включает/выключает автоматическое обновление"""
        status = "ON" if self.auto_update_var.get() else "OFF"
        self.log_info(f"Auto Update: {status}")
        self.set_status(f"Auto Update: {status}")
        
    def on_mousewheel(self, event):
        """Колесо мыши на корневом окне — оставлено для совместимости."""
        if event.state & 0x4:  # Ctrl зажат
            if event.delta > 0 or event.num == 4:
                self.zoom_in()
            else:
                self.zoom_out()
            return "break"

    def on_canvas_mousewheel(self, event):
        """Колесо мыши на canvas.
        Ctrl+колесо → зум.
        Без Ctrl → вертикальный скролл (Shift+колесо → горизонтальный).
        """
        # Определяем направление
        if event.num == 4:       # Linux вверх
            delta = 1
        elif event.num == 5:     # Linux вниз
            delta = -1
        else:                    # Windows
            delta = 1 if event.delta > 0 else -1

        ctrl  = event.state & 0x4
        shift = event.state & 0x1

        if ctrl:
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return "break"
        elif shift:
            self.canvas.xview_scroll(-delta, "units")
        else:
            self.canvas.yview_scroll(-delta, "units")
        return "break"
        
    def manual_update(self):
        """Ручное обновление отображения после перемещения"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        
        layer = self.layers[self.active_layer_index]
        
        if layer.image_params is not None and layer.image_data is not None:
            # Пересоздаем изображение с текущими параметрами
            self.recreate_layer_image(layer)
            
            self.log_info("Manual update: applied all pending moves")
            self.set_status("All pending moves applied")
            
            # Перерисовываем
            self.combine_layers()
        else:
            self.log_info("No image data to update")
            
    def recreate_layer_image(self, layer):
        """Пересоздает изображение слоя с текущими параметрами и данными"""
        if layer.image_params is None or layer.image_data is None:
            return
        
        x_start, block_start, x_end, block_end = layer.image_params
        
        # Вычисляем размеры
        width = 0 - (x_start - x_end) + 1
        height = (0 - (block_start - block_end) + 1) * 8
        
        # Проверяем корректность данных
        expected_data_size = width * (height // 8)
        if len(layer.image_data) != expected_data_size:
            self.log_info(f"Warning: data size mismatch. Expected {expected_data_size}, got {len(layer.image_data)}")
            # Не прерываем — рисуем столько данных, сколько есть
        
        # Создаем пустое изображение
        new_image = np.ones((self.screen_height, self.screen_width), dtype=np.uint8) * 255
        
        # Восстанавливаем изображение из данных
        data_index = 0
        for block_row in range(height // 8):
            y_block_pos = block_start + block_row
            y_start = y_block_pos * 8
            
            for col in range(width):
                x_pos = x_start + col
                
                if data_index >= len(layer.image_data):
                    break
                
                byte_val = layer.image_data[data_index]
                data_index += 1
                
                for bit in range(8):
                    y_pos = y_start + bit
                    
                    if 0 <= x_pos < self.screen_width and 0 <= y_pos < self.screen_height:
                        if byte_val & (1 << bit):
                            new_image[y_pos, x_pos] = 0  # Черный
        
        # Обновляем массив изображения
        layer.image_array = new_image
        
    def move_layer_left(self):
        """Перемещает активный слой влево"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Warning", "Layer has no image data")
            return
        
        x_start, block_start, x_end, block_end = layer.image_params
        
        # Проверяем, можно ли переместить влево
        if x_start <= 0:
            self.log_info("Cannot move left: already at left edge")
            return
        
        # Сохраняем состояние перед перемещением
        self.save_state_for_undo_move(f"Move {layer.name} left")
        
        # Смещаем параметры
        x_start -= 1
        x_end -= 1
        
        # ВСЕГДА обновляем параметры слоя и hex-строку
        layer.image_params = (x_start, block_start, x_end, block_end)
        self.update_layer_hex_string(layer)
        
        if self.auto_update_var.get():
            # Если Auto Update включен, пересоздаем и перерисовываем изображение
            self.recreate_layer_image(layer)
            self.combine_layers()
            self.set_status(f"Moved layer left")
        else:
            # Если Auto Update выключен, только перерисовываем рамку
            # Но само изображение остается на старом месте
            self.combine_layers()
            self.set_status(f"Preview: moved layer left - press Update to apply image")
        
        self.log_info(f"Moved layer '{layer.name}' left to X={x_start}-{x_end}")
    
    def move_layer_right(self):
        """Перемещает активный слой вправо"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Warning", "Layer has no image data")
            return
        
        x_start, block_start, x_end, block_end = layer.image_params
        
        # Проверяем, можно ли переместить вправо
        if x_end >= self.screen_width - 1:
            self.log_info("Cannot move right: already at right edge")
            return
        
        # Сохраняем состояние перед перемещением
        self.save_state_for_undo_move(f"Move {layer.name} right")
        
        # Смещаем параметры
        x_start += 1
        x_end += 1
        
        # ВСЕГДА обновляем параметры слоя и hex-строку
        layer.image_params = (x_start, block_start, x_end, block_end)
        self.update_layer_hex_string(layer)
        
        if self.auto_update_var.get():
            # Если Auto Update включен, пересоздаем и перерисовываем изображение
            self.recreate_layer_image(layer)
            self.combine_layers()
            self.set_status(f"Moved layer right")
        else:
            # Если Auto Update выключен, только перерисовываем рамку
            self.combine_layers()
            self.set_status(f"Preview: moved layer right - press Update to apply image")
        
        self.log_info(f"Moved layer '{layer.name}' right to X={x_start}-{x_end}")
    
    def move_layer_up_pos(self):
        """Перемещает активный слой вверх"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Warning", "Layer has no image data")
            return
        
        x_start, block_start, x_end, block_end = layer.image_params
        
        # Проверяем, можно ли переместить вверх
        if block_start <= 0:
            self.log_info("Cannot move up: already at top edge")
            return
        
        # Сохраняем состояние перед перемещением
        self.save_state_for_undo_move(f"Move {layer.name} up")
        
        # Смещаем параметры
        block_start -= 1
        block_end -= 1
        
        # ВСЕГДА обновляем параметры слоя и hex-строку
        layer.image_params = (x_start, block_start, x_end, block_end)
        self.update_layer_hex_string(layer)
        
        if self.auto_update_var.get():
            # Если Auto Update включен, пересоздаем и перерисовываем изображение
            self.recreate_layer_image(layer)
            self.combine_layers()
            self.set_status(f"Moved layer up")
        else:
            # Если Auto Update выключен, только перерисовываем рамку
            self.combine_layers()
            self.set_status(f"Preview: moved layer up - press Update to apply image")
        
        self.log_info(f"Moved layer '{layer.name}' up to blocks Y={block_start}-{block_end}")
    
    def move_layer_down_pos(self):
        """Перемещает активный слой вниз"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Warning", "Layer has no image data")
            return
        
        x_start, block_start, x_end, block_end = layer.image_params
        
        # Проверяем, можно ли переместить вниз
        if block_end >= 254:
            self.log_info("Cannot move down: already at bottom edge")
            return
        
        # Сохраняем состояние перед перемещением
        self.save_state_for_undo_move(f"Move {layer.name} down")
        
        # Смещаем параметры
        block_start += 1
        block_end += 1
        
        # ВСЕГДА обновляем параметры слоя и hex-строку
        layer.image_params = (x_start, block_start, x_end, block_end)
        self.update_layer_hex_string(layer)
        
        if self.auto_update_var.get():
            # Если Auto Update включен, пересоздаем и перерисовываем изображение
            self.recreate_layer_image(layer)
            self.combine_layers()
            self.set_status(f"Moved layer down")
        else:
            # Если Auto Update выключен, только перерисовываем рамку
            self.combine_layers()
            self.set_status(f"Preview: moved layer down - press Update to apply image")
        
        self.log_info(f"Moved layer '{layer.name}' down to blocks Y={block_start}-{block_end}")
            
    def show_screen_size_dialog(self):
        """Диалог изменения размера экрана (только квадратные размеры)."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Screen Size")
        dialog.geometry("240x120")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        pad = {'padx': 10, 'pady': 8}

        ttk.Label(dialog, text="Size (pixels):", font=('Arial', 10)).grid(
            row=0, column=0, sticky=tk.W, **pad)
        size_var = tk.IntVar(value=self.screen_width)
        ttk.Spinbox(dialog, from_=8, to=256, increment=8, width=8,
                    textvariable=size_var, font=('Arial', 10)).grid(
            row=0, column=1, sticky=tk.W, **pad)

        def apply():
            s = size_var.get()
            if s < 8:
                messagebox.showwarning("Invalid size", "Minimum size is 8.", parent=dialog)
                return
            if s > 256:
                messagebox.showwarning("Invalid size", "Maximum size is 256.", parent=dialog)
                return
            self.screen_width  = s
            self.screen_height = s
            self.image_container.config(text=f"Display ({s}x{s})")
            self.combine_layers()
            self.log_info(f"Screen size changed to {s}x{s}")
            self.set_status(f"Screen size: {s}x{s}")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=8)
        ttk.Button(btn_frame, text="Apply",  width=10, command=apply).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Cancel", width=10, command=dialog.destroy).pack(side=tk.LEFT, padx=6)

        dialog.bind('<Return>', lambda e: apply())
        dialog.bind('<Escape>', lambda e: dialog.destroy())

    def close_project(self):
        """Закрывает текущий проект и возвращает к начальному состоянию."""
        if self.layers and any(l.hex_string for l in self.layers):
            if not messagebox.askyesno(
                "Close Project",
                "Close the current project? Unsaved changes will be lost."
            ):
                return

        # Сбрасываем слои
        self.layers = []
        self.active_layer_index = -1
        self.combined_image = None

        # Сбрасываем undo/redo
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_redo_buttons()

        # Сбрасываем режим редактирования
        self.edit_mode = False
        self._update_edit_buttons()

        # Очищаем интерфейс
        self.canvas.delete("all")
        self._hex_set('')
        self.clear_info()
        self.update_layer_list()
        self.update_active_layer_display()

        # Добавляем один чистый слой
        self.add_new_layer()

        self.log_info("Project closed. New project started.")
        self.set_status("Ready - New project")

    def create_menu(self):
        """Создает меню приложения"""
        menubar = Menu(self.root)
        self.root.config(menu=menubar)
        
        # Меню File
        file_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open File...", command=self.open_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Load Image...", command=self.load_image_file)
        file_menu.add_command(label="New Image...", command=self.create_new_image, accelerator="Ctrl+N")
        file_menu.add_separator()
        file_menu.add_command(label="Save Project...", command=self.save_project, accelerator="Ctrl+S")
        file_menu.add_command(label="Load Project...", command=self.load_project)
        file_menu.add_command(label="Close Project", command=self.close_project)
        file_menu.add_separator()
        export_menu = Menu(file_menu, tearoff=0)
        export_menu.add_command(label="Image (All Layers)...", command=self.export_to_image)
        export_menu.add_command(label="Layer Image...", command=self.export_layer_image)
        export_menu.add_command(label="Layer Bytes...", command=self.export_layer_bytes)
        export_menu.add_separator()
        export_menu.add_command(label="Firmware Structures...", command=self.show_firmware_export_dialog)
        file_menu.add_cascade(label="Export", menu=export_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        # Меню Edit
        edit_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        
        # Undo/Redo в меню Edit
        self.undo_menu = edit_menu
        edit_menu.add_command(label="Undo", command=self.undo, accelerator="Ctrl+Z")
        self.redo_menu = edit_menu
        edit_menu.add_command(label="Redo", command=self.redo, accelerator="Ctrl+Y")
        edit_menu.add_separator()
        edit_menu.add_command(label="Clear History", command=self.clear_undo_history)
        
        # Меню Layer
        layer_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Layer", menu=layer_menu)
        layer_menu.add_command(label="New Layer", command=self.add_new_layer)
        layer_menu.add_command(label="Delete Layer", command=self.delete_layer, accelerator="Del")
        layer_menu.add_separator()
        layer_menu.add_command(label="Show All Layers", command=self.show_all_layers)
        layer_menu.add_command(label="Hide All Layers", command=self.hide_all_layers)
        layer_menu.add_separator()
        layer_menu.add_command(label="Move Layer Up", command=self.move_layer_up)
        layer_menu.add_command(label="Move Layer Down", command=self.move_layer_down)
        layer_menu.add_separator()
        layer_menu.add_checkbutton(label="Highlight on Select", variable=self.highlight_on_select)
        layer_menu.add_checkbutton(label="Show Layer Borders", variable=self.show_layer_borders,
                                   command=self.combine_layers)
        
        # Меню View
        view_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Zoom In", command=self.zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Out", command=self.zoom_out, accelerator="Ctrl+-")
        view_menu.add_separator()
        panels_menu = Menu(view_menu, tearoff=0)
        panels_menu.add_checkbutton(label="Toolbar", variable=self.show_toolbar,
                                    command=self.apply_panel_visibility)
        panels_menu.add_checkbutton(label="Layers", variable=self.show_layers_panel,
                                    command=self.apply_panel_visibility)
        panels_menu.add_checkbutton(label="Active Layer Hex", variable=self.show_hex_panel,
                                    command=self.apply_panel_visibility)
        panels_menu.add_checkbutton(label="Log", variable=self.show_log_panel,
                                    command=self.apply_panel_visibility)
        view_menu.add_cascade(label="Panels", menu=panels_menu)
        view_menu.add_separator()
        view_menu.add_command(label="Screen Size...", command=self.show_screen_size_dialog)
        
        # Меню Help
        help_menu = Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="Hotkeys...", command=self.show_hotkeys)
        help_menu.add_separator()
        help_menu.add_command(label="About", command=self.show_about)
        
    @staticmethod
    def _set_pane_visible(paned, widget, ordered, weight, visible):
        """Показывает/скрывает дочернюю панель PanedWindow, сохраняя исходный порядок.
        ordered — список всех панелей этого paned в их «естественном» порядке."""
        current = [str(p) for p in paned.panes()]
        shown = str(widget) in current
        if visible and not shown:
            idx = 0
            for w in ordered:
                if w is widget:
                    break
                if str(w) in current:
                    idx += 1
            if idx >= len(current):
                # Tk не позволяет insert с индексом == числу панелей — добавляем в конец
                paned.add(widget, weight=weight)
            else:
                paned.insert(idx, widget, weight=weight)
        elif not visible and shown:
            paned.forget(widget)

    def apply_panel_visibility(self):
        """Применяет состояние View → Panels: Toolbar, Layers, Active Layer Hex, Log."""
        # Тулбар (grid_remove запоминает параметры, grid() возвращает на место)
        if self.show_toolbar.get():
            self.toolbar_frame.grid()
        else:
            self.toolbar_frame.grid_remove()

        main_order = [self.left_frame, self.center_paned, self.right_frame]
        self._set_pane_visible(self.main_paned, self.left_frame, main_order, 1,
                               self.show_layers_panel.get())
        self._set_pane_visible(self.main_paned, self.right_frame, main_order, 1,
                               self.show_log_panel.get())

        self._set_pane_visible(self.center_paned, self.hex_frame,
                               [self.center_top, self.hex_frame], 1,
                               self.show_hex_panel.get())

    def _build_export_menu(self, parent, layer=None):
        """Подменю Export для контекстных меню. layer — слой, к которому относятся
        пункты Layer Image / Layer Bytes (None — пункты отключены)."""
        sub = Menu(parent, tearoff=0)
        has_img = layer is not None and layer.image_params is not None \
            and layer.image_data is not None
        sub.add_command(label="Image (All Layers)...", command=self.export_to_image,
                        state=tk.NORMAL if self.combined_image is not None else tk.DISABLED)
        sub.add_command(label="Layer Image...", command=self.export_layer_image,
                        state=tk.NORMAL if has_img else tk.DISABLED)
        sub.add_command(label="Layer Bytes...", command=self.export_layer_bytes,
                        state=tk.NORMAL if has_img else tk.DISABLED)
        return sub

    # ==================== ЭКСПОРТ В ПРОШИВКУ ====================

    @staticmethod
    def _addr_to_ptr_bytes(addr):
        """24-битный адрес -> 4 байта в обратном порядке: 0xFB0000 -> 00 00 FB 00."""
        return bytes([addr & 0xFF, (addr >> 8) & 0xFF, (addr >> 16) & 0xFF, 0x00])

    @staticmethod
    def _fmt_addr(addr):
        return f"{(addr >> 16) & 0xFF:02X}:{addr & 0xFFFF:04X}"

    @staticmethod
    def _parse_addr(text):
        """Принимает 'FB0000', '0xFB0000' или 'FB:0000'. Возвращает int или None."""
        t = text.strip().replace(':', '').replace(' ', '')
        if t.lower().startswith('0x'):
            t = t[2:]
        if not t:
            return None
        try:
            v = int(t, 16)
        except ValueError:
            raise ValueError(f"Invalid address: '{text}'")
        if not (0 <= v <= 0xFFFFFF):
            raise ValueError("Address must fit in 3 bytes (00:0000 - FF:FFFF)")
        return v

    def build_firmware_blob(self, entries, struct_addr, code_addr=None):
        """Собирает бинарный блок прошивки.
 
        entries — список пар (layer_idx, owner_idx) в порядке экспорта.
            owner_idx == layer_idx  -> слой имеет собственный байт-код;
            owner_idx != layer_idx  -> структура слоя ссылается на байт-код слоя owner_idx
                                       (байт-код пишется один раз).
        Структура (8 байт на слой):
            [4 байта: x_start, block_start, x_end, block_end]
            [4 байта: адрес байт-кода в обратном порядке, старший байт = 00]
        Байт-коды идут после таблицы структур (или с code_addr) в порядке
        первого обращения к ним из таблицы.
        Возвращает (blob, rows), rows: (name, struct_addr, code_addr, size, shared_with_name|None)
        """
        n = len(entries)
        table_size = n * 8
        table_end = struct_addr + table_size
        if code_addr is None:
            code_addr = table_end
        elif code_addr < table_end:
            raise ValueError(
                f"Bytecode address {self._fmt_addr(code_addr)} overlaps the structure table "
                f"(ends at {self._fmt_addr(table_end)})")
 
        table = bytearray()
        code = bytearray()
        rows = []
        code_addrs = {}          # owner_idx -> адрес байт-кода
        cur = code_addr
        for i, (idx, owner) in enumerate(entries):
            layer = self.layers[idx]
            if owner not in code_addrs:
                data = bytes(self.layers[owner].image_data)
                if cur + len(data) > 0x1000000:
                    raise ValueError("Bytecode exceeds the 24-bit address space")
                code_addrs[owner] = cur
                code += data
                cur += len(data)
            addr = code_addrs[owner]
            header = bytes(layer.image_params)          # 4 байта
            table += header + self._addr_to_ptr_bytes(addr)
            shared = self.layers[owner].name if owner != idx else None
            rows.append((layer.name, struct_addr + i * 8, addr,
                         len(self.layers[owner].image_data), shared))
 
        gap = bytes(code_addr - table_end)
        return bytes(table) + gap + bytes(code), rows
 
    def show_firmware_export_dialog(self):
        """Окно экспорта структур картинок и байт-кодов в прошивку.
        Выбор слоёв, их порядок, общий байт-код, горячие клавиши и подсказки."""
        candidates = [i for i, l in enumerate(self.layers)
                      if l.image_params is not None and l.image_data is not None]
        if not candidates:
            messagebox.showwarning("Export", "No layers with images to export")
            return
 
        win = tk.Toplevel(self.root)
        win.title("Export Firmware Structures")
        win.geometry("880x760")
        win.transient(self.root)
        win.grab_set()
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        win.rowconfigure(3, weight=1)
 
        # ---- состояние ----
        order = list(candidates)                         # порядок экспорта
        # по умолчанию отмечены только видимые слои; скрытые можно отметить вручную
        inc = {i: bool(self.layers[i].visible) for i in candidates}
        owner = {i: i for i in candidates}               # чей байт-код использует слой
 
        def lname(i):
            return self.layers[i].name
 
        def normalize():
            """Если владелец байт-кода исключён — передаём владение первому из зависимых."""
            for m in order:
                followers = [i for i in order if i != m and owner[i] == m]
                if followers and not inc[m]:
                    alive = [i for i in followers if inc[i]]
                    new_owner = alive[0] if alive else None
                    for i in followers:
                        owner[i] = new_owner if (new_owner is not None and inc[i]) else i
 
        # ---- всплывающие подсказки ----
        def add_tip(widget, text):
            tip = {'win': None, 'job': None}
 
            def show():
                tip['job'] = None
                if tip['win'] is not None:
                    return
                t = tk.Toplevel(widget)
                t.wm_overrideredirect(True)
                t.wm_geometry(f"+{widget.winfo_rootx() + 12}+{widget.winfo_rooty() + widget.winfo_height() + 4}")
                tk.Label(t, text=text, justify=tk.LEFT, background="#FFFFE0", relief=tk.SOLID,
                         borderwidth=1, wraplength=340, font=('Arial', 9)).pack()
                tip['win'] = t
 
            def hide(_e=None):
                if tip['job'] is not None:
                    widget.after_cancel(tip['job'])
                    tip['job'] = None
                if tip['win'] is not None:
                    tip['win'].destroy()
                    tip['win'] = None
 
            def schedule(_e=None):
                hide()
                tip['job'] = widget.after(450, show)
 
            widget.bind('<Enter>', schedule, add='+')
            widget.bind('<Leave>', hide, add='+')
            widget.bind('<ButtonPress>', hide, add='+')
            widget.bind('<Destroy>', hide, add='+')
 
        # ---- список слоёв ----
        lf = ttk.LabelFrame(win, text="Layers — top to bottom = order of structures in the file", padding=8)
        lf.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 4))
        lf.columnconfigure(0, weight=1)
        lf.rowconfigure(0, weight=1)
 
        cols = ("n", "name", "size", "exp", "code")
        tree = ttk.Treeview(lf, columns=cols, show="headings", selectmode="browse", height=9)
        for c, t, w, a in (("n", "#", 36, "center"), ("name", "Layer", 190, "w"),
                           ("size", "Size", 120, "w"), ("exp", "Export", 55, "center"),
                           ("code", "Bytecode source", 220, "w")):
            tree.heading(c, text=t)
            tree.column(c, width=w, anchor=a, stretch=(c in ("name", "code")))
        tree.grid(row=0, column=0, sticky="nsew")
        tsb = ttk.Scrollbar(lf, orient=tk.VERTICAL, command=tree.yview)
        tsb.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=tsb.set)
        tree.tag_configure("off", foreground="gray")
        tree.tag_configure("shared", foreground="#1a5fb4")
        add_tip(tree, "Layer list. ↑/↓ — move the cursor, Space — include/exclude the layer.\n"
                      "Grey = not exported. Blue = uses another layer's bytecode.\n"
                      "Hotkeys work while this list has focus.")
 
        ttk.Label(lf, foreground="gray", justify=tk.LEFT,
                  text="Space — include/exclude   Ctrl+↑/↓ — move layer   Ctrl+Home/End — to top/bottom\n"
                       "S — use another layer's bytecode   U — make bytecode separate   A — auto-find duplicates\n"
                       "Ctrl+A / Ctrl+D — include / exclude all   Ctrl+S — save .bin   Ctrl+Shift+C — copy hex"
                  ).grid(row=1, column=0, columnspan=3, sticky="w", pady=(6, 0))
 
        # ---- действия ----
        def selected():
            sel = tree.selection()
            return int(sel[0]) if sel else None
 
        def in_entry():
            return isinstance(win.focus_get(), (tk.Entry, ttk.Entry))
 
        def move(delta):
            i = selected()
            if i is None:
                return
            p = order.index(i)
            q = p + delta
            if 0 <= q < len(order):
                order[p], order[q] = order[q], order[p]
                refresh(keep=i)
 
        def move_edge(to_top):
            i = selected()
            if i is None:
                return
            order.remove(i)
            if to_top:
                order.insert(0, i)
            else:
                order.append(i)
            refresh(keep=i)
 
        def toggle_export(_e=None):
            i = selected()
            if i is None:
                return
            inc[i] = not inc[i]
            if not inc[i]:
                owner[i] = i
            refresh(keep=i)
 
        def share_candidates(i):
            data = bytes(self.layers[i].image_data)
            return [j for j in order if j != i and inc[j] and owner[j] == j
                    and bytes(self.layers[j].image_data) == data]
 
        def set_owner(i, j):
            for k in order:                      # зависимые от i переезжают к j
                if k != i and owner[k] == i:
                    owner[k] = j
            owner[i] = j
            refresh(keep=i)
 
        def share_menu():
            i = selected()
            if i is None:
                return
            if not inc[i]:
                messagebox.showinfo("Use same bytecode",
                                    "This layer is not marked for export.\n"
                                    "Include it first (Space).", parent=win)
                return
            cands = share_candidates(i)
            if not cands:
                messagebox.showinfo(
                    "Use same bytecode",
                    "No other exported layer has identical image data,\n"
                    "so there is nothing to share with.", parent=win)
                return
            m = tk.Menu(win, tearoff=0)
            m.add_command(label=f"'{lname(i)}' should use the bytecode of:", state=tk.DISABLED)
            m.add_separator()
            for j in cands:
                m.add_command(label=f"   {lname(j)}", command=lambda j=j: set_owner(i, j))
            bb = tree.bbox(str(i))
            if bb:
                x = tree.winfo_rootx() + bb[0] + 60
                y = tree.winfo_rooty() + bb[1] + bb[3]
            else:
                x, y = win.winfo_pointerx(), win.winfo_pointery()
            try:
                m.tk_popup(x, y)
            finally:
                m.grab_release()
 
        def unshare(_e=None):
            i = selected()
            if i is None:
                return
            if owner[i] == i:
                # слой — владелец: все, кто на него ссылался, снова получают свой байт-код
                for k in order:
                    if k != i and owner[k] == i:
                        owner[k] = k
            else:
                owner[i] = i
            refresh(keep=i)
 
        def auto_share():
            """Слои с одинаковыми данными -> общий байт-код (владелец — первый по порядку)."""
            groups = {}
            for i in order:
                if inc[i]:
                    groups.setdefault(bytes(self.layers[i].image_data), []).append(i)
            for g in groups.values():
                for i in g:
                    owner[i] = g[0]
            refresh()
 
        def unshare_all():
            for i in order:
                owner[i] = i
            refresh()
 
        def set_all(v):
            for i in order:
                inc[i] = v
            if not v:
                for i in order:
                    owner[i] = i
            refresh()
 
        # ---- боковая панель кнопок ----
        side = ttk.Frame(lf)
        side.grid(row=0, column=2, sticky="n", padx=(10, 0))
 
        def make_btn(parent, text, cmd, tip):
            def run():
                cmd()
                tree.focus_set()
            b = ttk.Button(parent, text=text, width=30, command=run)
            b.pack(pady=1)
            add_tip(b, tip)
            return b
 
        g1 = ttk.LabelFrame(side, text="Order in file", padding=4)
        g1.pack(fill=tk.X, pady=(0, 4))
        make_btn(g1, "▲ Move up   (Ctrl+↑)", lambda: move(-1),
                 "Move the selected layer one position up.\nIts structure will be earlier in the exported table.")
        make_btn(g1, "▼ Move down   (Ctrl+↓)", lambda: move(1),
                 "Move the selected layer one position down.")
 
        g2 = ttk.LabelFrame(side, text="What to export", padding=4)
        g2.pack(fill=tk.X, pady=(0, 4))
        make_btn(g2, "Include / exclude   (Space)", toggle_export,
                 "Mark the selected layer for export or remove the mark.\nDouble-click on a row does the same.")
        make_btn(g2, "Include all   (Ctrl+A)", lambda: set_all(True),
                 "Mark all layers for export, including hidden ones.")
        make_btn(g2, "Exclude all   (Ctrl+D)", lambda: set_all(False),
                 "Remove the export mark from all layers.")
 
        g3 = ttk.LabelFrame(side, text="Shared bytecode", padding=4)
        g3.pack(fill=tk.X)
        make_btn(g3, "Use bytecode of other layer…   (S)", share_menu,
                 "Use when the same picture is drawn in different places.\n"
                 "The selected layer keeps its own position/size in the structure,\n"
                 "but points to the bytecode of another layer, so the bytecode\n"
                 "is written to the file only once.\n"
                 "Only layers with identical image data are offered.")
        make_btn(g3, "Make bytecode separate   (U)", unshare,
                 "Cancel sharing for the selected layer: it gets its own copy of bytecode.\n"
                 "If other layers use this layer's bytecode, they become separate.")
        make_btn(g3, "Auto-find duplicates   (A)", auto_share,
                 "Find exported layers with identical image data and make them\n"
                 "share one bytecode (the first one in the list owns it).")
        make_btn(g3, "Make all separate   (Shift+U)", unshare_all,
                 "Cancel all sharing: every exported layer has its own bytecode.")
 
        # ---- адреса ----
        af = ttk.LabelFrame(win, text="Addresses (hex, e.g. FB0000 or FB:0000)", padding=8)
        af.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
 
        ttk.Label(af, text="Structures start:").grid(row=0, column=0, sticky=tk.W, pady=3)
        struct_var = tk.StringVar(value="FB0000")
        e1 = ttk.Entry(af, textvariable=struct_var, width=14, font=('Courier', 10))
        e1.grid(row=0, column=1, sticky=tk.W, padx=8)
        add_tip(e1, "Address in the firmware where the table of structures\n(8 bytes per layer) begins.")
 
        ttk.Label(af, text="Bytecode start:").grid(row=1, column=0, sticky=tk.W, pady=3)
        code_var = tk.StringVar(value="")
        e2 = ttk.Entry(af, textvariable=code_var, width=14, font=('Courier', 10))
        e2.grid(row=1, column=1, sticky=tk.W, padx=8)
        add_tip(e2, "Address where the image bytecode begins.\nLeave empty to place it right after the table of structures.")
        ttk.Label(af, text="(empty = right after the structure table)",
                  foreground="gray").grid(row=1, column=2, sticky=tk.W)
 
        ttk.Label(win, text="Structure: 4 bytes header (x_start, y_block_start, x_end, y_block_end) "
                            "+ 4 bytes bytecode address, reversed (FB:0000 → 00 00 FB 00). "
                            "Layers that share bytecode point to the same address; "
                            "the bytecode is exported once.",
                  foreground="gray", wraplength=840, justify=tk.LEFT).grid(
            row=2, column=0, sticky="w", padx=12, pady=2)
 
        # ---- предпросмотр ----
        pf = ttk.LabelFrame(win, text="Preview of the exported file", padding=6)
        pf.grid(row=3, column=0, sticky="nsew", padx=10, pady=4)
        pf.columnconfigure(0, weight=1)
        pf.rowconfigure(0, weight=1)
        preview = tk.Text(pf, font=('Courier', 9), wrap=tk.NONE, state=tk.DISABLED, height=10)
        preview.grid(row=0, column=0, sticky="nsew")
        psb = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=preview.yview)
        psb.grid(row=0, column=1, sticky="ns")
        preview.configure(yscrollcommand=psb.set)
 
        state = {'blob': None}
 
        def refresh(*_, keep=None):
            normalize()
            if keep is None:
                keep = selected()
            if keep is None and order:
                keep = order[0]
 
            # --- таблица ---
            tree.delete(*tree.get_children())
            pos = 0
            for i in order:
                layer = self.layers[i]
                xs, bs, xe, be = layer.image_params
                size = f"{xe - xs + 1}x{(be - bs + 1) * 8}, {len(layer.image_data)} B"
                if inc[i]:
                    pos += 1
                    num = str(pos)
                    if owner[i] != i:
                        code, tag = f"same as: {lname(owner[i])}", ("shared",)
                    else:
                        n_f = sum(1 for k in order if k != i and inc[k] and owner[k] == i)
                        code = f"own (used by {n_f} more)" if n_f else "own"
                        tag = ()
                else:
                    num, code, tag = "", "— not exported —", ("off",)
                tree.insert("", tk.END, iid=str(i),
                            values=(num, layer.name, size, "✓" if inc[i] else "", code),
                            tags=tag)
            if keep is not None and tree.exists(str(keep)):
                tree.selection_set(str(keep))
                tree.focus(str(keep))
                tree.see(str(keep))
 
            # --- предпросмотр ---
            state['blob'] = None
            lines = []
            try:
                entries = [(i, owner[i]) for i in order if inc[i]]
                if not entries:
                    raise ValueError("No layers selected")
                s_addr = self._parse_addr(struct_var.get())
                if s_addr is None:
                    raise ValueError("Enter structures start address")
                c_addr = self._parse_addr(code_var.get())
                blob, rows = self.build_firmware_blob(entries, s_addr, c_addr)
                state['blob'] = blob
                lines.append(f"Total: {len(blob)} bytes, "
                             f"{self._fmt_addr(s_addr)} - {self._fmt_addr(s_addr + len(blob) - 1)}")
                lines.append("")
                for name, sa, ca, size, shared in rows:
                    off = sa - s_addr
                    rec = blob[off:off + 8]
                    note = (f"shared with '{shared}'" if shared else f"{size} bytes")
                    lines.append(f"{self._fmt_addr(sa)}  {' '.join(f'{b:02X}' for b in rec)}"
                                 f"   ; {name} -> code {self._fmt_addr(ca)} ({note})")
            except ValueError as e:
                lines = [f"! {e}"]
            preview.config(state=tk.NORMAL)
            preview.delete('1.0', tk.END)
            preview.insert('1.0', '\n'.join(lines))
            preview.config(state=tk.DISABLED)
 
        struct_var.trace_add('write', lambda *a: refresh())
        code_var.trace_add('write', lambda *a: refresh())
 
        # ---- кнопки внизу ----
        bf = ttk.Frame(win)
        bf.grid(row=4, column=0, pady=10)
 
        def save_bin(_e=None):
            if state['blob'] is None:
                messagebox.showwarning("Export", "Nothing to export — fix the errors first", parent=win)
                return
            filename = filedialog.asksaveasfilename(
                parent=win, title="Save firmware structures",
                defaultextension=".bin",
                filetypes=[("Binary files", "*.bin"), ("All files", "*.*")])
            if not filename:
                return
            try:
                with open(filename, 'wb') as f:
                    f.write(state['blob'])
                self.log_info(f"Firmware structures exported: {filename} ({len(state['blob'])} bytes)")
                self.set_status(f"Exported {os.path.basename(filename)}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", f"Cannot save file: {e}", parent=win)
 
        def copy_hex(_e=None):
            if state['blob'] is None:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(state['blob'].hex().upper())
            self.set_status("Firmware blob copied to clipboard (hex)")
 
        b_save = ttk.Button(bf, text="Save as .bin…   (Ctrl+S)", width=24, command=save_bin)
        b_save.pack(side=tk.LEFT, padx=6)
        add_tip(b_save, "Save the structure table and the bytecode to a binary file.")
        b_copy = ttk.Button(bf, text="Copy as hex   (Ctrl+Shift+C)", width=26, command=copy_hex)
        b_copy.pack(side=tk.LEFT, padx=6)
        add_tip(b_copy, "Copy the whole exported data to the clipboard as a hex string.")
        b_close = ttk.Button(bf, text="Close   (Esc)", width=14, command=win.destroy)
        b_close.pack(side=tk.LEFT, padx=6)
 
        # ---- горячие клавиши ----
        # Буквенные клавиши продублированы для русской раскладки (Tk даёт Cyrillic-keysym).
        def bind_keys(widget, prefix, keysyms, func):
            for ks in keysyms:
                try:
                    widget.bind(f"<{prefix}Key-{ks}>", func)
                except tk.TclError:
                    pass
 
        def brk(func):
            def handler(_e=None):
                func()
                return "break"
            return handler
 
        # Навигация ↑/↓ — штатная для Treeview; здесь — остальное (только когда фокус на списке)
        tree.bind("<space>", brk(toggle_export))
        tree.bind("<Control-Up>", brk(lambda: move(-1)))
        tree.bind("<Control-Down>", brk(lambda: move(1)))
        tree.bind("<Alt-Up>", brk(lambda: move(-1)))
        tree.bind("<Alt-Down>", brk(lambda: move(1)))
        tree.bind("<Control-Home>", brk(lambda: move_edge(True)))
        tree.bind("<Control-End>", brk(lambda: move_edge(False)))
        tree.bind("<Return>", brk(toggle_export))
        bind_keys(tree, "", ["s", "S", "Cyrillic_yeru", "Cyrillic_YERU"], brk(share_menu))
        bind_keys(tree, "", ["u", "Cyrillic_ghe"], brk(unshare))
        bind_keys(tree, "", ["U", "Cyrillic_GHE"], brk(unshare_all))
        bind_keys(tree, "", ["a", "A", "Cyrillic_ef", "Cyrillic_EF"], brk(auto_share))
        tree.bind("<Double-1>", toggle_export)
 
        # Глобальные для окна (не мешают вводу адресов)
        def guarded(func):
            def handler(_e=None):
                if not in_entry():
                    func()
                    return "break"
            return handler
 
        bind_keys(win, "Control-", ["a", "Cyrillic_ef"], guarded(lambda: set_all(True)))
        bind_keys(win, "Control-", ["d", "Cyrillic_ve"], guarded(lambda: set_all(False)))
        bind_keys(win, "Control-", ["s", "Cyrillic_yeru"], lambda e: (save_bin(), "break")[1])
        bind_keys(win, "Control-", ["C", "Cyrillic_ES"], lambda e: (copy_hex(), "break")[1])
        win.bind('<Escape>', lambda e: win.destroy())
 
        refresh()
        tree.focus_set()
 
    # ==================== КОНЕЦ ЭКСПОРТА В ПРОШИВКУ ====================

    # ==================== ИЗМЕНЕНИЕ РАЗМЕРА СЛОЯ ====================

    @staticmethod
    def _unpack_layer_pixels(data, width, n_blocks):
        """Байты слоя -> 2D-список пикселей [row][col] (1 = чёрный).
        Раскладка данных: byte_idx = block * width + col, бит 0 = верхний пиксель блока."""
        height = n_blocks * 8
        pixels = [[0] * width for _ in range(height)]
        for blk in range(n_blocks):
            for col in range(width):
                idx = blk * width + col
                if idx >= len(data):
                    break
                b = data[idx]
                for bit in range(8):
                    if b & (1 << bit):
                        pixels[blk * 8 + bit][col] = 1
        return pixels

    @staticmethod
    def _pack_layer_pixels(pixels, width, n_blocks):
        """2D-список пикселей -> bytearray в раскладке слоя."""
        data = bytearray(width * n_blocks)
        for blk in range(n_blocks):
            for col in range(width):
                b = 0
                for bit in range(8):
                    if pixels[blk * 8 + bit][col]:
                        b |= (1 << bit)
                data[blk * width + col] = b
        return data

    @classmethod
    def resize_layer_data(cls, data, params, new_width, new_blocks, stretch=False):
        """Возвращает (new_data, new_params) для нового размера.
        stretch=False: пиксели остаются на месте (левый верхний угол), лишнее обрезается,
                       новое поле заполняется белым (0).
        stretch=True:  изображение масштабируется (nearest neighbour) на весь новый размер."""
        x_start, block_start, x_end, block_end = params
        old_w = x_end - x_start + 1
        old_blocks = block_end - block_start + 1
        old_h = old_blocks * 8
        new_h = new_blocks * 8

        src = cls._unpack_layer_pixels(data, old_w, old_blocks)
        dst = [[0] * new_width for _ in range(new_h)]
        if stretch:
            for y in range(new_h):
                sy = y * old_h // new_h
                for x in range(new_width):
                    dst[y][x] = src[sy][x * old_w // new_width]
        else:
            for y in range(min(old_h, new_h)):
                for x in range(min(old_w, new_width)):
                    dst[y][x] = src[y][x]

        new_data = cls._pack_layer_pixels(dst, new_width, new_blocks)
        new_params = (x_start, block_start,
                      x_start + new_width - 1, block_start + new_blocks - 1)
        return new_data, new_params

    def show_resize_layer_dialog(self):
        """Диалог изменения размера активного слоя (правая кнопка по слою)."""
        if self.active_layer_index == -1 or not self.layers:
            messagebox.showwarning("Warning", "No active layer selected")
            return
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Warning", "Layer has no image data")
            return

        x_start, block_start, x_end, block_end = layer.image_params
        cur_w = x_end - x_start + 1
        cur_h = (block_end - block_start + 1) * 8
        # Слой не должен выходить за экран (и параметры должны влезать в байт)
        max_w = max(1, min(self.screen_width - x_start, 256 - x_start))
        max_h = max(8, ((self.screen_height - block_start * 8) // 8) * 8)

        dlg = tk.Toplevel(self.root)
        dlg.title("Resize Layer")
        dlg.resizable(False, False)
        dlg.transient(self.root)
        dlg.grab_set()

        pad = {'padx': 10, 'pady': 5}
        ttk.Label(dlg, text=f"Layer: {layer.name}", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, columnspan=3, sticky=tk.W, padx=10, pady=(10, 2))
        ttk.Label(dlg, text=f"Current size: {cur_w} x {cur_h} px  "
                            f"({cur_h // 8} blocks, {len(layer.image_data)} bytes)",
                  foreground="gray").grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=10)

        w_var = tk.IntVar(value=cur_w)
        h_var = tk.IntVar(value=cur_h)

        ttk.Label(dlg, text="Width (px):").grid(row=2, column=0, sticky=tk.W, **pad)
        ttk.Spinbox(dlg, from_=1, to=max_w, increment=1, width=8, textvariable=w_var,
                    font=('Arial', 10)).grid(row=2, column=1, sticky=tk.W, **pad)
        ttk.Label(dlg, text=f"max {max_w}", foreground="gray").grid(row=2, column=2, sticky=tk.W)

        ttk.Label(dlg, text="Height (px):").grid(row=3, column=0, sticky=tk.W, **pad)
        ttk.Spinbox(dlg, from_=8, to=max_h, increment=8, width=8, textvariable=h_var,
                    font=('Arial', 10)).grid(row=3, column=1, sticky=tk.W, **pad)
        ttk.Label(dlg, text=f"multiple of 8, max {max_h}", foreground="gray").grid(
            row=3, column=2, sticky=tk.W)

        mode_var = tk.StringVar(value="crop")
        mf = ttk.LabelFrame(dlg, text="Content", padding=6)
        mf.grid(row=4, column=0, columnspan=3, sticky="ew", padx=10, pady=6)
        ttk.Radiobutton(mf, text="Keep pixels (crop / pad with white, top-left anchor)",
                        variable=mode_var, value="crop").pack(anchor=tk.W)
        ttk.Radiobutton(mf, text="Stretch image to the new size",
                        variable=mode_var, value="stretch").pack(anchor=tk.W)

        def apply():
            try:
                new_w = int(w_var.get())
                new_h = int(h_var.get())
            except (tk.TclError, ValueError):
                messagebox.showwarning("Invalid size", "Enter integer values.", parent=dlg)
                return
            if new_w < 1 or new_w > max_w:
                messagebox.showwarning("Invalid size",
                                       f"Width must be 1..{max_w}.", parent=dlg)
                return
            if new_h < 1 or new_h > max_h:
                messagebox.showwarning("Invalid size",
                                       f"Height must be 1..{max_h}.", parent=dlg)
                return
            new_blocks = (new_h + 7) // 8      # высота всегда кратна 8 — округляем вверх
            if new_blocks * 8 > max_h:
                new_blocks = max_h // 8

            if new_w == cur_w and new_blocks * 8 == cur_h:
                dlg.destroy()
                return

            self.save_state_for_undo(f"Resize '{layer.name}' to {new_w}x{new_blocks * 8}")
            new_data, new_params = self.resize_layer_data(
                layer.image_data, layer.image_params, new_w, new_blocks,
                stretch=(mode_var.get() == "stretch"))
            layer.image_data = new_data
            layer.image_params = new_params
            self.update_layer_hex_string(layer)
            self.recreate_layer_image(layer)     # данные изменились — перерисовываем всегда
            self.update_active_layer_display()
            self.combine_layers()
            self.log_info(f"Layer '{layer.name}' resized {cur_w}x{cur_h} -> "
                          f"{new_w}x{new_blocks * 8} ({len(new_data)} bytes)")
            self.set_status(f"Layer resized to {new_w}x{new_blocks * 8}")
            dlg.destroy()

        bf = ttk.Frame(dlg)
        bf.grid(row=5, column=0, columnspan=3, pady=10)
        ttk.Button(bf, text="Apply", width=10, command=apply).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Cancel", width=10, command=dlg.destroy).pack(side=tk.LEFT, padx=6)

        dlg.bind('<Return>', lambda e: apply())
        dlg.bind('<Escape>', lambda e: dlg.destroy())

    # ==================== КОНЕЦ ИЗМЕНЕНИЯ РАЗМЕРА СЛОЯ ====================

    # ==================== ЭКСПОРТ ОТДЕЛЬНОГО СЛОЯ ====================

    def _get_exportable_active_layer(self):
        """Возвращает активный слой с изображением или None (с предупреждением)."""
        if self.active_layer_index == -1 or not self.layers:
            messagebox.showwarning("Export", "No active layer selected")
            return None
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            messagebox.showwarning("Export", "Layer has no image data")
            return None
        return layer

    @staticmethod
    def _safe_filename(name):
        s = ''.join(c if (c.isalnum() or c in '-_.') else '_' for c in name.strip())
        return s or "layer"

    def export_layer_image(self):
        """Экспорт изображения только активного слоя (обрезано по рамке слоя)."""
        layer = self._get_exportable_active_layer()
        if layer is None:
            return

        x_start, block_start, x_end, block_end = layer.image_params
        width = x_end - x_start + 1
        n_blocks = block_end - block_start + 1
        pixels = self._unpack_layer_pixels(layer.image_data, width, n_blocks)
        arr = np.array([[0 if p else 255 for p in row] for row in pixels], dtype=np.uint8)

        filename = filedialog.asksaveasfilename(
            title=f"Export Layer Image — {layer.name}",
            initialfile=self._safe_filename(layer.name) + ".png",
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("BMP files", "*.bmp"),
                       ("JPEG files", "*.jpg"), ("All files", "*.*")])
        if not filename:
            return
        try:
            Image.fromarray(arr).save(filename)
            self.log_info(f"Layer '{layer.name}' image exported to: {filename} "
                          f"({width}x{n_blocks * 8} px)")
            self.set_status(f"Layer image saved as {os.path.basename(filename)}")
        except Exception as e:
            messagebox.showerror("Export Error", f"Cannot save image: {e}")

    def export_layer_bytes(self):
        """Окно экспорта байтов активного слоя: .bin / hex-текст / C-массив."""
        layer = self._get_exportable_active_layer()
        if layer is None:
            return

        header = bytes(layer.image_params)
        data = bytes(layer.image_data)
        base = self._safe_filename(layer.name)

        dlg = tk.Toplevel(self.root)
        dlg.title("Export Layer Bytes")
        dlg.geometry("560x420")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.columnconfigure(0, weight=1)
        dlg.rowconfigure(2, weight=1)

        ttk.Label(dlg, text=f"Layer: {layer.name}", font=('Arial', 10, 'bold')).grid(
            row=0, column=0, sticky=tk.W, padx=10, pady=(10, 2))

        opt = ttk.LabelFrame(dlg, text="Options", padding=8)
        opt.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
        inc_header = tk.BooleanVar(value=True)
        fmt_var = tk.StringVar(value="bin")
        ttk.Checkbutton(opt, text="Include 4-byte header (x_start, block_start, x_end, block_end)",
                        variable=inc_header, command=lambda: refresh()).grid(
            row=0, column=0, columnspan=3, sticky=tk.W)
        for col, (text, val) in enumerate([("Binary (.bin)", "bin"),
                                           ("Hex text (.txt)", "hex"),
                                           ("C array (.h)", "c")]):
            ttk.Radiobutton(opt, text=text, variable=fmt_var, value=val,
                            command=lambda: refresh()).grid(row=1, column=col, sticky=tk.W,
                                                            padx=(0, 14), pady=(6, 0))

        pf = ttk.LabelFrame(dlg, text="Preview", padding=6)
        pf.grid(row=2, column=0, sticky="nsew", padx=10, pady=4)
        pf.columnconfigure(0, weight=1)
        pf.rowconfigure(0, weight=1)
        preview = tk.Text(pf, font=('Courier', 9), wrap=tk.WORD, state=tk.DISABLED, height=10)
        preview.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(pf, orient=tk.VERTICAL, command=preview.yview)
        sb.grid(row=0, column=1, sticky="ns")
        preview.configure(yscrollcommand=sb.set)

        def payload():
            return (header + data) if inc_header.get() else data

        def as_hex(b):
            return ' '.join(f'{x:02X}' for x in b)

        def as_c(b):
            name = 'img_' + ''.join(c if c.isalnum() else '_' for c in base).lower()
            if name[4:5].isdigit():
                name = 'img__' + name[4:]
            lines = []
            for i in range(0, len(b), 12):
                lines.append('    ' + ', '.join(f'0x{x:02X}' for x in b[i:i + 12]))
            return (f"const unsigned char {name}[{len(b)}] = {{\n"
                    + ',\n'.join(lines) + "\n};\n")

        def render():
            b = payload()
            f = fmt_var.get()
            if f == "hex":
                return as_hex(b)
            if f == "c":
                return as_c(b)
            return as_hex(b)

        def refresh(*_):
            b = payload()
            text = f"{len(b)} bytes\n\n{render()}"
            preview.config(state=tk.NORMAL)
            preview.delete('1.0', tk.END)
            preview.insert('1.0', text)
            preview.config(state=tk.DISABLED)

        def save():
            f = fmt_var.get()
            ext, ftypes = {
                "bin": (".bin", [("Binary files", "*.bin")]),
                "hex": (".txt", [("Text files", "*.txt")]),
                "c":   (".h",   [("C header", "*.h")]),
            }[f]
            filename = filedialog.asksaveasfilename(
                parent=dlg, title="Save layer bytes", initialfile=base + ext,
                defaultextension=ext, filetypes=ftypes + [("All files", "*.*")])
            if not filename:
                return
            try:
                if f == "bin":
                    with open(filename, 'wb') as fh:
                        fh.write(payload())
                else:
                    with open(filename, 'w', encoding='utf-8') as fh:
                        fh.write(render() + "\n")
                self.log_info(f"Layer '{layer.name}' bytes exported: {filename} "
                              f"({len(payload())} bytes)")
                self.set_status(f"Layer bytes saved as {os.path.basename(filename)}")
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Export Error", f"Cannot save file: {e}", parent=dlg)

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(render())
            self.set_status("Layer bytes copied to clipboard")

        bf = ttk.Frame(dlg)
        bf.grid(row=3, column=0, pady=10)
        ttk.Button(bf, text="Save...", width=12, command=save).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Copy", width=12, command=copy).pack(side=tk.LEFT, padx=6)
        ttk.Button(bf, text="Close", width=12, command=dlg.destroy).pack(side=tk.LEFT, padx=6)
        dlg.bind('<Escape>', lambda e: dlg.destroy())
        refresh()

    # ==================== КОНЕЦ ЭКСПОРТА ОТДЕЛЬНОГО СЛОЯ ====================

    def show_hotkeys(self):
        """Показывает окно с горячими клавишами."""
        win = tk.Toplevel(self.root)
        win.title("Hotkeys")
        win.resizable(False, False)
        win.transient(self.root)

        hotkeys = [
            ("Ctrl+N",   "New Image"),
            ("Del",      "Delete Layer"),
            ("Ctrl+H",   "Toggle Visibility"),
            ("← → ↑ ↓", "Move Image"),
            ("F5",       "Manual Update"),
            ("Ctrl++",   "Zoom In"),
            ("Ctrl+-",   "Zoom Out"),
            ("Ctrl+S",   "Save Project"),
            ("Ctrl+O",   "Load Project"),
            ("Ctrl+Z",   "Undo"),
            ("Ctrl+Y",   "Redo"),
        ]

        frame = ttk.Frame(win, padding=15)
        frame.pack(fill=tk.BOTH, expand=True)

        for i, (key, desc) in enumerate(hotkeys):
            ttk.Label(frame, text=key, font=('Courier', 9, 'bold'),
                      anchor=tk.E, width=12).grid(row=i, column=0, sticky=tk.E, pady=2, padx=(0, 8))
            ttk.Label(frame, text=desc, font=('Arial', 9)).grid(row=i, column=1, sticky=tk.W, pady=2)

        ttk.Button(frame, text="Close", command=win.destroy).grid(
            row=len(hotkeys), column=0, columnspan=2, pady=(12, 0))
        win.bind('<Escape>', lambda e: win.destroy())

    def show_about(self):
        """Показывает окно 'О программе'"""
        messagebox.showinfo("About", "Byte2Image Editor\n\nVersion 0.7.0\n\nDENSO Hex image editor with layer support\n\nBy McShel")
        
    def setup_ui(self):
        # Настройка растягивания корневого окна
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)  # main_paned растягивается

        # ====================
        # ТУЛБАР — на всю ширину окна, row=0
        # ====================
        toolbar_frame = ttk.Frame(self.root, padding=(4, 3))
        self.toolbar_frame = toolbar_frame
        toolbar_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        # Кнопки Undo/Redo
        self.undo_btn = ttk.Button(toolbar_frame, text="↶", width=3,
                                command=self.undo, state=tk.DISABLED)
        self.undo_btn.pack(side=tk.LEFT, padx=1)
        self.redo_btn = ttk.Button(toolbar_frame, text="↷", width=3,
                                command=self.redo, state=tk.DISABLED)
        self.redo_btn.pack(side=tk.LEFT, padx=1)

        ttk.Label(toolbar_frame, text="|", foreground="gray").pack(side=tk.LEFT, padx=2)

        self.move_btn  = tk.Button(toolbar_frame, text="↖ Move",  width=8,
                                   relief=tk.SUNKEN, command=self.enter_move_mode)
        self.move_btn.pack(side=tk.LEFT, padx=2)
        self.shift_btn = tk.Button(toolbar_frame, text="⇔ Shift", width=8,
                                   relief=tk.RAISED, command=self.enter_shift_mode)
        self.shift_btn.pack(side=tk.LEFT, padx=2)
        self.draw_btn  = tk.Button(toolbar_frame, text="✏ Draw",  width=8,
                                   relief=tk.RAISED, command=self.enter_draw_mode)
        self.draw_btn.pack(side=tk.LEFT, padx=2)
        self.erase_btn = tk.Button(toolbar_frame, text="⬜ Erase", width=8,
                                   relief=tk.RAISED, command=self.enter_erase_mode)
        self.erase_btn.pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar_frame, text="|", foreground="gray").pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar_frame, text="🔍-", width=4,
                command=self.zoom_out).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar_frame, text="🔍+", width=4,
                command=self.zoom_in).pack(side=tk.LEFT, padx=1)
        self.zoom_label = ttk.Label(toolbar_frame, text="5x", foreground="blue", width=4)
        self.zoom_label.pack(side=tk.LEFT, padx=2)

        ttk.Label(toolbar_frame, text="|", foreground="gray").pack(side=tk.LEFT, padx=2)

        ttk.Button(toolbar_frame, text="←", width=2,
                command=self.move_layer_left).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar_frame, text="→", width=2,
                command=self.move_layer_right).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar_frame, text="↑", width=2,
                command=self.move_layer_up_pos).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar_frame, text="↓", width=2,
                command=self.move_layer_down_pos).pack(side=tk.LEFT, padx=1)

        ttk.Label(toolbar_frame, text="|", foreground="gray").pack(side=tk.LEFT, padx=2)

        self.auto_update_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(toolbar_frame, text="Auto Update", variable=self.auto_update_var,
                command=self.toggle_auto_update).pack(side=tk.LEFT, padx=2)

        self.active_layer_label = ttk.Label(toolbar_frame, text="No active layer",
                                        foreground="green", font=('Arial', 10))
        self.active_layer_label.pack(side=tk.RIGHT, padx=10)

        # ====================
        # ОСНОВНОЙ КОНТЕЙНЕР — row=1
        # ====================
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.main_paned = main_paned

        # --------------------
        # ЛЕВАЯ ПАНЕЛЬ - Layers
        # --------------------
        left_frame = ttk.LabelFrame(main_paned, text="Layers", padding="5")
        self.left_frame = left_frame
        left_frame.columnconfigure(0, weight=1)
        left_frame.rowconfigure(0, weight=1)

        # Список слоев с полосой прокрутки
        self.layer_list_frame = ttk.Frame(left_frame)
        self.layer_list_frame.grid(row=0, column=0, sticky="nsew")
        self.layer_list_frame.columnconfigure(0, weight=1)
        self.layer_list_frame.rowconfigure(0, weight=1)

        layer_scrollbar = ttk.Scrollbar(self.layer_list_frame, orient=tk.VERTICAL)
        layer_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2,0))

        self.layer_listbox = tk.Listbox(
            self.layer_list_frame,
            yscrollcommand=layer_scrollbar.set,
            selectmode=tk.SINGLE,
            font=('Arial', 9),
            bg='white'
        )
        self.layer_listbox.grid(row=0, column=0, sticky="nsew")
        layer_scrollbar.config(command=self.layer_listbox.yview)

        # Привязка событий
        self.layer_listbox.bind('<<ListboxSelect>>', self.on_layer_select)
        self.layer_listbox.bind('<Double-Button-1>', self.on_layer_double_click)
        self.layer_listbox.bind('<Button-3>', self.on_layer_right_click)

        # Drag & Drop: начало, движение, конец
        self.layer_listbox.bind('<ButtonPress-1>',   self.on_dnd_start)
        self.layer_listbox.bind('<B1-Motion>',        self.on_dnd_motion)
        self.layer_listbox.bind('<ButtonRelease-1>',  self.on_dnd_release)

        # Кнопки управления слоями — под списком
        button_frame = ttk.Frame(left_frame)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(5, 0))

        ttk.Button(button_frame, text="+", width=2,
                command=self.add_new_layer).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(button_frame, text="-", width=2,
                command=self.delete_layer).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Label(button_frame, text="", width=1).pack(side=tk.LEFT)
        self.toggle_visibility_btn = ttk.Button(button_frame, text="●", width=5,
                                                command=self.toggle_active_layer_visibility)
        self.toggle_visibility_btn.pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(button_frame, text="A●", width=4,
                command=self.show_all_layers).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(button_frame, text="A○", width=4,
                command=self.hide_all_layers).pack(side=tk.LEFT, padx=2, pady=2)

        main_paned.add(left_frame, weight=1)
        
        # --------------------
        # ЦЕНТР - Display + Hex
        # --------------------
        center_paned = ttk.PanedWindow(main_paned, orient=tk.VERTICAL)
        self.center_paned = center_paned

        # Верхняя часть центра - отображение
        center_top = ttk.Frame(center_paned)
        self.center_top = center_top
        
        # Display area
        self.image_container = ttk.LabelFrame(center_top, text=f"Display ({self.screen_width}x{self.screen_height})", padding="5")
        self.image_container.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        self.image_container.columnconfigure(0, weight=1)
        self.image_container.rowconfigure(0, weight=1)
        
        self.canvas_frame = ttk.Frame(self.image_container)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew")
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas_frame.rowconfigure(0, weight=1)
        
        self.canvas = tk.Canvas(self.canvas_frame, bg='white', 
                            highlightthickness=1, highlightbackground="gray")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<ButtonPress-1>",   self.on_canvas_press)
        self.canvas.bind("<B1-Motion>",       self.on_canvas_motion)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_drag_release)
        self.canvas.bind("<Button-3>",        self.on_canvas_right_click)
        # Колесо мыши на canvas: Ctrl+колесо = зум, просто колесо = скролл
        self.canvas.bind("<MouseWheel>",        self.on_canvas_mousewheel)  # Windows
        self.canvas.bind("<Button-4>",          self.on_canvas_mousewheel)  # Linux вверх
        self.canvas.bind("<Button-5>",          self.on_canvas_mousewheel)  # Linux вниз
        
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL, 
                                        command=self.canvas.yview)
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL,
                                        command=self.canvas.xview)
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.v_scrollbar.set, 
                            xscrollcommand=self.h_scrollbar.set)
        
        center_paned.add(center_top, weight=3)
        
        # Нижняя часть центра - Hex panel
        hex_frame = ttk.LabelFrame(center_paned, text="Active Layer Hex", padding="5")
        self.hex_frame = hex_frame

        self.hex_entry = tk.Text(hex_frame, height=2, font=('Courier', 9), wrap=tk.WORD)
        self.hex_entry.pack(fill=tk.BOTH, expand=True)
        self.hex_entry.tag_config('header', foreground='white', background='#2255AA')

        hex_btn_frame = ttk.Frame(hex_frame)
        hex_btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(hex_btn_frame, text="Update", width=10,
                command=self.update_active_layer).pack(side=tk.LEFT, padx=2)
        ttk.Button(hex_btn_frame, text="Clear", width=10,
                command=self.clear_active_layer).pack(side=tk.LEFT, padx=2)
        ttk.Button(hex_btn_frame, text="Copy", width=10,
                command=self.copy_hex_to_clipboard).pack(side=tk.LEFT, padx=2)
        ttk.Button(hex_btn_frame, text="Paste", width=10,
                command=self.paste_from_clipboard).pack(side=tk.LEFT, padx=2)
        
        # Панель добавляется в paned только если включена (по умолчанию скрыта)
        if self.show_hex_panel.get():
            center_paned.add(hex_frame, weight=1)

        main_paned.add(center_paned, weight=8)
        
        # --------------------
        # ПРАВАЯ ПАНЕЛЬ - Log
        # --------------------
        right_frame = ttk.LabelFrame(main_paned, text="Log", padding="5")
        self.right_frame = right_frame

        self.info_text = tk.Text(right_frame, height=15, font=('Courier', 8), wrap=tk.WORD)
        self.info_text.pack(fill=tk.BOTH, expand=True)

        log_scroll = ttk.Scrollbar(self.info_text, orient=tk.VERTICAL,
                                command=self.info_text.yview)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.info_text.configure(yscrollcommand=log_scroll.set)

        log_btn_frame = ttk.Frame(right_frame)
        log_btn_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Button(log_btn_frame, text="Clear Log", width=10,
                command=self.clear_info).pack(side=tk.LEFT, padx=2)
        
        main_paned.add(right_frame, weight=1)

        # Применяем начальную видимость панелей (Hex скрыт по умолчанию)
        self.apply_panel_visibility()

        # Статус бар
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - No layers")
        status_bar = ttk.Label(self.root, textvariable=self.status_var,
                            relief=tk.SUNKEN, font=('Arial', 9))
        status_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        
        # Создаем первый слой по умолчанию
        self.add_new_layer()
        
    # === МЕТОДЫ ДЛЯ УПРАВЛЕНИЯ ВИДИМОСТЬЮ ===
    
    def toggle_active_layer_visibility(self):
        """Переключает видимость активного слоя"""
        if self.active_layer_index == -1:
            return
            
        layer = self.layers[self.active_layer_index]
        
        # Сохраняем состояние перед изменением
        self.save_state_for_undo(f"Toggle visibility: {layer.name}")
        
        layer.visible = not layer.visible
        
        # Обновляем текст кнопки
        if layer.visible:
            self.toggle_visibility_btn.config(text="H")
        else:
            self.toggle_visibility_btn.config(text="S")
        
        self.update_layer_list()
        self.combine_layers()
        
        status = "shown" if layer.visible else "hidden"
        self.log_info(f"Layer '{layer.name}' {status}")
    
    def show_only_active_layer(self):
        """Показывает только активный слой, скрывая все остальные"""
        if self.active_layer_index == -1:
            return
            
        # Сохраняем состояние перед изменением
        self.save_state_for_undo("Show only active layer")
            
        # Скрываем все слои
        for layer in self.layers:
            layer.visible = False
        
        # Показываем только активный
        self.layers[self.active_layer_index].visible = True
        
        # Обновляем кнопку
        self.toggle_visibility_btn.config(text="Hide")
        
        self.update_layer_list()
        self.combine_layers()
        
        self.log_info(f"Showing only layer: {self.layers[self.active_layer_index].name}")
    
    def on_layer_double_click(self, event):
        """Обрабатывает двойной клик по слою - переименование"""
        selection = self.layer_listbox.curselection()
        if not selection:
            return
            
        index = selection[0]
        layer = self.layers[index]
        
        # Сохраняем старое имя
        old_name = layer.name
        
        # Создаем всплывающее окно для переименования
        rename_window = tk.Toplevel(self.root)
        rename_window.title("Rename Layer")
        rename_window.geometry("300x120")
        rename_window.transient(self.root)
        rename_window.grab_set()
        
        ttk.Label(rename_window, text=f"Rename layer:", 
                 font=('Arial', 10, 'bold')).pack(pady=10)
        
        name_var = tk.StringVar(value=layer.name)
        name_entry = ttk.Entry(rename_window, textvariable=name_var, font=('Arial', 10))
        name_entry.pack(pady=5, padx=20, fill=tk.X)
        name_entry.select_range(0, tk.END)
        name_entry.focus_set()
        
        def apply_rename():
            new_name = name_var.get().strip()
            if new_name and new_name != old_name:
                # Сохраняем состояние перед изменением
                self.save_state_for_undo(f"Rename layer: {old_name} → {new_name}")
                
                layer.name = new_name
                self.update_layer_list()
                self.update_active_layer_display()
                self.log_info(f"Layer renamed to: {new_name}")
            rename_window.destroy()
        
        btn_frame = ttk.Frame(rename_window)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="OK", command=apply_rename, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=rename_window.destroy, width=10).pack(side=tk.LEFT, padx=5)
        
        # Привязываем Enter для быстрого подтверждения
        rename_window.bind('<Return>', lambda e: apply_rename())
        rename_window.bind('<Escape>', lambda e: rename_window.destroy())
    
    def on_layer_right_click(self, event):
        """Контекстное меню для слоя"""
        index = self.layer_listbox.nearest(event.y)
        if index < 0 or index >= len(self.layers):
            return

        # Выбираем этот слой
        self.layer_listbox.selection_clear(0, tk.END)
        self.layer_listbox.selection_set(index)
        self.active_layer_index = index
        self.update_active_layer_display()

        layer = self.layers[index]
        m = tk.Menu(self.root, tearoff=0)

        # Видимость
        vis_label = "○  Hide Layer" if layer.visible else "●  Show Layer"
        m.add_command(label=vis_label, command=self.toggle_active_layer_visibility)
        m.add_command(label="◎  Show Only This Layer", command=self.show_only_active_layer)
        m.add_command(label="●  Show All Layers",      command=self.show_all_layers)
        m.add_command(label="○  Hide All Layers",      command=self.hide_all_layers)

        m.add_separator()
        
        m.add_command(label="◎  Center on Layer", command=self.center_on_output_area)
        m.add_separator()

        # Редактирование
        m.add_command(label="✎  Rename Layer",
                      command=lambda: self.on_layer_double_click(None))
        m.add_command(label="⧉  Duplicate Layer",
                      command=self.duplicate_active_layer)
        m.add_command(label="⤢  Resize Layer...",
                      command=self.show_resize_layer_dialog,
                      state=tk.NORMAL if (layer.image_params is not None
                                          and layer.image_data is not None) else tk.DISABLED)

        m.add_separator()

        # Экспорт слоя
        m.add_cascade(label="💾  Export", menu=self._build_export_menu(m, layer))

        m.add_separator()

        # Порядок
        m.add_command(label="↑  Move Up",   command=self.move_layer_up,
                      state=tk.NORMAL if index > 0 else tk.DISABLED)
        m.add_command(label="↓  Move Down", command=self.move_layer_down,
                      state=tk.NORMAL if index < len(self.layers) - 1 else tk.DISABLED)

        m.add_separator()

        # Удаление
        m.add_command(label="✕  Delete Layer", command=self.delete_layer,
                      foreground='red' if len(self.layers) > 1 else 'gray')

        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()
    
    # === DRAG & DROP ДЛЯ ПЕРЕМЕЩЕНИЯ СЛОЯ НА CANVAS ===

    def _canvas_hit_test(self, cx, cy):
        """Проверяет, попадает ли точка (cx,cy) в canvas-пикселях в активный слой.
        Возвращает True если попали в bounding box слоя."""
        if self.active_layer_index == -1:
            return False
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None or layer.image_data is None:
            return False
        x_start, block_start, x_end, block_end = layer.image_params
        sf = self.scale_factor
        lx1 = x_start * sf
        ly1 = block_start * 8 * sf
        lx2 = (x_end + 1) * sf
        ly2 = (block_end * 8 + 8) * sf
        return lx1 <= cx <= lx2 and ly1 <= cy <= ly2

    def on_canvas_press(self, event):
        """Диспетчер ButtonPress-1: shift → сдвиг, edit → пиксель, иначе → DnD."""
        if self.shift_mode:
            self._on_shift_start(event)
        elif self.edit_mode:
            self._pixel_edit_active = True
            self.begin_batch_edit("Edit Pixels")
            self.on_canvas_click(event)
        else:
            self.on_canvas_drag_start(event)

    def on_canvas_motion(self, event):
        """Диспетчер B1-Motion."""
        if self.shift_mode:
            self._on_shift_motion(event)
        elif self.edit_mode:
            self.on_canvas_click(event)
        else:
            self.on_canvas_drag_motion(event)

    def on_canvas_drag_start(self, event):
        """Начало перетаскивания слоя по canvas."""
        # В режиме редактирования пикселей DnD не работает
        if self.edit_mode:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        if not self._canvas_hit_test(cx, cy):
            return

        layer = self.layers[self.active_layer_index]
        self._canvas_drag_active = True
        self._canvas_drag_start_x = cx
        self._canvas_drag_start_y = cy
        self._canvas_drag_orig_params = tuple(layer.image_params)
        self.canvas.config(cursor="fleur")

    def on_canvas_drag_motion(self, event):
        """Перемещение мыши — двигаем слой в реальном времени."""
        if not self._canvas_drag_active:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)

        sf = self.scale_factor
        orig = self._canvas_drag_orig_params
        x_start0, block_start0, x_end0, block_end0 = orig

        # Смещение в пикселях изображения (X) и блоках (Y)
        dx_px  = int((cx - self._canvas_drag_start_x) / sf)
        dy_blk = int(round((cy - self._canvas_drag_start_y) / (sf * 8)))

        new_x_start  = x_start0  + dx_px
        new_x_end    = x_end0    + dx_px
        new_blk_start = block_start0 + dy_blk
        new_blk_end   = block_end0   + dy_blk

        # Зажимаем в границы экрана
        w = x_end0 - x_start0
        h = block_end0 - block_start0
        new_x_start  = max(0, min(self.screen_width  - 1 - w, new_x_start))
        new_x_end    = new_x_start + w
        new_blk_start = max(0, min(254 - h, new_blk_start))
        new_blk_end   = new_blk_start + h

        layer = self.layers[self.active_layer_index]
        layer.image_params = (new_x_start, new_blk_start, new_x_end, new_blk_end)

        # Быстрый предпросмотр: только пересоздаём изображение и рамки
        self.recreate_layer_image(layer)
        self.combine_layers()

    def on_canvas_drag_release(self, event):
        """Завершение перетаскивания или рисования."""
        # Завершаем сдвиг пикселей
        if self.shift_mode and self._shift_orig_data is not None:
            self._on_shift_release(event)
            return

        # Завершаем серию рисования пикселей
        if self._pixel_edit_active:
            self._pixel_edit_active = False
            self.end_batch_edit()
            return

        if not self._canvas_drag_active:
            return

        self._canvas_drag_active = False
        self.canvas.config(cursor="")

        layer = self.layers[self.active_layer_index]

        # Ничего не сдвинулось — не пишем undo
        if layer.image_params == self._canvas_drag_orig_params:
            self._canvas_drag_orig_params = None
            return

        # Сохраняем состояние ДО в undo (используем debounce-метод)
        # Но нам нужно сохранить именно оригинальное состояние,
        # поэтому пишем вручную, не через debounce
        orig_state = {
            'description': f"Drag '{layer.name}' on canvas",
            'layers': None,   # заполним ниже
            'active_layer_index': self.active_layer_index,
            'timestamp': len(self.undo_stack)
        }
        # Временно подменяем params на оригинал, снимаем стейт, восстанавливаем
        current_params = layer.image_params
        layer.image_params = self._canvas_drag_orig_params
        orig_state['layers'] = [l.get_state_dict() for l in self.layers]
        layer.image_params = current_params

        self.undo_stack.append(orig_state)
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_redo_buttons()

        # Обновляем hex-строку слоя
        self.update_layer_hex_string(layer)
        self.update_active_layer_display()
        self.combine_layers()

        x_start, block_start, x_end, block_end = layer.image_params
        self.log_info(f"Canvas drag: '{layer.name}' → X={x_start}-{x_end}, blocks={block_start}-{block_end}")
        self.set_status(f"Layer '{layer.name}' moved to ({x_start}, {block_start*8})")
        self._canvas_drag_orig_params = None

    # === КОНЕЦ CANVAS DRAG & DROP ===

    # ── Select ────────────────────────────────────────────
    def on_canvas_right_click(self, event):
        """Контекстное меню по правой кнопке на canvas."""
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px = int(cx) // self.scale_factor
        py = int(cy) // self.scale_factor
        sf = self.scale_factor

        # Собираем ВСЕ слои под курсором (сверху вниз по z-order)
        hit_indices = []
        for i in range(len(self.layers) - 1, -1, -1):
            layer = self.layers[i]
            if layer.image_params is None:
                continue
            x_start, block_start, x_end, block_end = layer.image_params
            lx1 = x_start * sf
            ly1 = block_start * 8 * sf
            lx2 = (x_end + 1) * sf
            ly2 = (block_end * 8 + 8) * sf
            if lx1 <= cx <= lx2 and ly1 <= cy <= ly2:
                hit_indices.append(i)

        # Все пункты действий всегда применяются к АКТИВНОМУ слою
        act_idx   = self.active_layer_index
        act_layer = self.layers[act_idx] if act_idx >= 0 and self.layers else None
        has_image = act_layer is not None and act_layer.image_array is not None

        m = tk.Menu(self.root, tearoff=0)

        # ── Select ────────────────────────────────────────────
        if len(hit_indices) > 1:
            select_menu = tk.Menu(m, tearoff=0)
            for idx in hit_indices:
                lyr = self.layers[idx]
                vis    = "●" if lyr.visible else "○"
                marker = "  ✓" if idx == act_idx else ""
                select_menu.add_command(
                    label=f"{vis}  {lyr.name}{marker}",
                    command=lambda i=idx: self._select_layer(i))
            m.add_cascade(label="★  Select Layer", menu=select_menu)
            m.add_separator()
        elif len(hit_indices) == 1 and hit_indices[0] != act_idx:
            lyr = self.layers[hit_indices[0]]
            m.add_command(
                label=f"★  Select '{lyr.name}'",
                font=('Arial', 9, 'bold'),
                command=lambda i=hit_indices[0]: self._select_layer(i))
            m.add_separator()

        # ── Инструменты (для активного слоя) ─────────────────
        def _check(active): return "  ✓" if active else "   "

        m.add_command(
            label=f"↖  Move{_check(not self.edit_mode and not self.shift_mode)}",
            command=self.enter_move_mode)
        m.add_command(
            label=f"⇔  Shift Pixels{_check(self.shift_mode)}",
            command=self.enter_shift_mode,
            state=tk.NORMAL if has_image else tk.DISABLED)
        m.add_command(
            label=f"✏  Draw{_check(self.edit_mode and self.current_color_index == 0)}",
            command=self.enter_draw_mode,
            state=tk.NORMAL if has_image else tk.DISABLED)
        m.add_command(
            label=f"⬜  Erase{_check(self.edit_mode and self.current_color_index == 1)}",
            command=self.enter_erase_mode,
            state=tk.NORMAL if has_image else tk.DISABLED)

        m.add_separator()

        # ── Активный слой ─────────────────────────────────────
        if act_layer is not None:
            name = act_layer.name
            vis_label = f"○  Hide '{name}'" if act_layer.visible else f"●  Show '{name}'"
            m.add_command(label=vis_label,
                          command=self.toggle_active_layer_visibility)
            m.add_command(label=f"⧉  Duplicate '{name}'",
                          command=self.duplicate_active_layer)
            m.add_command(label=f"⤢  Resize '{name}'...",
                          command=self.show_resize_layer_dialog,
                          state=tk.NORMAL if has_image else tk.DISABLED)
            m.add_command(label=f"✕  Clear '{name}'",
                          command=self.clear_active_layer,
                          state=tk.NORMAL if has_image else tk.DISABLED)
        else:
            m.add_command(label="No active layer", state=tk.DISABLED)

        m.add_separator()

        # ── Вид ───────────────────────────────────────────────
        m.add_command(label=f"🔍+  Zoom In   ({self.scale_factor}x)",
                      command=self.zoom_in)
        m.add_command(label=f"🔍−  Zoom Out  ({self.scale_factor}x)",
                      command=self.zoom_out)
        m.add_command(label="◎  Center on Layer",
                      command=self.center_on_output_area,
                      state=tk.NORMAL if has_image else tk.DISABLED)

        m.add_separator()

        m.add_cascade(label="💾  Export", menu=self._build_export_menu(m, act_layer))

        if 0 <= px < self.screen_width and 0 <= py < self.screen_height:
            m.add_separator()
            info = f"   ({px}, {py})"
            if act_layer:
                info += f"  —  {act_layer.name}"
            m.add_command(label=info, state=tk.DISABLED)

        try:
            m.tk_popup(event.x_root, event.y_root)
        finally:
            m.grab_release()

    def _select_layer(self, idx):
        """Выбирает слой по индексу и обновляет UI."""
        self.active_layer_index = idx
        self.layer_listbox.selection_clear(0, tk.END)
        self.layer_listbox.selection_set(idx)
        self.layer_listbox.see(idx)
        self.update_active_layer_display()

    # === DRAG & DROP ДЛЯ СПИСКА СЛОЕВ ===

    def on_dnd_start(self, event):
        """Фиксируем индекс элемента, который начали тащить"""
        idx = self.layer_listbox.nearest(event.y)
        if 0 <= idx < len(self.layers):
            self._dnd_drag_index = idx
            self._dnd_last_target = None
            # Меняем курсор, чтобы дать визуальную обратную связь
            self.layer_listbox.config(cursor="fleur")

    def on_dnd_motion(self, event):
        """Подсвечиваем элемент под курсором во время перетаскивания"""
        if self._dnd_drag_index is None:
            return

        target = self.layer_listbox.nearest(event.y)
        if target == self._dnd_last_target:
            return  # Ничего не изменилось, не перерисовываем

        # Убираем подсветку со старой цели
        if self._dnd_last_target is not None:
            self._restore_listbox_item_color(self._dnd_last_target)

        # Подсвечиваем новую цель (если это не сам перетаскиваемый элемент)
        if target != self._dnd_drag_index and 0 <= target < len(self.layers):
            self.layer_listbox.itemconfig(target, bg='#FFD700')  # Золотой
        self._dnd_last_target = target

    def on_dnd_release(self, event):
        """Завершаем перетаскивание: переставляем слои"""
        self.layer_listbox.config(cursor="")

        if self._dnd_drag_index is None:
            return

        target = self.layer_listbox.nearest(event.y)
        src = self._dnd_drag_index
        self._dnd_drag_index = None

        # Снимаем подсветку
        if self._dnd_last_target is not None:
            self._restore_listbox_item_color(self._dnd_last_target)
        self._dnd_last_target = None

        if target == src or not (0 <= target < len(self.layers)):
            return  # Нет смысла переставлять

        # Сохраняем состояние для undo
        self.save_state_for_undo(f"Drag layer '{self.layers[src].name}' → position {target}")

        # Перемещаем слой
        layer = self.layers.pop(src)
        self.layers.insert(target, layer)

        # Корректируем active_layer_index
        if self.active_layer_index == src:
            self.active_layer_index = target
        elif src < self.active_layer_index <= target:
            self.active_layer_index -= 1
        elif target <= self.active_layer_index < src:
            self.active_layer_index += 1

        self.update_layer_list()
        self.layer_listbox.selection_set(self.active_layer_index)
        self.combine_layers()
        self.log_info(f"Layer moved: index {src} → {target}")
        self.set_status(f"Layer moved to position {target + 1}")

    def _restore_listbox_item_color(self, idx):
        """Восстанавливает стандартный цвет фона для элемента списка"""
        if idx < 0 or idx >= len(self.layers):
            return
        layer = self.layers[idx]
        if not layer.visible:
            bg = '#f5f5f5'
        else:
            bg = 'white'
        self.layer_listbox.itemconfig(idx, bg=bg)

    # === КОНЕЦ DRAG & DROP ===

    def update_layer_list(self):
        """Обновляет список слоев с иконками видимости"""
        self.layer_listbox.delete(0, tk.END)
        
        for i, layer in enumerate(self.layers):
            if layer.visible:
                visibility_icon = "●"
                fg_color = 'black'
            else:
                visibility_icon = "○"
                fg_color = 'gray'
            
            image_icon = " ▪" if layer.image_array is not None else ""
            text = f"{visibility_icon} {layer.name} {image_icon}"
            
            self.layer_listbox.insert(i, text)
            self.layer_listbox.itemconfig(i, fg=fg_color)
            
            # Скрытые слои — серый фон, видимые — белый (активный определяется через selection_set)
            if not layer.visible:
                self.layer_listbox.itemconfig(i, bg='#f5f5f5')
            else:
                self.layer_listbox.itemconfig(i, bg='white')
        
        # Системное выделение активного слоя
        if self.active_layer_index >= 0:
            self.layer_listbox.selection_set(self.active_layer_index)
            self.layer_listbox.see(self.active_layer_index)
        
        # Обновляем кнопку видимости
        if self.active_layer_index != -1 and self.layers:
            layer = self.layers[self.active_layer_index]
            if layer.visible:
                self.toggle_visibility_btn.config(text="Hide")
            else:
                self.toggle_visibility_btn.config(text="Show")
    
    # === ОБНОВЛЕННЫЕ МЕТОДЫ ДЛЯ РАБОТЫ СО СЛОЯМИ ===
    
    def on_layer_select(self, event):
        """Обрабатывает выбор слоя в списке"""
        selection = self.layer_listbox.curselection()
        if selection:
            self.active_layer_index = selection[0]
            self.update_active_layer_display()
            if self.highlight_on_select.get():
                self.flash_active_layer_border()
    
    def update_active_layer_display(self):
        """Обновляет отображение активного слоя"""
        if self.active_layer_index == -1 or not self.layers:
            self.active_layer_label.config(text="No active layer")
            self._hex_set('')
            self.toggle_visibility_btn.config(text="H", state=tk.DISABLED)
            return
            
        layer = self.layers[self.active_layer_index]
        self.active_layer_label.config(text=f"Active: {layer.name}")
        
        # Обновляем hex-строку
        self._hex_set(layer.hex_string)
        
        # Обновляем кнопку видимости
        self.toggle_visibility_btn.config(state=tk.NORMAL)
        if layer.visible:
            self.toggle_visibility_btn.config(text="Hide")
        else:
            self.toggle_visibility_btn.config(text="Show")
        
        # Перерисовываем комбинированное изображение
        self.combine_layers()  # Используем combine_layers для отображения
    
    def add_new_layer(self, name=None):
        """Добавляет новый слой"""
        if name is None:
            name = f"Layer {len(self.layers) + 1}"
        
        # Сохраняем состояние перед добавлением
        self.save_state_for_undo(f"Add layer: {name}")
        
        layer = Layer(name)
        self.layers.append(layer)
        self.update_layer_list()
        
        # Активируем новый слой
        self.active_layer_index = len(self.layers) - 1
        self.layer_listbox.selection_set(self.active_layer_index)
        self.update_active_layer_display()
        
        self.log_info(f"Added new layer: {name}")
        self.set_status(f"Active: {name}")
    
    def duplicate_active_layer(self):
        """Дублирует активный слой."""
        if self.active_layer_index == -1:
            return
        self.save_state_for_undo(f"Duplicate layer: {self.layers[self.active_layer_index].name}")
        src = self.layers[self.active_layer_index]
        new_layer = src.clone()
        new_layer.name = src.name + " copy"
        insert_at = self.active_layer_index + 1
        self.layers.insert(insert_at, new_layer)
        self.active_layer_index = insert_at
        self.update_layer_list()
        self.layer_listbox.selection_set(self.active_layer_index)
        self.update_active_layer_display()
        self.log_info(f"Duplicated layer: {new_layer.name}")
        self.set_status(f"Layer duplicated: {new_layer.name}")

    def delete_layer(self):
        """Удаляет активный слой"""
        if self.active_layer_index == -1:
            return
            
        if len(self.layers) <= 1:
            messagebox.showwarning("Warning", "Cannot delete the only layer")
            return
        
        layer_name = self.layers[self.active_layer_index].name
        
        # Сохраняем состояние перед удалением
        self.save_state_for_undo(f"Delete layer: {layer_name}")
        
        # Удаляем слой
        del self.layers[self.active_layer_index]
        
        # Корректируем индекс активного слоя
        if self.active_layer_index >= len(self.layers):
            self.active_layer_index = len(self.layers) - 1
        
        self.update_layer_list()
        
        if self.active_layer_index >= 0:
            self.layer_listbox.selection_set(self.active_layer_index)
            self.update_active_layer_display()
        
        self.log_info(f"Deleted layer: {layer_name}")
        self.combine_layers()
    
    def show_all_layers(self):
        """Делает все слои видимыми"""
        # Сохраняем состояние перед изменением
        self.save_state_for_undo("Show all layers")
        
        for layer in self.layers:
            layer.visible = True
        self.update_layer_list()
        self.combine_layers()
        self.toggle_visibility_btn.config(text="Hide")
        self.log_info("All layers visible")
    
    def hide_all_layers(self):
        """Скрывает все слои"""
        # Сохраняем состояние перед изменением
        self.save_state_for_undo("Hide all layers")
        
        for layer in self.layers:
            layer.visible = False
        self.update_layer_list()
        self.combine_layers()
        self.toggle_visibility_btn.config(text="Show")
        self.log_info("All layers hidden")
    
    def move_layer_up(self):
        """Перемещает активный слой вверх"""
        if self.active_layer_index > 0:
            # Сохраняем состояние перед изменением
            self.save_state_for_undo(f"Move layer up: {self.layers[self.active_layer_index].name}")
            
            self.layers[self.active_layer_index], self.layers[self.active_layer_index - 1] = \
                self.layers[self.active_layer_index - 1], self.layers[self.active_layer_index]
            self.active_layer_index -= 1
            self.update_layer_list()
            self.layer_listbox.selection_set(self.active_layer_index)
            self.combine_layers()
    
    def move_layer_down(self):
        """Перемещает активный слой вниз"""
        if self.active_layer_index < len(self.layers) - 1:
            # Сохраняем состояние перед изменением
            self.save_state_for_undo(f"Move layer down: {self.layers[self.active_layer_index].name}")
            
            self.layers[self.active_layer_index], self.layers[self.active_layer_index + 1] = \
                self.layers[self.active_layer_index + 1], self.layers[self.active_layer_index]
            self.active_layer_index += 1
            self.update_layer_list()
            self.layer_listbox.selection_set(self.active_layer_index)
            self.combine_layers()
    
    def clear_active_layer(self):
        """Очищает активный слой"""
        if self.active_layer_index == -1:
            return
            
        layer = self.layers[self.active_layer_index]
        
        # Сохраняем состояние перед очисткой
        self.save_state_for_undo(f"Clear layer: {layer.name}")
        
        layer.hex_string = ""
        layer.image_data = None
        layer.image_params = None
        layer.image_array = None
        
        self._hex_set('')
        self.update_layer_list()
        self.combine_layers()
        self.log_info(f"Cleared layer: {layer.name}")
        self.set_status(f"Layer cleared: {layer.name}")
    
    def save_project(self):
        """Сохраняет проект в файл JSON"""
        filename = filedialog.asksaveasfilename(
            title="Save Project",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                project_data = {
                    'layers': [layer.to_dict() for layer in self.layers],
                    'active_layer_index': self.active_layer_index
                }
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(project_data, f, indent=2)
                
                self.log_info(f"Project saved to: {filename}")
                self.set_status(f"Project saved")
                
            except Exception as e:
                messagebox.showerror("Save Error", f"Cannot save project: {str(e)}")
    
    def load_project(self):
        """Загружает проект из файла JSON"""
        filename = filedialog.askopenfilename(
            title="Load Project",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    project_data = json.load(f)
                
                # Очищаем текущие слои
                self.layers = []
                
                # Загружаем слои
                for layer_data in project_data['layers']:
                    layer = Layer.from_dict(layer_data)
                    
                    # Парсим hex-строку для восстановления изображения
                    if layer.hex_string:
                        image = self.display_image_from_hex(layer.hex_string)
                        if image is not None:
                            layer.image_array = image
                            layer.image_params = self.image_params
                            layer.image_data = self.current_image_data
                    
                    self.layers.append(layer)
                
                # Восстанавливаем активный слой
                self.active_layer_index = project_data.get('active_layer_index', 0)
                if self.active_layer_index >= len(self.layers):
                    self.active_layer_index = len(self.layers) - 1
                
                # Обновляем интерфейс
                self.update_layer_list()
                if self.active_layer_index >= 0:
                    self.layer_listbox.selection_set(self.active_layer_index)
                    self.update_active_layer_display()
                
                # Очищаем историю undo/redo
                self.clear_undo_history()
                
                self.log_info(f"Project loaded from: {filename}")
                self.set_status(f"Project loaded: {len(self.layers)} layers")
                
            except Exception as e:
                messagebox.showerror("Load Error", f"Cannot load project: {str(e)}")
    
    def flash_active_layer_border(self):
        """Кратковременно подсвечивает контур активного слоя яркой рамкой."""
        if self.active_layer_index == -1:
            return
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None:
            return

        x_start, block_start, x_end, block_end = layer.image_params
        sf = self.scale_factor
        width  = (x_end - x_start + 1)
        height = (block_end - block_start + 1) * 8

        x1 = x_start * sf
        y1 = block_start * 8 * sf
        x2 = (x_start + width)  * sf
        y2 = (block_start * 8 + height) * sf

        FLASH_COLOR  = '#00CFFF'   # яркий голубой
        FLASH_WIDTH  = 3
        STEPS        = 6           # кол-во мигания (чётное)
        INTERVAL_MS  = 80          # интервал между шагами

        def _step(n, rect_id):
            if n <= 0:
                # Убираем вспышку и перерисовываем обычные рамки
                self.canvas.delete(rect_id)
                self.draw_all_layer_borders()
                return
            # Чётный шаг — показываем, нечётный — прячем
            state = tk.NORMAL if (n % 2 == 0) else tk.HIDDEN
            self.canvas.itemconfig(rect_id, state=state)
            self.root.after(INTERVAL_MS, lambda: _step(n - 1, rect_id))

        # Удаляем старые рамки и рисуем вспышку
        self.canvas.delete('layer_border')
        rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline=FLASH_COLOR, width=FLASH_WIDTH,
            tags='layer_flash'
        )
        self.root.after(INTERVAL_MS, lambda: _step(STEPS, rect_id))

    # === КОМБИНИРОВАНИЕ СЛОЕВ ===
    
    def combine_layers(self):
        """Комбинирует все видимые слои в одно изображение"""
        combined = np.ones((self.screen_height, self.screen_width), dtype=np.uint8) * 255
        
        for layer in self.layers:
            if not layer.visible or layer.image_array is None:
                continue
            # Если размер не совпадает — пересоздаём
            if layer.image_array.shape != (self.screen_height, self.screen_width):
                if layer.image_params is not None:
                    self.recreate_layer_image(layer)
                # После пересоздания повторно проверяем — если всё ещё не совпадает, пропускаем
                if layer.image_array is None or \
                   layer.image_array.shape != (self.screen_height, self.screen_width):
                    continue
            mask = layer.image_array < 128
            combined[mask] = 0
        
        self.combined_image = combined
        self.display_on_canvas(combined)
        self.draw_all_layer_borders()
        self.draw_screen_border()
    
    def draw_all_layer_borders(self):
        """Рисует рамки всех видимых слоев разными цветами"""
        if not self.show_layer_borders.get():
            return
        colors = ['red', 'green', 'blue', 'purple', 'orange', 'cyan', 'magenta', 'yellow']
        
        for i, layer in enumerate(self.layers):
            if layer.visible and layer.image_params is not None:
                color = colors[i % len(colors)]
                self.draw_layer_border(layer, color)
    
    def draw_layer_border(self, layer, color='red'):
        """Рисует рамку для одного слоя"""
        if layer.image_params is None:
            return
            
        x_start, block_start, x_end, block_end = layer.image_params
        
        width = 0 - (x_start - x_end) + 1
        height = (0 - (block_start - block_end) + 1) * 8
        
        x1 = x_start * self.scale_factor
        y1 = block_start * 8 * self.scale_factor
        x2 = (x_start + width) * self.scale_factor
        y2 = (block_start * 8 + height) * self.scale_factor
        
        self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline=color, width=1, dash=(2, 2), tags='layer_border'
        )
        
        if width > 20 and height > 10:
            self.canvas.create_text(
                x1 + 5, y1 + 5,
                text=layer.name,
                fill=color,
                anchor=tk.NW,
                font=('Arial', 8, 'bold'),
                tags='layer_border'
            )
    
    def draw_screen_border(self):
        """Рисует контур границы экрана."""
        sf = self.scale_factor
        w = self.screen_width  * sf
        h = self.screen_height * sf
        self.canvas.create_rectangle(
            0, 0, w, h,
            outline='#888888', width=2, dash=(4, 4), tags='screen_border'
        )

    # === РЕДАКТИРОВАНИЕ (только активный слой) ===
    
    def enter_draw_mode(self):
        """Входит в режим рисования (или выходит если уже активен)."""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer to edit")
            return
        if self.edit_mode and self.current_color_index == 0:
            self.enter_move_mode()
        else:
            self.edit_mode = True
            self.shift_mode = False
            self.canvas.config(cursor="")
            self.current_color_index = 0
            self._update_edit_buttons()
            self.draw_grid()
            self.set_status(f"Draw mode — {self.layers[self.active_layer_index].name}")
            self.log_info("Draw mode enabled")

    def enter_erase_mode(self):
        """Входит в режим стирания (или выходит если уже активен)."""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer to edit")
            return
        if self.edit_mode and self.current_color_index == 1:
            self.enter_move_mode()
        else:
            self.edit_mode = True
            self.shift_mode = False
            self.canvas.config(cursor="")
            self.current_color_index = 1
            self._update_edit_buttons()
            self.draw_grid()
            self.set_status(f"Erase mode — {self.layers[self.active_layer_index].name}")
            self.log_info("Erase mode enabled")

    def enter_shift_mode(self):
        """Входит в режим сдвига пикселей (или выходит если уже активен)."""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer to edit")
            return
        if self.shift_mode:
            self.enter_move_mode()
            return
        self.shift_mode = True
        self.edit_mode = False
        self.canvas.config(cursor="fleur")
        self._update_edit_buttons()
        self.clear_grid()
        self.set_status("Shift Pixels mode — drag to shift content of layer")
        self.log_info("Shift pixels mode enabled")

    def enter_move_mode(self):
        """Выходит из режима редактирования — режим перемещения."""
        self.edit_mode = False
        self.shift_mode = False
        self.canvas.config(cursor="")
        self._update_edit_buttons()
        self.clear_grid()
        self.set_status("Move mode")
        self.log_info("Move mode enabled")

    def exit_edit_mode(self):
        """Алиас для совместимости."""
        self.enter_move_mode()

    def _update_edit_buttons(self):
        """Обновляет визуальное состояние кнопок Draw / Erase / Move / Shift."""
        self.draw_btn.config(relief=tk.RAISED)
        self.erase_btn.config(relief=tk.RAISED)
        self.move_btn.config(relief=tk.RAISED)
        self.shift_btn.config(relief=tk.RAISED)
        if self.shift_mode:
            self.shift_btn.config(relief=tk.SUNKEN)
        elif not self.edit_mode:
            self.move_btn.config(relief=tk.SUNKEN)
        elif self.current_color_index == 0:
            self.draw_btn.config(relief=tk.SUNKEN)
        else:
            self.erase_btn.config(relief=tk.SUNKEN)

    def _on_shift_start(self, event):
        """Начало drag в режиме сдвига пикселей."""
        if self.active_layer_index == -1:
            return
        layer = self.layers[self.active_layer_index]
        if layer.image_data is None or layer.image_params is None:
            return
        self._shift_start_x = self.canvas.canvasx(event.x)
        self._shift_start_y = self.canvas.canvasy(event.y)
        self._shift_orig_data = bytearray(layer.image_data)
        self._shift_applied_dx = 0
        self._shift_applied_dy = 0

    def _on_shift_motion(self, event):
        """Drag в режиме сдвига — предпросмотр в реальном времени."""
        if self._shift_orig_data is None:
            return
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        sf = self.scale_factor
        dx = int((cx - self._shift_start_x) / sf)
        dy = int((cy - self._shift_start_y) / sf)
        if dx == self._shift_applied_dx and dy == self._shift_applied_dy:
            return
        self._shift_applied_dx = dx
        self._shift_applied_dy = dy
        layer.image_data = self._shift_pixels(self._shift_orig_data,
                                               layer.image_params, dx, dy)
        self.recreate_layer_image(layer)
        self.update_layer_hex_string(layer)
        self.combine_layers()

    def _on_shift_release(self, event):
        """Завершение сдвига — фиксируем и пишем undo."""
        layer = self.layers[self.active_layer_index]
        if self._shift_applied_dx == 0 and self._shift_applied_dy == 0:
            self._shift_orig_data = None
            return
        orig_data = self._shift_orig_data
        self._shift_orig_data = None
        current_data = layer.image_data
        layer.image_data = orig_data
        state = {
            'description': f"Shift pixels in '{layer.name}' ({self._shift_applied_dx:+d}, {self._shift_applied_dy:+d})",
            'layers': [l.get_state_dict() for l in self.layers],
            'active_layer_index': self.active_layer_index,
            'timestamp': len(self.undo_stack)
        }
        layer.image_data = current_data
        self.undo_stack.append(state)
        if len(self.undo_stack) > self.max_undo_steps:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.update_undo_redo_buttons()
        self.log_info(f"Pixels shifted ({self._shift_applied_dx:+d}, {self._shift_applied_dy:+d}) in '{layer.name}'")
        self.set_status(f"Pixels shifted ({self._shift_applied_dx:+d}, {self._shift_applied_dy:+d})")
        self._shift_applied_dx = 0
        self._shift_applied_dy = 0

    def _shift_pixels(self, orig_data, image_params, dx, dy):
        """Сдвигает пиксели внутри bbox слоя. Пиксели за границей обрезаются."""
        x_start, block_start, x_end, block_end = image_params
        width  = x_end - x_start + 1
        height = (block_end - block_start + 1) * 8
        n_blocks = block_end - block_start + 1
        # Разворачиваем в 2D
        pixels = [[0] * width for _ in range(height)]
        for col in range(width):
            for blk in range(n_blocks):
                byte_idx = blk * width + col
                if byte_idx >= len(orig_data):
                    break
                byte_val = orig_data[byte_idx]
                for bit in range(8):
                    row = blk * 8 + bit
                    if row < height:
                        pixels[row][col] = 1 if (byte_val & (1 << bit)) else 0
        # Применяем сдвиг
        new_pixels = [[0] * width for _ in range(height)]
        for src_y in range(height):
            dst_y = src_y + dy
            if dst_y < 0 or dst_y >= height:
                continue
            for src_x in range(width):
                dst_x = src_x + dx
                if dst_x < 0 or dst_x >= width:
                    continue
                new_pixels[dst_y][dst_x] = pixels[src_y][src_x]
        # Сворачиваем обратно
        new_data = bytearray(len(orig_data))
        for col in range(width):
            for blk in range(n_blocks):
                byte_idx = blk * width + col
                if byte_idx >= len(new_data):
                    break
                byte_val = 0
                for bit in range(8):
                    row = blk * 8 + bit
                    if row < height and new_pixels[row][col]:
                        byte_val |= (1 << bit)
                new_data[byte_idx] = byte_val
        return new_data
    
    def on_canvas_click(self, event):
        """Обрабатывает клик на canvas в режиме редактирования"""
        if self.active_layer_index == -1:
            return
            
        # Получаем координаты с учетом прокрутки
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        
        # Вычисляем координаты пикселя
        x = int(x) // self.scale_factor
        y = int(y) // self.scale_factor
        
        # Проверяем границы
        if 0 <= x < self.screen_width and 0 <= y < self.screen_height:
            self.toggle_pixel(x, y)
    
    def toggle_pixel(self, x, y):
        """Переключает состояние пикселя в активном слое"""
        if self.active_layer_index == -1:
            return
            
        layer = self.layers[self.active_layer_index]
        
        try:
            if layer.image_params is None:
                return
                
            x_start, block_start, x_end, block_end = layer.image_params
            
            # Проверяем, находится ли пиксель в области вывода
            if (x_start <= x <= x_end and 
                block_start * 8 <= y <= block_end * 8 + 7):
                
                # Вычисляем смещения в данных
                width = 0 - (x_start - x_end) + 1
                height = (0 - (block_start - block_end) + 1) * 8
                
                # Вычисляем индекс столбца и строки блока
                col = x - x_start
                block_row = (y // 8) - block_start
                bit_pos = y % 8
                
                # Вычисляем индекс байта в данных
                byte_index = block_row * width + col
                
                if 0 <= byte_index < len(layer.image_data):
                    current_byte = layer.image_data[byte_index]
                    
                    # Draw (index=0) → бит=1 (чёрный), Erase (index=1) → бит=0 (белый)
                    if self.current_color_index == 0:
                        new_byte = current_byte | (1 << bit_pos)
                    else:
                        new_byte = current_byte & ~(1 << bit_pos)
                    layer.image_data[byte_index] = new_byte
                    
                    # Обновляем массив изображения
                    if new_byte & (1 << bit_pos):
                        layer.image_array[y, x] = 0  # Черный
                    else:
                        layer.image_array[y, x] = 255  # Белый
                    
                    # Обновляем hex-строку
                    self.update_layer_hex_string(layer)
                    
                    # Перерисовываем
                    self.combine_layers()
                    
                    self.log_info(f"Toggled pixel at ({x}, {y}) in {layer.name}")
                    
        except Exception as e:
            self.log_info(f"Error toggling pixel: {str(e)}")
    
    # === HEX ENTRY HELPERS ===

    def _hex_set(self, hex_string):
        """Вставляет hex-строку в поле с пробелами между байтами
        и подсветкой первых 4 байт (заголовок параметров)."""
        self.hex_entry.delete(1.0, tk.END)
        if not hex_string:
            return
        # Разбиваем на пары (байты) и вставляем с пробелами
        s = hex_string.upper()
        pairs = [s[i:i+2] for i in range(0, len(s), 2)]
        formatted = ' '.join(pairs)
        self.hex_entry.insert(1.0, formatted)
        # Подсвечиваем первые 4 байта: "XX XX XX XX" = 11 символов
        if len(pairs) >= 4:
            self.hex_entry.tag_add('header', '1.0', '1.11')

    def _hex_get(self):
        """Читает hex-строку из поля, удаляя пробелы, переносы и прочие разделители."""
        raw = self.hex_entry.get(1.0, tk.END)
        return ''.join(c for c in raw if c in '0123456789ABCDEFabcdef').upper()

    def update_layer_hex_string(self, layer):
        """Обновляет hex-строку слоя"""
        if layer.image_data is not None and layer.image_params is not None:
            new_byte_array = bytearray()
            new_byte_array.extend(layer.image_params)  # Добавляем обновленные параметры
            new_byte_array.extend(layer.image_data)    # Данные изображения остаются те же
            
            hex_string = new_byte_array.hex().upper()
            layer.hex_string = hex_string
            
            # Обновляем поле ввода если это активный слой
            if layer == self.layers[self.active_layer_index]:
                self._hex_set(hex_string)
    
    # === ОСНОВНЫЕ ФУНКЦИИ ===
    
    def zoom_in(self):
        if self.current_scale_index < len(self.scale_factors) - 1:
            self.current_scale_index += 1
            self.scale_factor = self.scale_factors[self.current_scale_index]
            self.update_zoom_display()
            if self.combined_image is not None:
                self.display_on_canvas(self.combined_image)
    
    def zoom_out(self):
        if self.current_scale_index > 0:
            self.current_scale_index -= 1
            self.scale_factor = self.scale_factors[self.current_scale_index]
            self.update_zoom_display()
            if self.combined_image is not None:
                self.display_on_canvas(self.combined_image)
    
    def update_zoom_display(self):
        self.zoom_label.config(text=f"{self.scale_factor}x")
    
    def copy_hex_to_clipboard(self):
        hex_string = self._hex_get()
        if hex_string:
            self.root.clipboard_clear()
            self.root.clipboard_append(hex_string)
            self.set_status("Hex string copied to clipboard")
            self.log_info("Hex string copied to clipboard")
    
    def paste_from_clipboard(self):
        try:
            clipboard_data = self.root.clipboard_get()
            if clipboard_data:
                clean_data = ''.join(c for c in clipboard_data if c in '0123456789ABCDEFabcdef').upper()
                if clean_data:
                    # Сохраняем состояние перед вставкой
                    self.save_state_for_undo("Paste hex data")
                    
                    self._hex_set(clean_data)
                    self.set_status("Pasted from clipboard")
        except:
            messagebox.showwarning("Warning", "Cannot access clipboard")
    
    def export_to_image(self):
        if self.combined_image is None:
            messagebox.showwarning("Warning", "No image to export")
            return
            
        filename = filedialog.asksaveasfilename(
            title="Export Combined Image",
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("BMP files", "*.bmp"),
                ("All files", "*.*")
            ]
        )
        
        if filename:
            try:
                img = Image.fromarray(self.combined_image)
                img.save(filename)
                self.log_info(f"Combined image exported to: {filename}")
                self.set_status(f"Image saved as {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Cannot save image: {str(e)}")
    
    def display_on_canvas(self, image_array):
        try:
            self.canvas.delete("all")
            
            canvas_width = self.screen_width * self.scale_factor
            canvas_height = self.screen_height * self.scale_factor
            self.canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))

            pil_image = Image.fromarray(image_array)
            display_size = (canvas_width, canvas_height)
            pil_image = pil_image.resize(display_size, Image.NEAREST)
            
            self.tk_image = ImageTk.PhotoImage(pil_image)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
            
            if self.edit_mode:
                self.draw_grid()
                
        except Exception as e:
            messagebox.showerror("Display Error", f"Cannot display image: {str(e)}")
    
    def draw_grid(self):
        self.clear_grid()
        
        # При малом масштабе сетка не нужна — пиксели и так не видны
        if self.scale_factor < 3:
            return
        
        canvas_width = self.screen_width * self.scale_factor
        canvas_height = self.screen_height * self.scale_factor
        
        for x in range(0, canvas_width + 1, self.scale_factor):
            self.canvas.create_line(x, 0, x, canvas_height, 
                                  fill='lightgray', width=1, tags='grid')
        
        for y in range(0, canvas_height + 1, self.scale_factor):
            self.canvas.create_line(0, y, canvas_width, y, 
                                  fill='lightgray', width=1, tags='grid')
    
    def clear_grid(self):
        for item in self.canvas.find_withtag('grid'):
            self.canvas.delete(item)
        # Перерисовываем рамки слоёв после скрытия сетки
        self.draw_all_layer_borders()
        self.draw_screen_border()
    
    def center_on_output_area(self):
        if self.active_layer_index == -1:
            return
            
        layer = self.layers[self.active_layer_index]
        if layer.image_params is None:
            return
            
        try:
            x_start, block_start, x_end, block_end = layer.image_params
            
            width = 0 - (x_start - x_end) + 1
            height = (0 - (block_start - block_end) + 1) * 8
            
            center_x = (x_start + width / 2) * self.scale_factor
            center_y = (block_start * 8 + height / 2) * self.scale_factor
            
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            x_pos = max(0, center_x - canvas_width / 2)
            y_pos = max(0, center_y - canvas_height / 2)
            
            self.canvas.xview_moveto(x_pos / (self.screen_width * self.scale_factor))
            self.canvas.yview_moveto(y_pos / (self.screen_height * self.scale_factor))
            
        except Exception as e:
            self.log_info(f"Error centering view: {str(e)}")
    
    def log_info(self, message):
        self.info_text.insert(tk.END, message + "\n")
        self.info_text.see(tk.END)
        self.root.update()
    
    def clear_info(self):
        self.info_text.delete(1.0, tk.END)
    
    def set_status(self, message):
        self.status_var.set(message)
        self.root.update()
    
    def open_file(self):
        """Открывает файл и загружает в активный слой"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
            
        filename = filedialog.askopenfilename(
            title="Open File",
            filetypes=[
                ("All files", "*.*"),
                ("Text files", "*.txt"),
                ("Hex files", "*.hex"),
                ("Binary files", "*.bin")
            ]
        )
        
        if filename:
            try:
                self.set_status(f"Loading file...")
                
                # Определяем тип файла
                if filename.lower().endswith(('.bin', '.dat')):
                    with open(filename, 'rb') as f:
                        data = f.read()
                    hex_string = data.hex().upper()
                else:
                    with open(filename, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    hex_string = ''.join(c for c in content if c in '0123456789ABCDEFabcdef').upper()
                
                # Сохраняем состояние перед загрузкой файла
                self.save_state_for_undo(f"Load file: {os.path.basename(filename)}")
                
                # Заполняем поле hex-строки
                self._hex_set(hex_string)
                
                # Автоматически обновляем слой если данных достаточно
                if len(hex_string) >= 8:
                    self.update_active_layer()
                
                self.log_info(f"Loaded file into active layer: {os.path.basename(filename)}")
                
            except Exception as e:
                messagebox.showerror("File Error", f"Cannot open file: {str(e)}")
    
    def load_image_file(self):
        """Загружает изображение в активный слой"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
            
        file_types = [
            ("Image files", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff"),
            ("PNG files", "*.png"),
            ("JPEG files", "*.jpg *.jpeg"),
            ("BMP files", "*.bmp"),
            ("All files", "*.*")
        ]
        
        filename = filedialog.askopenfilename(
            title="Load Image File",
            filetypes=file_types
        )
        
        if filename:
            try:
                self.set_status("Loading and processing image...")
                self.log_info("=" * 50)
                self.log_info(f"LOADING IMAGE FOR LAYER: {self.layers[self.active_layer_index].name}")
                self.log_info("=" * 50)
                
                with Image.open(filename) as img:
                    img_gray = img.convert('L')
                    orig_width, orig_height = img_gray.size
                    self.log_info(f"Original image size: {orig_width}x{orig_height}")
                    
                    hex_data = self.show_image_import_settings(img_gray, filename)
                    
                    if hex_data:
                        # Сохраняем состояние перед загрузкой изображения
                        self.save_state_for_undo(f"Load image: {os.path.basename(filename)}")
                        
                        self._hex_set(hex_data)
                        self.log_info(f"Image converted to hex string ({len(hex_data)//2} bytes)")
                        
                        self.update_active_layer()
                        
            except Exception as e:
                messagebox.showerror("Image Error", f"Cannot load image: {str(e)}")
    
    def create_new_image(self):
        """Создает новое изображение в активном слое"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
            
        new_window = tk.Toplevel(self.root)
        new_window.title("Create New Image")
        new_window.geometry("400x350")
        new_window.transient(self.root)
        new_window.grab_set()

        # Вычисляем лимиты из текущего размера экрана (max 256)
        max_x    = min(self.screen_width, 256) - 1     # макс X позиция
        max_w    = min(self.screen_width, 256)          # макс ширина
        max_yblk = min(self.screen_height // 8, 255) - 1  # макс Y блок
        max_blks = min(self.screen_height // 8, 255)    # макс блоков
        
        input_frame = ttk.Frame(new_window, padding="25")
        input_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        ttk.Label(input_frame, text="Create New Image", font=('Arial', 14, 'bold')).grid(
            row=0, column=0, columnspan=2, pady=(0, 25))
        
        ttk.Label(input_frame, text=f"Width (1-{max_w}):", font=('Arial', 10)).grid(
            row=1, column=0, sticky=tk.W, pady=8)
        width_var = tk.IntVar(value=min(40, max_w))
        width_spin = ttk.Spinbox(input_frame, from_=1, to=max_w, width=12,
                               textvariable=width_var, font=('Arial', 10))
        width_spin.grid(row=1, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        
        ttk.Label(input_frame, text=f"Height in blocks (1-{max_blks}):", font=('Arial', 10)).grid(
            row=2, column=0, sticky=tk.W, pady=8)
        blocks_var = tk.IntVar(value=min(5, max_blks))
        blocks_spin = ttk.Spinbox(input_frame, from_=1, to=max_blks, width=12,
                                textvariable=blocks_var, font=('Arial', 10))
        blocks_spin.grid(row=2, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        
        ttk.Label(input_frame, text=f"X Position (0-{max_x}):", font=('Arial', 10)).grid(
            row=3, column=0, sticky=tk.W, pady=8)
        x_pos_var = tk.IntVar(value=min(60, max_x))
        x_pos_spin = ttk.Spinbox(input_frame, from_=0, to=max_x, width=12,
                               textvariable=x_pos_var, font=('Arial', 10))
        x_pos_spin.grid(row=3, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        
        ttk.Label(input_frame, text=f"Y Block (0-{max_yblk}):", font=('Arial', 10)).grid(
            row=4, column=0, sticky=tk.W, pady=8)
        y_block_var = tk.IntVar(value=min(7, max_yblk))
        y_block_spin = ttk.Spinbox(input_frame, from_=0, to=max_yblk, width=12,
                                 textvariable=y_block_var, font=('Arial', 10))
        y_block_spin.grid(row=4, column=1, sticky=tk.W, pady=8, padx=(10, 0))
        
        def create_image():
            width  = width_var.get()
            blocks = blocks_var.get()
            x_pos  = x_pos_var.get()
            y_block = y_block_var.get()
            
            if x_pos + width > max_w:
                messagebox.showerror("Error", f"X + Width must not exceed {max_w}")
                return
            if y_block + blocks > max_blks:
                messagebox.showerror("Error", f"Y Block + Height must not exceed {max_blks}")
                return
            
            # Сохраняем состояние перед созданием изображения
            self.save_state_for_undo("Create new image")
            
            # Создаем hex-строку
            x_start = x_pos
            x_end = x_pos + width - 1
            block_start = y_block
            block_end = y_block + blocks - 1
            
            data_size = width * blocks
            hex_data = f"{x_start:02X}{block_start:02X}{x_end:02X}{block_end:02X}" + "00" * data_size
            
            # Заполняем hex-строку
            self._hex_set(hex_data)
            
            new_window.destroy()
            self.update_active_layer()
            self.log_info(f"Created new image: {width}x{blocks*8} at ({x_pos},{y_block*8})")
            
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=25)
        
        ttk.Button(btn_frame, text="Create Image", command=create_image, 
                 width=15).grid(row=0, column=0, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=new_window.destroy, 
                 width=15).grid(row=0, column=1, padx=10)
        
        new_window.columnconfigure(0, weight=1)
        new_window.rowconfigure(0, weight=1)
        input_frame.columnconfigure(1, weight=1)
    
    def update_active_layer(self):
        """Обновляет активный слой из hex-строки"""
        if self.active_layer_index == -1:
            messagebox.showwarning("Warning", "No active layer selected")
            return
            
        hex_string = self._hex_get()
        
        if not hex_string:
            messagebox.showerror("Error", "Please enter a hex string")
            return
            
        try:
            self.clear_info()
            self.set_status("Updating active layer...")
            self.log_info("=" * 50)
            self.log_info(f"UPDATING LAYER: {self.layers[self.active_layer_index].name}")
            self.log_info("=" * 50)
            
            # Сохраняем состояние перед обновлением
            self.save_state_for_undo(f"Update layer: {self.layers[self.active_layer_index].name}")
            
            layer = self.layers[self.active_layer_index]
            layer.hex_string = hex_string
            
            image = self.display_image_from_hex(hex_string)
            if image is not None:
                layer.image_array = image
                layer.image_params = self.image_params
                layer.image_data = self.current_image_data
                
                self.set_status(f"Layer updated: {layer.name}")
                self.combine_layers()
                self.center_on_output_area()
                self.update_layer_list()
                
            else:
                self.set_status("Failed to update layer")
                
        except Exception as e:
            messagebox.showerror("Error", f"Processing failed: {str(e)}")
            self.set_status("Update error")
    
    # === ФУНКЦИИ ДЛЯ РАБОТЫ С HEX ===
    
    def display_image_from_hex(self, hex_string):
        """Функция для отображения изображения из hex-строки"""
        try:
            byte_array = bytearray.fromhex(hex_string)
            self.log_info(f"Loaded bytes: {len(byte_array)}")
            
            if len(byte_array) < 4:
                self.log_info("Error: Not enough data for parameters")
                return None
                
            x_start = byte_array[0]
            block_start = byte_array[1]
            x_end = byte_array[2]
            block_end = byte_array[3]
            
            self.image_params = (x_start, block_start, x_end, block_end)
            self.current_image_data = bytearray(byte_array[4:])
            
            self.log_info("Image Parameters:")
            self.log_info(f"  x_start: {x_start} (0x{x_start:02X})")
            self.log_info(f"  block_start: {block_start} (0x{block_start:02X})")
            self.log_info(f"  x_end: {x_end} (0x{x_end:02X})")
            self.log_info(f"  block_end: {block_end} (0x{block_end:02X})")
            
            width = 0 - (x_start - x_end) + 1
            height = (0 - (block_start - block_end) + 1) * 8
            
            self.log_info(f"Output Area: {width}x{height} pixels")
            self.log_info(f"Position: X={x_start}-{x_end}, Blocks Y={block_start}-{block_end}")
            self.log_info(f"Absolute Y: {block_start*8}-{block_end*8+7}")
            
            image_data = byte_array[4:]
            self.log_info(f"Image data: {len(image_data)} bytes")
            
            expected_data_size = width * (height // 8)
            self.log_info(f"Expected data: {expected_data_size} bytes")
            
            if len(image_data) < expected_data_size:
                self.log_info(f"Error: Not enough data. Need {expected_data_size}, have {len(image_data)}")
                return None
                
            screen = np.ones((self.screen_height, self.screen_width), dtype=np.uint8) * 255
            
            data_index = 0
            self.log_info("Reconstructing image...")
            
            for block_row in range(height // 8):
                y_block_pos = block_start + block_row
                y_start = y_block_pos * 8
                
                for col in range(width):
                    x_pos = x_start + col
                    
                    if data_index >= len(image_data):
                        break
                    
                    byte_val = image_data[data_index]
                    data_index += 1
                    
                    for bit in range(8):
                        y_pos = y_start + bit
                        
                        if 0 <= x_pos < self.screen_width and 0 <= y_pos < self.screen_height:
                            if byte_val & (1 << bit):
                                screen[y_pos, x_pos] = 0
                                
            self.log_info(f"Done! Used {data_index} bytes of data")
            return screen
            
        except Exception as e:
            self.log_info(f"Error: {str(e)}")
            return None
    
    def show_image_import_settings(self, img, filename):
        """Окно настроек импорта изображения"""
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Import Image Settings")
        settings_window.geometry("550x700")
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        result = [None]
        
        preview_frame = ttk.LabelFrame(settings_window, text="Preview", padding="10")
        preview_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        img_preview = img.resize((200, 200), Image.Resampling.LANCZOS)
        tk_img = ImageTk.PhotoImage(img_preview)
        
        img_label = tk.Label(preview_frame, image=tk_img)
        img_label.image = tk_img
        img_label.grid(row=0, column=0)
        
        info_frame = ttk.Frame(settings_window)
        info_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=5)
        
        ttk.Label(info_frame, text=f"File: {os.path.basename(filename)}", 
                font=('Arial', 9)).grid(row=0, column=0, sticky=tk.W)
        ttk.Label(info_frame, text=f"Size: {img.size[0]}x{img.size[1]} pixels", 
                font=('Arial', 9)).grid(row=1, column=0, sticky=tk.W, pady=2)
        
        settings_frame = ttk.LabelFrame(settings_window, text="Import Settings", padding="15")
        settings_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=10, pady=10)
        
        ttk.Label(settings_frame, text="Threshold (0-255):", 
                font=('Arial', 10)).grid(row=0, column=0, sticky=tk.W, pady=8)
        threshold_var = tk.IntVar(value=128)
        threshold_scale = ttk.Scale(settings_frame, from_=0, to=255, 
                                  variable=threshold_var, orient=tk.HORIZONTAL, length=200)
        threshold_scale.grid(row=0, column=1, sticky=tk.W, pady=8, padx=10)
        threshold_val_label = ttk.Label(settings_frame, text="128", width=3)
        threshold_val_label.grid(row=0, column=2, sticky=tk.W, pady=8)
        
        def update_threshold_label(*args):
            threshold_val_label.config(text=str(threshold_var.get()))
        
        threshold_var.trace('w', update_threshold_label)
        
        invert_var = tk.BooleanVar(value=True)
        invert_cb = ttk.Checkbutton(settings_frame, text="Invert colors (black=1)", 
                                  variable=invert_var)
        invert_cb.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=8)
        
        ttk.Label(settings_frame, text="Output Area:", 
                font=('Arial', 10, 'bold')).grid(row=2, column=0, columnspan=3, 
                                               sticky=tk.W, pady=(15, 8))

        # Динамические лимиты из текущего размера экрана (max 256)
        max_x_imp    = min(self.screen_width, 256) - 1
        max_yblk_imp = min(self.screen_height // 8, 255) - 1

        ttk.Label(settings_frame, text=f"X Position (0-{max_x_imp}):", 
                font=('Arial', 9)).grid(row=3, column=0, sticky=tk.W, pady=4)
        x_pos_var = tk.IntVar(value=0)
        x_pos_spin = ttk.Spinbox(settings_frame, from_=0, to=max_x_imp, width=10,
                               textvariable=x_pos_var, font=('Arial', 9))
        x_pos_spin.grid(row=3, column=1, sticky=tk.W, pady=4, padx=10)
        
        ttk.Label(settings_frame, text=f"Y Block (0-{max_yblk_imp}):", 
                font=('Arial', 9)).grid(row=4, column=0, sticky=tk.W, pady=4)
        y_block_var = tk.IntVar(value=0)
        y_block_spin = ttk.Spinbox(settings_frame, from_=0, to=max_yblk_imp, width=10,
                                 textvariable=y_block_var, font=('Arial', 9))
        y_block_spin.grid(row=4, column=1, sticky=tk.W, pady=4, padx=10)
        
        btn_frame = ttk.Frame(settings_window)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=20)
        
        def convert_and_close():
            try:
                hex_data = self.convert_image_to_hex(
                    img, 
                    threshold=threshold_var.get(),
                    invert=invert_var.get(),
                    x_pos=x_pos_var.get(),
                    y_block=y_block_var.get()
                )
                result[0] = hex_data
                settings_window.destroy()
            except Exception as e:
                messagebox.showerror("Conversion Error", f"Failed to convert image: {str(e)}")
        
        ttk.Button(btn_frame, text="Convert to Hex", command=convert_and_close, 
                 width=20).grid(row=0, column=0, padx=10)
        ttk.Button(btn_frame, text="Cancel", command=settings_window.destroy, 
                 width=20).grid(row=0, column=1, padx=10)
        
        settings_window.columnconfigure(0, weight=1)
        settings_window.wait_window()
        
        return result[0]
    
    def convert_image_to_hex(self, img, threshold=128, invert=False, x_pos=0, y_block=0):
        """Конвертирует изображение в hex-строку"""
        img_array = np.array(img)
        
        if invert:
            binary_array = (img_array < threshold).astype(np.uint8)
        else:
            binary_array = (img_array >= threshold).astype(np.uint8)
        
        height, width = binary_array.shape
        
        max_width  = self.screen_width - x_pos
        max_height = (255 - y_block) * 8
        
        if width > max_width:
            width = max_width
            binary_array = binary_array[:, :width]
        
        if height > max_height:
            height = max_height
            binary_array = binary_array[:height, :]
        
        x_start = x_pos
        x_end = x_start + width - 1
        block_start = y_block
        block_end = block_start + ((height - 1) // 8)
        
        byte_array = bytearray()
        byte_array.append(x_start)
        byte_array.append(block_start)
        byte_array.append(x_end)
        byte_array.append(block_end)
        
        for block_row in range(block_start, block_end + 1):
            y_start = block_row * 8
            y_end = min(y_start + 8, height)
            
            for col in range(width):
                byte_val = 0
                for y in range(y_start, y_end):
                    if y < height:
                        bit_pos = y - y_start
                        if binary_array[y, col]:
                            byte_val |= (1 << bit_pos)
                
                byte_array.append(byte_val)
        
        hex_string = byte_array.hex().upper()
        
        self.log_info("=" * 50)
        self.log_info("IMAGE CONVERSION RESULT")
        self.log_info("=" * 50)
        self.log_info(f"Threshold: {threshold}")
        self.log_info(f"Invert: {invert}")
        self.log_info(f"Output area: ({x_start},{block_start*8}) to ({x_end},{block_end*8+7})")
        self.log_info(f"Size: {width}x{height} pixels")
        self.log_info(f"Hex length: {len(hex_string)} chars ({len(byte_array)} bytes)")
        
        return hex_string

def main():
    root = tk.Tk()
    app = ImageDisplayApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()