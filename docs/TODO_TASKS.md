# PandaPlot TODO Tasks

This document contains all TODO items found in the codebase, organized by category and priority.

## High Priority Tasks

### Application Core

#### TASK-001: Multi-Project Support
**Title:** Clean state on opening new project or add support for multiple projects  
**Description:** Currently the application state isn't properly cleaned when opening a new project. Need to either implement proper state cleanup or add support for multiple concurrent projects.  
**Tags:** `core`, `state-management`, `architecture`  
**Related Tasks:** TASK-002, TASK-003  
**File:** `pandaplot/app.py:118`

#### TASK-002: Application State Refactoring
**Title:** Move project-related functionality out of application state  
**Description:** The application state currently contains project-specific functionality that should be moved to the project model or project container model.  
**Tags:** `core`, `state-management`, `refactoring`  
**Related Tasks:** TASK-001  
**File:** `pandaplot/models/state/app_state.py:24`

#### TASK-003: Configuration Management System
**Title:** Implement configuration management  
**Description:** Need to implement a proper configuration management system for the application. This is connected to settings. 
**Tags:** `core`, `configuration`, `architecture`  
**Related Tasks:** TASK-001, TASK-030  
**File:** `pandaplot/models/state/config.py:1`

### Data Management

#### TASK-004: Fix Data Serialization Issues
**Title:** Fix how transformed columns are saved  
**Description:** Transformed columns aren't saved correctly, need to fix the serialization mechanism.  
**Tags:** `data`, `serialization`, `bug`  
**Related Tasks:** TASK-005  
**File:** `pandaplot/app.py:113`

#### TASK-005: DataFrame Serialization
**Title:** Implement proper DataFrame serialization  
**Description:** Need to implement proper serialization mechanism for pandas DataFrames.  
**Tags:** `data`, `serialization`, `pandas`  
**Related Tasks:** TASK-004  
**File:** `pandaplot/models/project/items/dataset.py:40`

#### TASK-006: Fix Project Hierarchy Loading
**Title:** Fix loading hierarchy as items don't have parent id  
**Description:** Items don't have parent id and we need to know all parents in the collection for proper hierarchy loading.  
**Tags:** `data`, `hierarchy`, `project`  
**Related Tasks:** TASK-007, TASK-008  
**File:** `pandaplot/storage/project_data_manager.py:42`

### User Interface

#### TASK-007: Remove Qt Signals Dependency
**Title:** Remove signals and replace with event bus  
**Description:** Replace Qt signals with the existing event bus implementation throughout the application.  
**Tags:** `ui`, `refactoring`, `architecture`, `signals`  
**Related Tasks:** TASK-008, TASK-009  
**File:** `pandaplot/gui/main_window.py:124`

#### TASK-008: Component Setup Refactoring
**Title:** Move component setup out of main window  
**Description:** Setup logic for various UI components should happen somewhere else, not in the main window.  
**Tags:** `ui`, `refactoring`, `architecture`  
**Related Tasks:** TASK-007  
**Files:** 
- `pandaplot/gui/main_window.py:154`
- `pandaplot/gui/main_window.py:179`
- `pandaplot/gui/main_window.py:204`
- `pandaplot/gui/main_window.py:229`

## Medium Priority Tasks

### Chart and Visualization

#### TASK-009: Fix Chart Series Management
**Title:** Fix add and remove series functionality  
**Description:** Chart series addition and removal functionality needs to be fixed, particularly when loading damped pendulum project and trying to add series to energy graph.  
**Tags:** `charts`, `visualization`, `bug`  
**Related Tasks:** TASK-010  
**File:** `pandaplot/app.py:109,110`

#### TASK-010: Separate Chart Item Name and Title
**Title:** Separate item name and title for charts  
**Description:** Chart items should have separate name and title properties for better organization.  
**Tags:** `charts`, `data-model`  
**Related Tasks:** TASK-009  
**File:** `pandaplot/models/project/items/chart.py:98`

### Error Handling and Logging

#### TASK-011: Implement Proper Logging
**Title:** Convert prints into log statements  
**Description:** Replace print statements throughout the codebase with proper logging statements.  
**Tags:** `logging`, `debugging`, `maintenance`  
**Related Tasks:** TASK-012  
**File:** `pandaplot/app.py:111`

#### TASK-012: User Error Messages
**Title:** Log error messages to the user  
**Description:** Implement proper error message logging and display to users.  
**Tags:** `logging`, `ui`, `error-handling`  
**Related Tasks:** TASK-011, TASK-013  
**File:** `pandaplot/app.py:112`

#### TASK-013: Error Dialog Implementation
**Title:** Show error dialog or status message for transform errors  
**Description:** Implement proper error dialogs or status messages when data transformations fail.  
**Tags:** `ui`, `error-handling`, `dialogs`  
**Related Tasks:** TASK-012  
**File:** `pandaplot/gui/main_window.py:276`

### Project Management

#### TASK-014: Project Rename and Creation Dialog
**Title:** Allow project rename and create project creation dialog  
**Description:** Implement functionality to rename projects and create a proper project creation dialog.  
**Tags:** `project`, `ui`, `dialogs`  
**Related Tasks:** TASK-015  
**File:** `pandaplot/app.py:114`

#### TASK-015: Improve Project Name View
**Title:** Improve view of project name  
**Description:** Enhance how project names are displayed in the UI.  
**Tags:** `project`, `ui`  
**Related Tasks:** TASK-014  
**File:** `pandaplot/app.py:115`

#### TASK-016: Recent Projects Tracking
**Title:** Implement recent projects tracking  
**Description:** Add functionality to track and display recently opened projects.  
**Tags:** `project`, `user-experience`  
**Related Tasks:** TASK-017  
**File:** `pandaplot/services/data_managers/project_manager.py:134`

#### TASK-017: Project File Validation
**Title:** Implement project file validation  
**Description:** Add validation for project files during loading and saving operations.  
**Tags:** `project`, `validation`, `data-integrity`  
**Related Tasks:** TASK-016  
**File:** `pandaplot/services/data_managers/project_manager.py:157`

## Low Priority Tasks

### Architecture and Code Quality

#### TASK-018: UI Controller Facade
**Title:** Create UI controller facade for all UI-related interactions  
**Description:** The UI controller should be a facade for all UI-related interactions.  
**Tags:** `architecture`, `ui`, `facade-pattern`  
**Related Tasks:** TASK-019  
**File:** `pandaplot/gui/controllers/ui_controller.py:4`

#### TASK-019: Command Pattern Improvements
**Title:** Improve command pattern implementation  
**Description:** Various improvements needed for command pattern implementation throughout the application.  
**Tags:** `architecture`, `command-pattern`  
**Related Tasks:** TASK-018, TASK-020  
**Files:**
- `pandaplot/commands/command_executor.py:40`
- `pandaplot/commands/project/item/move_item_command.py:14`

#### TASK-020: Multi-threading Support
**Title:** Create process for multi-threaded operations  
**Description:** Implement proper multi-threading support for long-running operations.  
**Tags:** `performance`, `threading`, `architecture`  
**Related Tasks:** TASK-021  
**File:** `pandaplot/app.py:116`

#### TASK-021: Application Loading Optimization
**Title:** Improve initial loading of the app  
**Description:** Optimize the initial application loading process for better user experience.  
**Tags:** `performance`, `startup`, `optimization`  
**Related Tasks:** TASK-020  
**File:** `pandaplot/app.py:117`

### User Interface Enhancements

#### TASK-022: Theme and Style Management
**Title:** Improve how we handle styles and themes  
**Description:** Implement proper theme and style management system.  
**Tags:** `ui`, `theming`, `styling`  
**Related Tasks:** TASK-023, TASK-024, TASK-025  
**File:** `pandaplot/app.py:88`

#### TASK-023: Settings Storage Implementation
**Title:** Load from actual settings storage  
**Description:** Implement proper settings storage and loading mechanism.  
**Tags:** `settings`, `storage`, `configuration`  
**Related Tasks:** TASK-022, TASK-003  
**File:** `pandaplot/gui/dialogs/settings_dialog.py:336`

#### TASK-024: Theme Preview Implementation
**Title:** Implement theme preview functionality  
**Description:** Add theme preview functionality to settings dialog.  
**Tags:** `ui`, `theming`, `preview`  
**Related Tasks:** TASK-022, TASK-025  
**File:** `pandaplot/gui/dialogs/settings_dialog.py:393`

#### TASK-025: Font Preview Implementation
**Title:** Implement font preview functionality  
**Description:** Add font preview functionality for both regular and editor fonts.  
**Tags:** `ui`, `fonts`, `preview`  
**Related Tasks:** TASK-024  
**Files:**
- `pandaplot/gui/dialogs/settings_dialog.py:398`
- `pandaplot/gui/dialogs/settings_dialog.py:403`

### Feature Implementation

#### TASK-026: Welcome Tab Examples
**Title:** Implement examples functionality in welcome tab  
**Description:** Implement the examples functionality in the welcome tab.  
**Tags:** `ui`, `examples`, `welcome`  
**Related Tasks:** TASK-027  
**File:** `pandaplot/gui/components/tabs/welcome_tab.py:143`

#### TASK-027: Getting Started Steps
**Title:** Implement getting started step actions  
**Description:** Implement functionality for getting started steps in welcome tab.  
**Tags:** `ui`, `onboarding`, `welcome`  
**Related Tasks:** TASK-026  
**File:** `pandaplot/gui/components/tabs/welcome_tab.py:316`

#### TASK-028: Data Export Functionality
**Title:** Implement data export functionality  
**Description:** Add data export functionality to dataset tabs.  
**Tags:** `data`, `export`, `functionality`  
**Related Tasks:** TASK-029  
**File:** `pandaplot/gui/components/tabs/dataset_tab.py:678`

#### TASK-029: Note Save Dialog
**Title:** Show save dialog for notes  
**Description:** Implement save dialog functionality for note tabs.  
**Tags:** `ui`, `notes`, `dialogs`  
**Related Tasks:** TASK-028  
**File:** `pandaplot/gui/components/tabs/note_tab.py:458`

### Code Cleanup and Refactoring

#### TASK-030: File Extension Requirements
**Title:** Verify if we need file extension at all  
**Description:** Review and determine if file extensions are necessary for the current architecture.  
**Tags:** `architecture`, `file-system`, `cleanup`  
**Related Tasks:** TASK-003  
**File:** `pandaplot/app.py:33`

#### TASK-031: Tab Container Type Knowledge
**Title:** Remove tab type knowledge from tab container  
**Description:** Tab container shouldn't know about specific tab types directly.  
**Tags:** `ui`, `architecture`, `coupling`  
**Related Tasks:** TASK-032  
**File:** `pandaplot/gui/components/tabs/tab_container.py:28`

#### TASK-032: Item Creation Event Handling
**Title:** Handle new item creation at tab container level  
**Description:** New item creation should be handled on tab container level by listening to creation events.  
**Tags:** `ui`, `events`, `architecture`  
**Related Tasks:** TASK-031  
**File:** `pandaplot/gui/components/tabs/tab_container.py:516`

#### TASK-033: Settings Button Generalization
**Title:** Make settings button addition more generic  
**Description:** Icon bar shouldn't know about settings specifically, make button addition more generic.  
**Tags:** `ui`, `architecture`, `generalization`  
**Related Tasks:** TASK-034  
**File:** `pandaplot/gui/components/sidebar/icon_bar.py:40`

#### TASK-034: Command Usage in Icon Bar
**Title:** Use command instead of signal in icon bar  
**Description:** Replace signal usage with command pattern in icon bar.  
**Tags:** `ui`, `command-pattern`, `refactoring`  
**Related Tasks:** TASK-033, TASK-007  
**File:** `pandaplot/gui/components/sidebar/icon_bar.py:39`

#### TASK-035: Simplify Event Subscriptions
**Title:** Simplify subscriptions in project view panel  
**Description:** Review and simplify event subscriptions, probably don't need all of them.  
**Tags:** `events`, `optimization`, `cleanup`  
**Related Tasks:** TASK-007  
**File:** `pandaplot/gui/components/sidebar/project/project_view_panel.py:385`

## Technical Debt

#### TASK-036: Item Hierarchy Implementation
**Title:** Parse root hierarchy when item types are fully implemented  
**Description:** Complete the implementation of item hierarchy parsing once all item types are fully implemented.  
**Tags:** `data-model`, `hierarchy`, `technical-debt`  
**Related Tasks:** TASK-037  
**File:** `pandaplot/models/project/project.py:134`

#### TASK-037: Nested Items Parsing
**Title:** Parse nested items when their specific types are implemented  
**Description:** Implement nested items parsing once specific types are fully implemented.  
**Tags:** `data-model`, `hierarchy`, `technical-debt`  
**Related Tasks:** TASK-036  
**File:** `pandaplot/models/project/items/item.py:124`

#### TASK-038: Method Scope Review
**Title:** Consider getting rid of method or changing the scope  
**Description:** Review a specific method in Item class and decide whether to remove it or change its scope.  
**Tags:** `code-quality`, `api-design`, `technical-debt`  
**Related Tasks:** TASK-039  
**File:** `pandaplot/models/project/items/item.py:114`

#### TASK-039: Optional Types Elimination
**Title:** Avoid optional types in move item command  
**Description:** Refactor move item command to avoid using optional types.  
**Tags:** `type-safety`, `refactoring`, `technical-debt`  
**Related Tasks:** TASK-038  
**File:** `pandaplot/commands/project/item/move_item_command.py:14`

#### TASK-040: Command Executor Error Handling
**Title:** Improve command executor error handling  
**Description:** Consider raising exceptions instead of current error handling in save project command.  
**Tags:** `error-handling`, `command-pattern`, `technical-debt`  
**Related Tasks:** TASK-041  
**File:** `pandaplot/commands/project/project/save_project_command.py:89`

#### TASK-041: Ineffective Code Removal
**Title:** Remove or fix ineffective code in save project command  
**Description:** There's code that doesn't do anything currently and needs to be removed or fixed.  
**Tags:** `code-quality`, `cleanup`, `technical-debt`  
**Related Tasks:** TASK-040  
**File:** `pandaplot/commands/project/project/save_project_command.py:108`

---

## Summary

**Total Tasks:** 41  
**High Priority:** 6  
**Medium Priority:** 11  
**Low Priority:** 14  
**Technical Debt:** 10  

**Key Areas:**
- Architecture and state management (9 tasks)
- User interface improvements (12 tasks)  
- Data management and serialization (6 tasks)
- Error handling and logging (5 tasks)
- Project management features (4 tasks)
- Code cleanup and refactoring (5 tasks)

**Recommended Next Steps:**
1. Start with high-priority architecture tasks (TASK-001 to TASK-003)
2. Address data serialization issues (TASK-004, TASK-005)
3. Begin UI refactoring to remove Qt signals dependency (TASK-007, TASK-008)
4. Implement proper logging and error handling (TASK-011, TASK-012)
