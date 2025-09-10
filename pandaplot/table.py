import sys
import pandas as pd
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTableView, QVBoxLayout, QWidget,
    QMenu
)
from PySide6.QtGui import QUndoCommand, QUndoStack, QAction
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QKeySequence


# ---------------- Undo/Redo Commands ----------------

class EditCommand(QUndoCommand):
    def __init__(self, model, index, old_value, new_value):
        super().__init__("Uredi ćeliju")
        self.model = model
        self.index = index
        self.old_value = old_value
        self.new_value = new_value

    def undo(self):
        self.model._setData(self.index, self.old_value)

    def redo(self):
        self.model._setData(self.index, self.new_value)


class InsertRowCommand(QUndoCommand):
    def __init__(self, model, row):
        super().__init__("Dodaj redak")
        self.model = model
        self.row = row

    def undo(self):
        self.model.removeRows([self.row])

    def redo(self):
        self.model.insertRow(self.row)


class InsertColCommand(QUndoCommand):
    def __init__(self, model, col):
        super().__init__("Dodaj stupac")
        self.model = model
        self.col = col
        self.colname = None

    def undo(self):
        self.model.removeColumns([self.col])

    def redo(self):
        if self.colname:
            self.model.insertColumn(self.col, self.colname)
        else:
            self.colname = self.model.insertColumn(self.col)


class RemoveRowsCommand(QUndoCommand):
    def __init__(self, model, rows):
        super().__init__("Obriši retke")
        self.model = model
        self.rows = sorted(rows)
        self.backup = model._df.iloc[self.rows].copy()

    def undo(self):
        for i, (_, row) in enumerate(self.backup.iterrows()):
            self.model.insertRow(self.rows[i], row)

    def redo(self):
        self.model.removeRows(self.rows)


class RemoveColsCommand(QUndoCommand):
    def __init__(self, model, cols):
        super().__init__("Obriši stupce")
        self.model = model
        self.cols = sorted(cols)
        self.backup = self.model._df.iloc[:, self.cols].copy()

    def undo(self):
        for i, col in enumerate(self.backup.columns):
            self.model.insertColumn(self.cols[i], col, self.backup[col])

    def redo(self):
        self.model.removeColumns(self.cols)


# ---------------- Model ----------------

class PandasModel(QAbstractTableModel):
    def __init__(self, df: pd.DataFrame, undo_stack: QUndoStack):
        super().__init__()
        self._df = df
        self.undo_stack = undo_stack


    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if role == Qt.ItemDataRole.EditRole:
            old_value = self._df.iloc[index.row(), index.column()]
            command = EditCommand(self, index, old_value, value)
            self.undo_stack.push(command)
            return True
        return False

    def _setData(self, index, value):
        row, col = index.row(), index.column()
        dtype = self._df.dtypes.iloc[col]
        try:
            if pd.api.types.is_numeric_dtype(dtype):
                if pd.api.types.is_integer_dtype(dtype):
                    value = int(value)
                else:
                    value = float(value)
        except Exception:
            pass
        self._df.iloc[row, col] = value
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    def sort(self, column, order):
        colname = self._df.columns[column]
        self.beginResetModel()
        self._df.sort_values(by=colname, ascending=(order == Qt.SortOrder.AscendingOrder), inplace=True)
        self._df.reset_index(drop=True, inplace=True)
        self.endResetModel()

    # ---- Row/Column Ops ----
    def insertRow(self, row, row_data=None):
        self.beginInsertRows(QModelIndex(), row, row)
        if row_data is None:
            empty = {col: [None] for col in self._df.columns}
            new_row = pd.DataFrame(empty)
        else:
            new_row = pd.DataFrame([row_data])
        self._df = pd.concat(
            [self._df.iloc[:row], new_row, self._df.iloc[row:]]
        ).reset_index(drop=True)
        self.endInsertRows()

    def insertColumn(self, col, name=None, series=None):
        self.beginInsertColumns(QModelIndex(), col, col)
        new_col_name = name or self._generate_new_colname()
        if series is None:
            self._df.insert(col, new_col_name, [None] * len(self._df))
        else:
            self._df.insert(col, new_col_name, series.values)
        self.endInsertColumns()
        return new_col_name

    def removeRows(self, rows):
        for row in sorted(rows, reverse=True):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._df.drop(index=row, inplace=True)
            self._df.reset_index(drop=True, inplace=True)
            self.endRemoveRows()

    def removeColumns(self, cols):
        for col in sorted(cols, reverse=True):
            self.beginRemoveColumns(QModelIndex(), col, col)
            self._df.drop(self._df.columns[col], axis=1, inplace=True)
            self.endRemoveColumns()

    def _generate_new_colname(self):
        base = "Novi stupac"
        name = base
        i = 1
        while name in self._df.columns:
            name = f"{base} {i}"
            i += 1
        return name


# ---------------- TableView ----------------

class TableView(QTableView):
    def __init__(self, model, undo_stack):
        super().__init__()
        self.setModel(model)
        self.undo_stack = undo_stack
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copySelection()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.pasteSelection()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.undo_stack.undo()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.undo_stack.redo()
        else:
            super().keyPressEvent(event)

    def copySelection(self):
        selection = self.selectionModel().selectedIndexes()
        if not selection:
            return
        rows = sorted(index.row() for index in selection)
        cols = sorted(index.column() for index in selection)
        rowcount = rows[-1] - rows[0] + 1
        colcount = cols[-1] - cols[0] + 1
        table = [["" for _ in range(colcount)] for _ in range(rowcount)]
        for index in selection:
            row = index.row() - rows[0]
            col = index.column() - cols[0]
            table[row][col] = index.data()
        text = "\n".join(["\t".join(row) for row in table])
        QApplication.clipboard().setText(text)

    def pasteSelection(self):
        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return
        selection = self.selectionModel().selectedIndexes()
        if not selection:
            return
        start_row = selection[0].row()
        start_col = selection[0].column()
        model: PandasModel = self.model()
        rows = clipboard.split("\n")
        for i, row in enumerate(rows):
            if not row.strip():
                continue
            cols = row.split("\t")
            for j, value in enumerate(cols):
                idx = model.index(start_row + i, start_col + j)
                if idx.isValid():
                    old_value = model._df.iloc[idx.row(), idx.column()]
                    command = EditCommand(model, idx, old_value, value)
                    self.undo_stack.push(command)

    def openMenu(self, position):
        menu = QMenu()
        model: PandasModel = self.model()
        indexes = self.selectionModel().selectedIndexes()

        if indexes:
            row = indexes[0].row()
            col = indexes[0].column()

            add_row_action = QAction("Dodaj redak ispod", self)
            add_row_action.triggered.connect(
                lambda: self.undo_stack.push(InsertRowCommand(model, row + 1))
            )
            menu.addAction(add_row_action)

            add_col_action = QAction("Dodaj stupac desno", self)
            add_col_action.triggered.connect(
                lambda: self.undo_stack.push(InsertColCommand(model, col + 1))
            )
            menu.addAction(add_col_action)

            menu.addSeparator()

            remove_rows_action = QAction("Obriši označene retke", self)
            remove_rows_action.triggered.connect(
                lambda: self.undo_stack.push(RemoveRowsCommand(model, set(i.row() for i in indexes)))
            )
            menu.addAction(remove_rows_action)

            remove_cols_action = QAction("Obriši označene stupce", self)
            remove_cols_action.triggered.connect(
                lambda: self.undo_stack.push(RemoveColsCommand(model, set(i.column() for i in indexes)))
            )
            menu.addAction(remove_cols_action)

        menu.exec(self.viewport().mapToGlobal(position))


# ---------------- MainWindow ----------------

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Excel-like Pandas Table (PySide6)")

        data = {
            "Ime": ["Ana", "Marko", "Ivana"],
            "Dob": [23, 35, 29],
            "Grad": ["Zagreb", "Rijeka", "Split"]
        }
        df = pd.DataFrame(data)

        self.undo_stack = QUndoStack(self)
        self.model = PandasModel(df, self.undo_stack)
        self.view = TableView(self.model, self.undo_stack)
        self.view.setSortingEnabled(True)
        self.view.resizeColumnsToContents()

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.view)
        self.setCentralWidget(container)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(800, 500)
    window.show()
    sys.exit(app.exec())
