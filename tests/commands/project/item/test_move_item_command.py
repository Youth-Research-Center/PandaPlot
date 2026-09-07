"""
Tests for the logging behavior added to MoveItemCommand.execute(). This file
intentionally does not attempt full command coverage -- only the newly-added
warning-log paths, following the mock/fixture conventions used in
tests/commands/project/item/test_delete_item_command.py.
"""

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.item.move_item_command import MoveItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state import AppContext, AppState


class TestMoveItemCommandLogging:
    """Test suite for MoveItemCommand's warning-log paths."""

    @pytest.fixture
    def mock_app_context(self):
        """Create mock app context with all dependencies."""
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller

        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        """Create a mock project for testing."""
        project = Mock()
        project.find_item = Mock()
        project.remove_item = Mock()
        project.add_item = Mock()
        return project

    def test_execute_logs_a_warning_when_no_project_loaded(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert "MoveItemCommand.execute" in caplog.text
        assert result is CommandResult.FAILURE

    def test_execute_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert "MoveItemCommand.execute" in caplog.text
        assert result is CommandResult.FAILURE

    def test_execute_logs_a_warning_when_no_item_id_specified(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        command = MoveItemCommand(app_context, item_id=None, target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert "MoveItemCommand.execute" in caplog.text
        assert result is CommandResult.FAILURE

    def test_execute_logs_a_warning_when_item_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None

        command = MoveItemCommand(app_context, item_id="missing-item", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert "missing-item" in caplog.text
        assert result is CommandResult.FAILURE

    def test_execute_returns_failure_when_target_folder_does_not_exist(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"

        def find_item(item_id):
            if item_id == "item-123":
                return item
            return None  # target folder lookup misses

        sample_project.find_item.side_effect = find_item
        sample_project.items_index = {"item-123": item}

        command = MoveItemCommand(
            app_context, item_id="item-123", target_folder_id="missing-folder"
        )

        result = command.execute()

        assert result is CommandResult.FAILURE
        sample_project.remove_item.assert_not_called()
        sample_project.add_item.assert_not_called()

    def test_execute_returns_success_when_move_succeeds(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="root", target_folder_id="root"
        )

        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert command.move_performed is True
        sample_project.remove_item.assert_called_once_with(item)
        sample_project.add_item.assert_called_once_with(item, parent_id=None)

    def test_execute_restores_item_to_source_when_add_to_target_fails(self, mock_app_context, sample_project):
        """If add_item() to the target raises after remove_item() already
        succeeded, the item must be re-added to its original parent rather
        than left orphaned, and move_performed must stay False so undo()
        correctly no-ops instead of silently doing nothing about a lost item."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item
        sample_project.add_item.side_effect = [RuntimeError("boom"), None]

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="source-folder", target_folder_id="root"
        )

        with pytest.raises(RuntimeError):
            command.execute()

        assert command.move_performed is False
        sample_project.remove_item.assert_called_once_with(item)
        assert sample_project.add_item.call_args_list == [
            ((item,), {"parent_id": None}),
            ((item,), {"parent_id": "source-folder"}),
        ]

    def test_undo_returns_noop_when_move_was_never_performed(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")
        # move_performed defaults to False -- execute() never succeeded.

        assert command.undo() is CommandResult.NOOP

    def test_undo_returns_success_after_a_successful_move(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="root", target_folder_id="root"
        )
        assert command.execute() is CommandResult.SUCCESS

        assert command.undo() is CommandResult.SUCCESS

    def test_undo_restores_item_to_target_when_re_add_to_source_fails(self, mock_app_context, sample_project):
        """Mirrors the execute() rollback: if re-adding the item to its
        original folder raises during undo(), the item must go back to the
        folder undo() found it in (the move's target) rather than being
        orphaned. Since that rollback succeeds, no net project-state change
        occurred, so the result must be ABORTED (retryable) rather than
        FAILURE -- FAILURE would make CommandExecutor.undo() move this
        command to the redo stack as if it had actually been undone, even
        though the item never left the target folder (see PR #373 review)."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="source-folder", target_folder_id="root"
        )
        assert command.execute() is CommandResult.SUCCESS

        sample_project.remove_item.reset_mock()
        sample_project.add_item.reset_mock()
        sample_project.add_item.side_effect = [RuntimeError("boom"), None]

        result = command.undo()

        assert result is CommandResult.ABORTED
        sample_project.remove_item.assert_called_once_with(item)
        assert sample_project.add_item.call_args_list == [
            ((item,), {"parent_id": "source-folder"}),
            ((item,), {"parent_id": None}),
        ]

    def test_undo_reraises_when_rollback_itself_also_fails(self, mock_app_context, sample_project):
        """If the compensating add_item() back to the target *also* raises,
        the item is genuinely orphaned (removed from its old location, never
        successfully re-added anywhere) -- a real uncertain state, unlike the
        recovered case above. Swallowing this as an ordinary FAILURE would
        let CommandExecutor.undo() move the command to the redo stack and
        leave the rest of history untouched, even though only an exception
        triggers the history invalidation this uncertain state actually
        needs -- so undo() must re-raise here, matching what redo() already
        does for the equivalent double-failure (see PR #373 review)."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="source-folder", target_folder_id="root"
        )
        assert command.execute() is CommandResult.SUCCESS

        sample_project.add_item.reset_mock()
        sample_project.add_item.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError):
            command.undo()

    def test_redo_returns_aborted_when_add_to_target_fails_but_rollback_succeeds(self, mock_app_context, sample_project):
        """redo() delegates to execute(); when execute()'s own rollback
        recovers (item put back in the source folder, no net change), redo()
        must report ABORTED instead of letting the exception propagate --
        otherwise CommandExecutor.redo() would invalidate the entire
        undo/redo history for what was actually a no-op (see PR #373
        review)."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item
        sample_project.add_item.side_effect = [RuntimeError("boom"), None]

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="source-folder", target_folder_id="root"
        )

        assert command.redo() is CommandResult.ABORTED
        assert command.move_performed is False

    def test_redo_reraises_when_rollback_itself_also_fails(self, mock_app_context, sample_project):
        """If the recovery add_item() also raises, the item's state is
        genuinely uncertain, so redo() must let the exception propagate
        (letting CommandExecutor invalidate history) rather than report
        ABORTED."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        item = Mock()
        item.name = "Some Item"
        sample_project.find_item.return_value = item
        sample_project.add_item.side_effect = RuntimeError("boom")

        command = MoveItemCommand(
            app_context, item_id="item-123", source_folder_id="source-folder", target_folder_id="root"
        )

        with pytest.raises(RuntimeError):
            command.redo()

    def test_redo_returns_aborted_when_execute_fails_validation_without_mutating(self, mock_app_context):
        """redo() delegates to execute(); a FAILURE returned (not raised) by
        execute() means one of its early guard checks refused before
        remove_item() ever ran -- nothing was mutated. redo() must translate
        that to ABORTED so CommandExecutor keeps the still-undone command on
        the redo stack, instead of forwarding a bare FAILURE that
        CommandExecutor would move to the undo stack as if it had actually
        been redone (see PR #373 review)."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")

        assert command.redo() is CommandResult.ABORTED

    def test_cleanup_does_not_raise(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")
        command.move_performed = True

        command.cleanup()
