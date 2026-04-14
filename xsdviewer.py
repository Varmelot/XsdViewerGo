import sys
import os
from lxml import etree
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem, 
                             QVBoxLayout, QWidget, QFileDialog, QLabel, QHBoxLayout, 
                             QToolBar, QStyledItemDelegate, QStyle, QHeaderView, 
                             QLineEdit, QSplitter, QTableWidget, QTableWidgetItem)
from PyQt6.QtGui import QColor, QBrush, QAction, QFont, QPalette, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QRect

class XsdColorDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.search_term = ""

    def paint(self, painter, option, index):
        painter.save()
        bg_hex = index.data(Qt.ItemDataRole.UserRole)
        bg_color = QColor(bg_hex) if bg_hex else QColor("#FFFFFF")
        
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
            painter.setPen(Qt.GlobalColor.white)
        else:
            painter.fillRect(option.rect, bg_color)
            painter.setPen(Qt.GlobalColor.black)

        font = QFont(option.font)
        font.setBold(True if index.column() == 0 else False)
        painter.setFont(font)

        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        margin = int(painter.fontMetrics().horizontalAdvance(' ') * 4) if index.column() == 0 else 8
        text_rect = option.rect.adjusted(margin, 0, -5, 0)
        
        if self.search_term and self.search_term.lower() in text.lower():
            fm = painter.fontMetrics()
            current_x = text_rect.x()
            y = text_rect.y()
            h = text_rect.height()
            lower_text = text.lower()
            st_lower = self.search_term.lower()
            st_len = len(st_lower)
            start = 0
            
            while True:
                idx = lower_text.find(st_lower, start)
                if idx == -1:
                    rem = text[start:]
                    if rem:
                        painter.drawText(QRect(current_x, y, text_rect.right() - current_x, h), 
                                         Qt.AlignmentFlag.AlignVCenter, rem)
                    break
                p1 = text[start:idx]
                if p1:
                    painter.drawText(QRect(current_x, y, text_rect.right() - current_x, h), 
                                     Qt.AlignmentFlag.AlignVCenter, p1)
                    current_x += fm.horizontalAdvance(p1)
                p2 = text[idx:idx+st_len]
                w2 = fm.horizontalAdvance(p2)
                hl_rect = QRect(current_x, y + (h - fm.height()) // 2, w2, fm.height())
                painter.fillRect(hl_rect, QColor("#FFCA28"))
                painter.save()
                painter.setPen(Qt.GlobalColor.black)
                painter.drawText(QRect(current_x, y, w2, h), Qt.AlignmentFlag.AlignVCenter, p2)
                painter.restore()
                current_x += w2
                start = idx + st_len
        else:
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        
        painter.setPen(QColor("#CCCCCC"))
        painter.drawRect(option.rect)
        painter.restore()

class XSDViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        self.xsd_ns = "http://www.w3.org/2001/XMLSchema"
        self.files_map = {} 
        self.types_registry = {} 
        self.elements_registry = {} 
        self.color_palette = ["#FCE4EC", "#E8F5E9", "#FFFDE7", "#E1F5FE", "#EDE7F6", "#E0F7FA", "#FFF3E0", "#ECEFF1"]
        self.color_idx = 0
        self.current_font_size = 10
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("XSD Viewer Pro")
        self.resize(1500, 900)
        
        # --- ТУЛБАРЫ ---
        tb = self.addToolBar("Main")
        tb.setMovable(False)
        open_act = QAction("📁 Open XSD", self)
        open_act.triggered.connect(self.select_file)
        tb.addAction(open_act)
        tb.addSeparator()
        expand_act = QAction("➕ Expand", self)
        expand_act.triggered.connect(lambda: self.tree.expandAll())
        tb.addAction(expand_act)
        collapse_act = QAction("➖ Collapse", self)
        collapse_act.triggered.connect(lambda: self.tree.collapseAll())
        tb.addAction(collapse_act)
        tb.addSeparator()
        zoom_in_act = QAction("🔍+", self)
        zoom_in_act.triggered.connect(lambda: self.change_zoom(1))
        tb.addAction(zoom_in_act)
        zoom_out_act = QAction("🔍-", self)
        zoom_out_act.triggered.connect(lambda: self.change_zoom(-1))
        tb.addAction(zoom_out_act)

        self.addToolBarBreak()
        search_tb = self.addToolBar("Search")
        search_tb.setMovable(False)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Быстрый поиск по всем колонкам...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 6px; border: 1px solid #777; border-radius: 4px;
                background-color: white; color: black; font-size: 14px; margin: 4px 10px;
            }
        """)
        self.search_input.textChanged.connect(self.search_tree)
        search_tb.addWidget(self.search_input)
        
        # --- ГЛАВНЫЙ ВИДЖЕТ И СЛОИ ---
        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        
        self.legend_layout = QHBoxLayout()
        self.legend_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.main_layout.addLayout(self.legend_layout)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Structure", "Type / Occurs", "Annotation"])
        self.tree.setColumnWidth(0, 450)
        self.tree.setColumnWidth(1, 250)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.delegate = XsdColorDelegate()
        self.tree.setItemDelegate(self.delegate)
        self.tree.itemSelectionChanged.connect(self.update_sidebar)
        
        self.side_panel = QTableWidget()
        self.side_panel.setColumnCount(2)
        self.side_panel.setHorizontalHeaderLabels(["Attribute", "Value"])
        self.side_panel.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.side_panel.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        self.tree.header().setStyleSheet("""
            QHeaderView::section { background-color: #333; color: white; font-weight: bold; border: 1px solid #111; padding: 4px;}
        """)
        self.tree.setStyleSheet("QTreeView { background-color: white; border: none; }")

        self.side_panel.setStyleSheet("""
            QTableWidget { background-color: #FFFFFF; color: #000000; gridline-color: #DDDDDD; border: none; }
            QTableWidget::item:selected { background-color: #0078D7; color: #FFFFFF; }
            QHeaderView::section { background-color: #333333; color: #FFFFFF; font-weight: bold; border: 1px solid #111111; padding: 4px; }
        """)
        
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.side_panel)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.main_layout.addWidget(self.splitter, 1)

        self.update_tree_font()

        # --- ГОРЯЧИЕ КЛАВИШИ И СТАТУС БАР ---
        QShortcut(QKeySequence("Ctrl++"), self, lambda: self.change_zoom(1))
        QShortcut(QKeySequence("Ctrl+-"), self, lambda: self.change_zoom(-1))
        QShortcut(QKeySequence("Ctrl+0"), self, lambda: self.change_zoom(0))
        QShortcut(QKeySequence("Ctrl+F"), self, lambda: self.search_input.setFocus())
        QShortcut(QKeySequence("F2"), self, self.copy_node_name)
        
        self.statusBar().showMessage("Готово к работе. Выберите файл или передайте его параметром.")

    def copy_node_name(self):
        selected = self.tree.selectedItems()
        if not selected: return
        
        raw_text = selected[0].text(0)
        clean_name = raw_text.replace("● ", "")
        clean_name = clean_name.split(" (")[0].strip()
        clean_name = clean_name.lstrip("@")
        
        if clean_name:
            QApplication.clipboard().setText(clean_name)
            self.statusBar().showMessage(f"Скопировано в буфер: {clean_name}", 4000)

    def update_sidebar(self):
        self.side_panel.setRowCount(0)
        selected = self.tree.selectedItems()
        if not selected: return
        
        item = selected[0]
        attrs = item.data(0, Qt.ItemDataRole.UserRole + 1) or {}
        
        self.side_panel.setRowCount(len(attrs))
        for row, (name, val) in enumerate(sorted(attrs.items())):
            self.side_panel.setItem(row, 0, QTableWidgetItem(name))
            self.side_panel.setItem(row, 1, QTableWidgetItem(str(val)))

    def get_schema_attributes(self, node):
        res = []
        for child in node.iterchildren():
            if not isinstance(child.tag, str): continue
            tag = child.tag.split('}')[-1]
            if tag == 'attribute':
                res.append(child)
            elif tag in ['complexType', 'simpleContent', 'complexContent', 'extension', 'restriction']:
                res.extend(self.get_schema_attributes(child))
        return res

    def get_all_attributes(self, xml_node, type_str):
        data = {}
        for k, v in xml_node.attrib.items():
            if k in ['name', 'ref']: continue
            data[k] = v
            
        if type_str:
            uri, local = self.get_ns_info(type_str, xml_node)
            res = self.types_registry.get((uri, local))
            if res:
                type_node = res[0]
                facets = type_node.xpath(".//xs:restriction/* | .//xs:extension/*", namespaces=self.ns)
                for f in facets:
                    tag = f.tag.split('}')[-1]
                    if tag in ['pattern', 'minLength', 'maxLength', 'minInclusive', 'maxInclusive', 'totalDigits', 'fractionDigits']:
                        data[tag] = f.get('value')
                    elif tag == 'enumeration':
                        existing = data.get('enumeration', "")
                        val = f.get('value')
                        data['enumeration'] = f"{existing}, {val}" if existing else val
        return data

    def create_attribute_node(self, attr_node, ui_parent, current_file):
        name = attr_node.get('name')
        if not name and attr_node.get('ref'):
            uri, local = self.get_ns_info(attr_node.get('ref'), attr_node)
            name = local
            
        if not name: return

        display_name = f"@{name}"
        type_str = attr_node.get('type', '')
        use_str = attr_node.get('use', 'optional')
        occ = f"[{use_str}]"

        bg_color = self.files_map.get(os.path.abspath(current_file), "#FFFFFF")
        if type_str:
            uri, local = self.get_ns_info(type_str, attr_node)
            if uri == self.xsd_ns: bg_color = "#FFFFFF" 
            else:
                res = self.types_registry.get((uri, local))
                if res: bg_color = self.files_map.get(os.path.abspath(res[1]), "#FFFFFF")

        item = QTreeWidgetItem(ui_parent)
        item.setText(0, display_name)
        item.setText(1, f"{type_str} {occ}" if type_str else occ)
        anno = attr_node.xpath("./xs:annotation/xs:documentation/text()", namespaces=self.ns)
        item.setText(2, " ".join(" ".join(anno).split()) if anno else "")

        attr_data = {}
        for k, v in attr_node.attrib.items():
            if k in ['name', 'ref']: continue
            attr_data[k] = v 
        item.setData(0, Qt.ItemDataRole.UserRole + 1, attr_data)

        for i in range(3): item.setData(i, Qt.ItemDataRole.UserRole, bg_color)

    def create_node(self, xml_node, ui_parent, current_file, visited=None, prefix=""):
        if visited is None: visited = set()
        
        name = xml_node.get('name')
        if not name and xml_node.get('ref'):
            uri, local = self.get_ns_info(xml_node.get('ref'), xml_node)
            res = self.elements_registry.get((uri, local))
            if res: xml_node, current_file, name = res[0], res[1], res[0].get('name')
        
        name = name or f"[{xml_node.tag.split('}')[-1]}]"

        is_collapsed = False
        inner_item = None
        if name.endswith('List'):
            cts = xml_node.xpath("./xs:complexType", namespaces=self.ns)
            if len(cts) == 1:
                seqs = cts[0].xpath("./xs:sequence", namespaces=self.ns)
                if len(seqs) == 1:
                    elems = seqs[0].xpath("./xs:element", namespaces=self.ns)
                    if len(elems) == 1: is_collapsed, inner_item = True, elems[0]

        if is_collapsed:
            inner_file = current_file
            if not inner_item.get('name') and inner_item.get('ref'):
                uri, local = self.get_ns_info(inner_item.get('ref'), inner_item)
                res = self.elements_registry.get((uri, local))
                if res: inner_item, inner_file = res
            child_name = inner_item.get('name') or "[anonymous]"
            display_name, type_str = f"{prefix}{name} ({child_name})", inner_item.get('type', '')
            occ = f"[{inner_item.get('minOccurs','1')}..{inner_item.get('maxOccurs','unbounded')}]"
            target_node, target_file = inner_item, inner_file
        else:
            display_name, type_str = f"{prefix}{name}", xml_node.get('type', '')
            occ = f"[{xml_node.get('minOccurs','1')}..{xml_node.get('maxOccurs','1')}]"
            target_node, target_file = xml_node, current_file

        bg_color = self.files_map.get(os.path.abspath(target_file), "#FFFFFF")
        if type_str:
            uri, local = self.get_ns_info(type_str, target_node)
            if uri == self.xsd_ns: bg_color = "#FFFFFF" 
            else:
                res = self.types_registry.get((uri, local))
                if res: bg_color = self.files_map.get(os.path.abspath(res[1]), "#FFFFFF")

        item = QTreeWidgetItem(ui_parent)
        item.setText(0, display_name)
        item.setText(1, f"{type_str} {occ}" if type_str else occ)
        anno = xml_node.xpath("./xs:annotation/xs:documentation/text()", namespaces=self.ns)
        item.setText(2, " ".join(" ".join(anno).split()) if anno else "")

        all_attrs = self.get_all_attributes(target_node, type_str)
        item.setData(0, Qt.ItemDataRole.UserRole + 1, all_attrs)

        for i in range(3): item.setData(i, Qt.ItemDataRole.UserRole, bg_color)
        self.find_children(target_node, item, target_file, visited, type_str)

    def search_tree(self, text):
        self.delegate.search_term = text
        self.tree.viewport().update()
        text_lower = text.lower()
        def filter_node(item):
            match = any(text_lower in item.text(col).lower() for col in range(3)) if text_lower else True
            child_match = any(filter_node(item.child(i)) for i in range(item.childCount()))
            item.setHidden(not (match or child_match))
            if text_lower and (match or child_match): item.setExpanded(True)
            return match or child_match
        for i in range(self.tree.topLevelItemCount()): filter_node(self.tree.topLevelItem(i))
        if not text_lower:
            self.tree.collapseAll()
            for i in range(self.tree.topLevelItemCount()): self.tree.topLevelItem(i).setExpanded(True)

    def change_zoom(self, delta):
        if delta == 0: self.current_font_size = 10
        else: self.current_font_size = max(6, min(40, self.current_font_size + delta))
        self.update_tree_font()

    def update_tree_font(self):
        font = QFont("Ubuntu", self.current_font_size)
        self.tree.setFont(font)
        self.tree.setStyleSheet(f"QTreeView::item {{ height: {self.current_font_size * 2.5}px; }}")
        self.tree.setColumnWidth(0, int(self.current_font_size * 45))
        self.tree.setColumnWidth(1, int(self.current_font_size * 25))
        self.side_panel.setFont(font)
        self.side_panel.verticalHeader().setDefaultSectionSize(int(self.current_font_size * 2.5))

    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select XSD", "", "XSD (*.xsd)")
        if path:
            self.load_file(path)

    def load_file(self, path):
        """Новый метод для загрузки файла по переданному пути"""
        if not os.path.exists(path):
            self.statusBar().showMessage(f"Ошибка: Файл не найден - {path}", 5000)
            return

        self.tree.clear()
        self.side_panel.setRowCount(0)
        self.search_input.clear()
        self.files_map.clear()
        self.types_registry.clear()
        self.elements_registry.clear()
        self.color_idx = 0
        
        while self.legend_layout.count():
            item = self.legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None: widget.deleteLater()

        try:
            self.scan_schema(path)
            self.render_legend()
            
            root_doc = etree.parse(path)
            for el in root_doc.getroot().xpath("./xs:element", namespaces=self.ns):
                self.create_node(el, self.tree, path)
            self.tree.expandAll()
            self.statusBar().showMessage(f"Файл успешно загружен: {os.path.basename(path)}", 5000)
        except Exception as e:
            self.statusBar().showMessage(f"Ошибка парсинга XSD: {str(e)}", 5000)

    def scan_schema(self, path):
        path = os.path.abspath(path)
        if path in self.files_map: return
        self.files_map[path] = self.color_palette[self.color_idx % len(self.color_palette)]
        self.color_idx += 1
        try:
            tree = etree.parse(path)
            root = tree.getroot()
            tns = root.get('targetNamespace')
            for node in root.xpath("./xs:complexType | ./xs:simpleType | ./xs:element", namespaces=self.ns):
                name = node.get('name')
                if not name: continue
                if node.tag.endswith('element'): self.elements_registry[(tns, name)] = (node, path)
                else: self.types_registry[(tns, name)] = (node, path)
            base_dir = os.path.dirname(path)
            for imp in root.xpath("./xs:import | ./xs:include", namespaces=self.ns):
                loc = imp.get('schemaLocation')
                if loc:
                    full_path = os.path.normpath(os.path.join(base_dir, loc))
                    if os.path.exists(full_path): self.scan_schema(full_path)
        except: pass

    def get_ns_info(self, qname, node):
        if not qname: return None, None
        prefix, local = qname.split(':') if ':' in qname else (None, qname)
        uri = node.nsmap.get(prefix) if prefix else node.xpath("ancestor::xs:schema/@targetNamespace", namespaces=self.ns)[0]
        return uri, local

    def is_choice_variant(self, node):
        p = node.getparent()
        while p is not None:
            tag = p.tag.split('}')[-1]
            if tag == 'choice': return True
            if tag in ['element', 'complexType', 'schema']: return False
            p = p.getparent()
        return False

    def get_child_elements(self, node):
        elems = []
        for child in node.iterchildren():
            if not isinstance(child.tag, str): continue
            tag = child.tag.split('}')[-1]
            if tag == 'element': elems.append(child)
            elif tag in ['sequence', 'choice', 'all']: elems.extend(self.get_child_elements(child))
        return elems

    def find_children(self, node, ui_item, current_file, visited, type_str):
        for ct in node.xpath("./xs:complexType", namespaces=self.ns):
            self.process_structure(ct, ui_item, current_file, visited)
        if type_str:
            uri, local = self.get_ns_info(type_str, node)
            res = self.types_registry.get((uri, local))
            if res and type_str not in visited:
                visited.add(type_str)
                self.process_structure(res[0], ui_item, res[1], visited)
                visited.remove(type_str)

    def process_structure(self, struct_node, ui_item, current_file, visited):
        for ext in struct_node.xpath("./xs:complexContent/xs:extension | ./xs:simpleContent/xs:extension", namespaces=self.ns):
            uri, local = self.get_ns_info(ext.get('base'), ext)
            res = self.types_registry.get((uri, local))
            if res: self.process_structure(res[0], ui_item, res[1], visited)
            
        attrs = struct_node.xpath("./xs:attribute | ./xs:simpleContent/xs:extension/xs:attribute | ./xs:complexContent/xs:extension/xs:attribute", namespaces=self.ns)
        for attr in attrs:
            self.create_attribute_node(attr, ui_item, current_file)

        for ext in struct_node.xpath("./xs:complexContent/xs:extension | ./xs:simpleContent/xs:extension", namespaces=self.ns):
            for child in self.get_child_elements(ext):
                prefix = "● " if self.is_choice_variant(child) else ""
                self.create_node(child, ui_item, current_file, visited, prefix)
                
        for child in self.get_child_elements(struct_node):
            prefix = "● " if self.is_choice_variant(child) else ""
            self.create_node(child, ui_item, current_file, visited, prefix)

    def render_legend(self):
        for p, color in self.files_map.items():
            lbl = QLabel(f" {os.path.basename(p)} ")
            lbl.setFixedHeight(24) 
            lbl.setStyleSheet(f"background-color: {color}; color: black; border: 1px solid #333; font-weight: bold; padding: 2px 5px; border-radius: 3px;")
            self.legend_layout.addWidget(lbl)
        self.legend_layout.addStretch() 


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = XSDViewer()
    w.show()
    
    # ПЕРЕХВАТ ПАРАМЕТРА КОМАНДНОЙ СТРОКИ
    if len(sys.argv) > 1:
        target_file = sys.argv[1]
        w.load_file(target_file)

    sys.exit(app.exec())
